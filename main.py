"""
PRELIQUIDADOR DE RETEFUENTE - COLOMBIA
====================================

Sistema automatizado para procesar facturas y calcular retención en la fuente
usando Google Gemini AI y FastAPI.

ARQUITECTURA MODULAR:
- Clasificador/: Clasificación de documentos con Gemini
- Liquidador/: Cálculo de retenciones según normativa
- Extraccion/: Extracción de texto de archivos (PDF, OCR, Excel, Word)
- Results/: Almacenamiento de resultados organizados por fecha

 FUNCIONALIDAD INTEGRADA:
- Retención en la fuente (funcionalidad original)
- Estampilla pro universidad nacional - obra publica (nueva funcionalidad)
- IVA y ReteIVA (nueva funcionalidad)
- Procesamiento paralelo cuando ambos impuestos aplican

Autor: Miguel Angel Jaramillo Durango
"""

import os
import json
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import asynccontextmanager

# FastAPI y dependencias web
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

# Configuración de logging - INFRASTRUCTURE LAYER
import logging
from app_logging import configurar_logging

logger = logging.getLogger(__name__)

# ===============================
# IMPORTAR MÓDULOS LOCALES
# ===============================

# Importar clases desde módulos
from app.validacion_archivos import ValidadorArchivos
from Clasificador import ProcesadorGemini
from Liquidador import LiquidadorRetencion
from Extraccion import ProcesadorArchivos, preprocesar_excel_limpio
from app.extraccion_hibrida import ExtractorHibrido

# Importar módulos de base de datos (SOLID: Clean Architecture Module)
from database import (
    DatabaseManager,
    SupabaseDatabase,
    BusinessDataService,
    crear_business_service,
    inicializar_database_manager  # INFRASTRUCTURE SETUP
)

# Cargar configuración global - INCLUYE ESTAMPILLA Y OBRA PÚBLICA
from config import (
    inicializar_configuracion,
    obtener_nits_disponibles,
    validar_nit_administrativo,
    nit_aplica_retencion_fuente,
    codigo_negocio_aplica_estampilla_universidad,
    codigo_negocio_aplica_obra_publica,
    nit_aplica_iva_reteiva,  #  NUEVA IMPORTACIÓN IVA
    nit_aplica_ICA,  #  NUEVA IMPORTACIÓN ICA
    nit_aplica_tasa_prodeporte,  #  NUEVA IMPORTACIÓN TASA PRODEPORTE
    nit_aplica_timbre,  #  NUEVA IMPORTACIÓN TIMBRE
    detectar_impuestos_aplicables_por_codigo,  #  DETECCIÓN AUTOMÁTICA POR CÓDIGO
    guardar_archivo_json,  # FUNCIÓN DE UTILIDAD PARA GUARDAR JSON

)

from app.validacion_negocios import validar_negocio

from app.clasificacion_documentos import clasificar_archivos

from app.ejecucion_tareas_paralelo import ejecutar_tareas_paralelo

from app.validar_retefuente import validar_retencion_en_la_fuente

from app.validar_impuestos_esp import validar_impuestos_especiales

from app.validar_iva_reteiva import validar_iva_reteiva

from app.validar_estampillas_generales import validar_estampillas_generales

from app.validar_ica import validar_ica

from app.validar_bomberil import validar_sobretasa_bomberil

from app.validar_tasa_prodeporte import validar_tasa_prodeporte

from app.validar_timbre import validar_timbre

from app.impuestos_no_aplicados import agregar_impuestos_no_aplicados


# Dependencias para preprocesamiento Excel
import pandas as pd
import io

# Importar utilidades - Respuestas mock para validaciones (SRP)
from utils.mockups import crear_respuesta_negocio_no_parametrizado
from utils.error_handlers import registrar_exception_handler

# ===============================
# INICIALIZACIÓN DE BASE DE DATOS
# ===============================

# Variables globales para el gestor de base de datos y servicio de negocio
# NOTA: Inicializadas en el lifespan de FastAPI
db_manager = None
business_service = None

# ===============================
# CONFIGURACIÓN Y CONSTANTES
# ===============================

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

# Inicializar configuración global
inicializar_configuracion()

# Configurar APIs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY no está configurada en el archivo .env")

# Importar conceptos retefuente  desde configuración
from config import CONCEPTOS_RETEFUENTE

# ===============================
# NOTA: Los modelos Pydantic fueron movidos a modelos/modelos.py (Domain Layer - Clean Architecture)
# Este archivo trabaja directamente con diccionarios en lugar de modelos Pydantic
# ===============================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manejador del ciclo de vida de la aplicación.
    Reemplaza los eventos startup/shutdown.

    PRINCIPIOS SOLID:
    - SRP: Solo maneja ciclo de vida de la aplicación
    - DIP: Usa funciones de infraestructura inyectadas
    """
    # Código que se ejecuta ANTES de que la aplicación inicie
    configurar_logging()
    global logger, db_manager, business_service
    logger = logging.getLogger(__name__)

    logger.info(" Worker de FastAPI iniciándose... Cargando configuración.")
    if not inicializar_configuracion():
        logger.critical(" FALLO EN LA CARGA DE CONFIGURACIÓN. La aplicación puede no funcionar correctamente.")

    # Inicializar gestor de base de datos usando Infrastructure Layer
    db_manager, business_service = inicializar_database_manager()

    yield # <--- La aplicación se ejecuta aquí

    # Código que se ejecuta DESPUÉS de que la aplicación se detiene (opcional)
    logger.info(" Worker de FastAPI deteniéndose.")

# ===============================
# API FASTAPI
# ===============================

app = FastAPI(
    title="Preliquidador de Retefuente - Colombia",
    description="Sistema automatizado para calcular retención en la fuente con arquitectura modular",
    version="2.0.0",
    lifespan=lifespan
)

# Registrar exception handler para validaciones (SRP)
# Convierte errores 422 de validación Pydantic en respuestas 200 OK con estructura mockup
registrar_exception_handler(app)


@app.post("/api/procesar-facturas")
async def procesar_facturas_integrado(
    archivos: List[UploadFile] = File(...),
    codigo_del_negocio: int = Form(...),
    proveedor: str = Form(...),
    nit_proveedor: str = Form(...),
    estructura_contable: int = Form(...),
    observaciones_tp: Optional[str] = Form(None),
    genera_presupuesto: Optional[str] = Form(None),
    rubro: Optional[str] = Form(None),
    centro_costos: Optional[int] = Form(None),
    numero_contrato: Optional[str] = Form(None),
    valor_contrato_municipio: Optional[float] = Form(None),
    tipoMoneda: Optional[str] = Form("COP")
) -> JSONResponse:
    """
     ENDPOINT PRINCIPAL - SISTEMA INTEGRADO v3.0

    Procesa facturas y calcula múltiples impuestos en paralelo:
     RETENCIÓN EN LA FUENTE (funcionalidad original)
     ESTAMPILLA PRO UNIVERSIDAD NACIONAL (integrada)
     CONTRIBUCIÓN A OBRA PÚBLICA 5% (integrada)
     IVA Y RETEIVA (nueva funcionalidad)
     PROCESAMIENTO PARALELO cuando múltiples impuestos aplican
     GUARDADO AUTOMÁTICO de JSONs en Results/
     CONSULTA DE BASE DE DATOS para información del negocio
     CONTEXTO DEL PROVEEDOR para mejor identificación (v3.0)

    Args:
        archivos: Lista de archivos (facturas, RUTs, anexos, contratos)
        codigo_del_negocio: Código del negocio para consultar en base de datos (el NIT administrativo se obtiene de la DB)
        proveedor: Nombre del proveedor que emite la factura (OBLIGATORIO - mejora identificación de consorcios y retenciones)

    Returns:
        JSONResponse: Resultado consolidado de todos los impuestos aplicables
    """
    logger.info(f" ENDPOINT PRINCIPAL INTEGRADO v3.0 - Procesando {len(archivos)} archivos")
    logger.info(f" Código negocio: {codigo_del_negocio} | Proveedor: {proveedor}")

    try:
        # =================================
        # PASO 1: VALIDACIÓN Y CONFIGURACIÓN
        # =================================

        # Consultar información del negocio usando BusinessService 
        resultado_negocio = business_service.obtener_datos_negocio(codigo_del_negocio)
        
        #validacion de de impuestos a procesar dada la naturaleza del proovedor 
        
        resultado_validacion = validar_negocio(resultado_negocio=resultado_negocio,codigo_del_negocio=codigo_del_negocio, business_service=business_service)
        
        if isinstance(resultado_validacion,JSONResponse):
            return resultado_validacion
        
        (impuestos_a_procesar, aplica_retencion, aplica_estampilla, aplica_obra_publica, aplica_iva, aplica_ica, aplica_timbre, aplica_tasa_prodeporte, nombre_negocio, nit_administrativo, deteccion_impuestos,nombre_entidad) = resultado_validacion
        
        # =================================
        # PASO 2: FILTRADO Y VALIDACIÓN DE ARCHIVOS
        # =================================
                
        validador_archivos = ValidadorArchivos()
        
        archivos_validos, archivos_ignorados = validador_archivos.validar(archivos)
   
        # =================================
        # PASO 3: EXTRACCIÓN HÍBRIDA DE TEXTO
        # =================================
        
        extractor_hibrido = ExtractorHibrido()
        
        archivos_directos, textos_preprocesados = await extractor_hibrido.extraer(archivos_validos)
        
        # =================================
        # PASO 4: CLASIFICACIÓN HÍBRIDA CON MULTIMODALIDAD
        # =================================

        # Clasificar documentos usando enfoque híbrido multimodal
        clasificador = ProcesadorGemini(estructura_contable=estructura_contable, db_manager=db_manager)

       
        resultado_clasificacion = await clasificar_archivos(
            clasificador=clasificador,
            archivos_directos=archivos_directos,
            textos_preprocesados=textos_preprocesados,
            provedor=proveedor,
            nit_administrativo=nit_administrativo,
            nombre_entidad=nombre_entidad,
            impuestos_a_procesar=impuestos_a_procesar
        )

        documentos_clasificados, es_consorcio, es_recurso_extranjero, es_facturacion_extranjera, clasificacion = resultado_clasificacion

        # =================================
        # PASO 4.1: PROCESAMIENTO PARALELO (TODOS LOS IMPUESTOS)
        # =================================

        # Log resumido de documentos (sin mostrar contenido completo)
        docs_resumen = {nombre: {"categoria": info["categoria"], "chars": len(info["texto"])}
                       for nombre, info in documentos_clasificados.items()}
        logger.info(f"Documentos a analizar: {docs_resumen}")

        # REFACTOR SOLID: Modulo de preparacion de tareas
        from app.preparacion_tareas_analisis import preparar_tareas_analisis

        # Preparar todas las tareas de analisis en paralelo
        resultado_preparacion = await preparar_tareas_analisis(
            clasificador=clasificador,
            estructura_contable=estructura_contable,
            db_manager=db_manager,
            documentos_clasificados=documentos_clasificados,
            archivos_directos=archivos_directos,
            aplica_retencion=aplica_retencion,
            aplica_estampilla=aplica_estampilla,
            aplica_obra_publica=aplica_obra_publica,
            aplica_iva=aplica_iva,
            aplica_ica=aplica_ica,
            aplica_timbre=aplica_timbre,
            aplica_tasa_prodeporte=aplica_tasa_prodeporte,
            es_consorcio=es_consorcio,
            es_recurso_extranjero=es_recurso_extranjero,
            es_facturacion_extranjera=es_facturacion_extranjera,
            proveedor=proveedor,
            nit_administrativo=nit_administrativo,
            observaciones_tp=observaciones_tp,
            impuestos_a_procesar=impuestos_a_procesar
        )

        # Extraer cache (compatible con codigo existente)
        cache_archivos = resultado_preparacion.cache_archivos

        # =================================
        # PASO 4.2: EJECUTAR TAREAS (TODOS LOS IMPUESTOS)
        # =================================

        logger.info(f" Ejecutando {len(resultado_preparacion.tareas_analisis)} análisis paralelos con Gemini...")

        try:
            # Ejecutar todas las tareas en paralelo con control de concurrencia
            resultado_ejecucion = await ejecutar_tareas_paralelo(
                tareas_analisis=resultado_preparacion.tareas_analisis,
                max_workers=4
            )

            # Extraer resultados del dataclass
            resultados_analisis = resultado_ejecucion.resultados_analisis

            # Logging de metricas
            logger.info(
                f" Ejecucion completada: {resultado_ejecucion.tareas_exitosas}/{resultado_ejecucion.total_tareas} exitosas "
                f"en {resultado_ejecucion.tiempo_total:.2f}s"
            )

        except Exception as e:
            logger.error(f" Error ejecutando analisis paralelo: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error ejecutando analisis paralelo: {str(e)}"
            )

        # Guardar analisis paralelo con metricas adicionales
        analisis_paralelo_data = {
            "timestamp": datetime.now().isoformat(),
            "impuestos_analizados": resultado_ejecucion.impuestos_procesados,
            "resultados_analisis": resultado_ejecucion.resultados_analisis,
            "metricas": {
                "total_tareas": resultado_ejecucion.total_tareas,
                "exitosas": resultado_ejecucion.tareas_exitosas,
                "fallidas": resultado_ejecucion.tareas_fallidas,
                "tiempo_total_segundos": resultado_ejecucion.tiempo_total
            }
        }
        guardar_archivo_json(analisis_paralelo_data, "analisis_paralelo")
        
        # =================================
        # PASO 5: LIQUIDACIÓN DE IMPUESTOS
        # =================================

        logger.info(" Iniciando liquidación de impuestos en paralelo...")
        
        resultado_final = {
            "impuestos_procesados": impuestos_a_procesar,
            "nit_administrativo": nit_administrativo,
            "nombre_entidad": nombre_entidad,
            "timestamp": datetime.now().isoformat(),
            "version": "2.9.3",
            "impuestos": {}  # NUEVA ESTRUCTURA PARA TODOS LOS IMPUESTOS
        }
        
        # Liquidar Retefuente
        resultado_retefuente = await validar_retencion_en_la_fuente(
            resultados_analisis=resultados_analisis,
            aplica_retencion=aplica_retencion,
            es_consorcio=es_consorcio,
            es_recurso_extranjero=es_recurso_extranjero,
            es_facturacion_extranjera=es_facturacion_extranjera,
            estructura_contable=estructura_contable,
            db_manager=db_manager,
            nit_administrativo=nit_administrativo,
            tipoMoneda=tipoMoneda,
            archivos_directos=archivos_directos,
            cache_archivos=cache_archivos
        )

        if resultado_retefuente:
            resultado_final["impuestos"]["retefuente"] = resultado_retefuente
            
        # Liquidar Impuestos Especiales (Estampilla Pro Universidad Nacional + Obra Pública)
        resultado_especiales = await validar_impuestos_especiales(
            resultados_analisis=resultados_analisis,
            aplica_estampilla=aplica_estampilla,
            aplica_obra_publica=aplica_obra_publica,
            codigo_del_negocio=codigo_del_negocio,
            nombre_negocio=nombre_negocio
        )

        if resultado_especiales:
            if "estampilla_universidad" in resultado_especiales:
                resultado_final["impuestos"]["estampilla_universidad"] = resultado_especiales["estampilla_universidad"]

            if "contribucion_obra_publica" in resultado_especiales:
                resultado_final["impuestos"]["contribucion_obra_publica"] = resultado_especiales["contribucion_obra_publica"]
        
        # Liquidar IVA y ReteIVA
        resultado_iva_reteiva = await validar_iva_reteiva(
            resultados_analisis=resultados_analisis,
            aplica_iva=aplica_iva,
            es_recurso_extranjero=es_recurso_extranjero,
            es_facturacion_extranjera=es_facturacion_extranjera,
            nit_administrativo=nit_administrativo,
            tipoMoneda=tipoMoneda
        )

        if resultado_iva_reteiva:
            resultado_final["impuestos"]["iva_reteiva"] = resultado_iva_reteiva

        # Liquidar Estampillas Generales
        resultado_estampillas_generales = await validar_estampillas_generales(
            resultados_analisis=resultados_analisis
        )

        if resultado_estampillas_generales:
            resultado_final["impuestos"]["estampillas_generales"] = resultado_estampillas_generales

        # Liquidar ICA
        resultado_ica = await validar_ica(
            resultados_analisis=resultados_analisis,
            aplica_ica=aplica_ica,
            estructura_contable=estructura_contable,
            db_manager=db_manager,
            tipoMoneda=tipoMoneda
        )

        if resultado_ica:
            resultado_final["impuestos"]["ica"] = resultado_ica

        # Liquidar Sobretasa Bomberil (REFACTORIZADO - Depende de ICA)
        resultado_sobretasa = await validar_sobretasa_bomberil(
            resultado_final=resultado_final,
            db_manager=db_manager
        )

        if resultado_sobretasa:
            resultado_final["impuestos"]["sobretasa_bomberil"] = resultado_sobretasa

        # Liquidar Tasa Prodeporte (REFACTORIZADO)
        resultado_tasa_prodeporte = await validar_tasa_prodeporte(
            resultados_analisis=resultados_analisis,
            db_manager=db_manager,
            observaciones_tp=observaciones_tp,
            genera_presupuesto=genera_presupuesto,
            rubro=rubro,
            centro_costos=centro_costos,
            numero_contrato=numero_contrato,
            valor_contrato_municipio=valor_contrato_municipio
        )

        if resultado_tasa_prodeporte:
            resultado_final["impuestos"]["tasa_prodeporte"] = resultado_tasa_prodeporte

        # Liquidar Timbre (REFACTORIZADO)
        resultado_timbre = await validar_timbre(
            resultados_analisis=resultados_analisis,
            aplica_timbre=aplica_timbre,
            db_manager=db_manager,
            clasificador_gemini=clasificador,
            nit_administrativo=nit_administrativo,
            codigo_del_negocio=codigo_del_negocio,
            proveedor=proveedor,
            documentos_clasificados=documentos_clasificados,
            archivos_directos=archivos_directos,
            cache_archivos=cache_archivos
        )

        if resultado_timbre:
            resultado_final["impuestos"]["timbre"] = resultado_timbre

        # =================================
        # COMPLETAR IMPUESTOS QUE NO APLICAN
        # =================================

        agregar_impuestos_no_aplicados(
            resultado_final=resultado_final,
            deteccion_impuestos=deteccion_impuestos, 
            aplica_estampilla=aplica_estampilla,
            aplica_obra_publica=aplica_obra_publica,
            aplica_iva=aplica_iva,
            aplica_tasa_prodeporte=aplica_tasa_prodeporte,
            aplica_timbre=aplica_timbre,
            nit_administrativo=nit_administrativo,
            nombre_negocio=nombre_negocio
        )

        # =================================
        # PASO 6: CONSOLIDACIÓN Y GUARDADO FINAL
        # =================================
        
        # Agregar metadatos finales
        resultado_final.update({
            "nit_administrativo": nit_administrativo,
            "nombre_entidad": nombre_entidad,
            "es_consorcio": es_consorcio,
            "es_facturacion_extranjera": es_facturacion_extranjera,
            "documentos_procesados": len(archivos),
            "documentos_clasificados": list(clasificacion.keys()),
        })
        
        # Guardar resultado final completo
        guardar_archivo_json(resultado_final, "resultado_final")
        
        # Log final de éxito
        logger.info("Procesamiento completado exitosamente")
        logger.info(f"Impuestos procesados: {resultado_final.get('impuestos_procesados', [])}")

        
        return JSONResponse(
            status_code=200,
            content=resultado_final
        )
        
    except HTTPException:
        # Re-lanzar HTTPExceptions directamente
        raise
    except Exception as e:
        # Manejo de errores generales
        error_msg = f"Error en procesamiento integrado: {str(e)}"
        logger.error(f" {error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Guardar error para debugging
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "nit_administrativo": nit_administrativo,
            "error_mensaje": error_msg,
            "error_tipo": type(e).__name__,
            "traceback": traceback.format_exc(),
            "archivos_recibidos": [archivo.filename for archivo in archivos],
            "version": "2.4.0"
        }
        guardar_archivo_json(error_data, "error_procesamiento")
        
        # Determinar tipo de error para respuesta apropiada
        if "Gemini" in error_msg or "API" in error_msg:
            error_type = "API_ERROR"
            user_message = "Error en el servicio de inteligencia artificial"
        elif "liquidar" in error_msg.lower():
            error_type = "CALCULATION_ERROR"
            user_message = "Error en los cálculos de impuestos"
        elif "extrac" in error_msg.lower():
            error_type = "EXTRACTION_ERROR"
            user_message = "Error extrayendo texto de los archivos"
        else:
            error_type = "GENERAL_ERROR"
            user_message = "Error general en el procesamiento"
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error de procesamiento ({error_type})",
                "mensaje": user_message,
                "detalle_tecnico": error_msg,
                "tipo": error_type,
                "version": "2.4.0",
                "timestamp": datetime.now().isoformat()
            }
        )

# ===============================
# ENDPOINTS ADICIONALES
# ===============================


@app.get("/api/nits-disponibles")
async def obtener_nits_disponibles_endpoint():
    """Obtener lista de NITs administrativos disponibles"""
    try:
        nits_data = obtener_nits_disponibles()
        
        # Formatear para el frontend
        nits_formateados = []
        for nit, datos in nits_data.items():
            nits_formateados.append({
                "nit": nit,
                "nombre": datos["nombre"],
                "impuestos_aplicables": datos["impuestos_aplicables"],
                "total_impuestos": len(datos["impuestos_aplicables"]),
                "aplica_retencion_fuente": "RETENCION_FUENTE" in datos["impuestos_aplicables"],
                "aplica_estampilla_universidad": "ESTAMPILLA_UNIVERSIDAD" in datos["impuestos_aplicables"]
            })
        
        return {
            "success": True,
            "nits": nits_formateados,
            "total_nits": len(nits_formateados),
            "version": "2.4.0",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo NITs disponibles: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Error obteniendo NITs",
                "mensaje": str(e),
                "version": "2.4.0"
            }
        )

@app.get("/api/extracciones")
async def obtener_estadisticas_extracciones():
    """Obtener estadísticas de textos extraídos guardados"""
    try:
        extractor = ProcesadorArchivos()
        estadisticas = extractor.obtener_estadisticas_guardado()
        
        return {
            "success": True,
            "version": "2.4.0",
            "modulo": "Extraccion",
            "estadisticas": estadisticas,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de extracciones: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Error obteniendo estadísticas",
                "mensaje": str(e),
                "modulo": "Extraccion"
            }
        )

@app.post("/api/prueba-simple")
async def prueba_simple(nit_administrativo: Optional[str] = Form(None)):
    """Endpoint de prueba simple SIN archivos"""
    logger.info(f" PRUEBA SIMPLE: Recibido NIT: {nit_administrativo}")
    return {
        "success": True,
        "mensaje": "POST sin archivos funciona - Sistema integrado",
        "nit_recibido": nit_administrativo,
        "version": "2.4.0",
        "sistema": "integrado_retefuente_estampilla",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/database/health")
async def database_health_check():
    """
    Verificar el estado de la conexión a la base de datos usando BusinessService.

    PRINCIPIO SRP: Endpoint específico para health check de base de datos
    """
    if not business_service:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": "BusinessService no está inicializado",
                "details": "Error en inicialización del sistema de base de datos"
            }
        )

    try:
        # Usar el servicio para validar disponibilidad (SRP)
        is_available = business_service.validar_disponibilidad_database()

        if is_available:
            return {
                "status": "healthy",
                "message": "Conexión a base de datos OK",
                "service": "BusinessDataService",
                "architecture": "SOLID + Strategy Pattern",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "message": "Conexión a base de datos no disponible",
                    "service": "BusinessDataService",
                    "timestamp": datetime.now().isoformat()
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Error verificando base de datos: {str(e)}",
                "service": "BusinessDataService",
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/api/database/test/{codigo_negocio}")
async def test_database_query(codigo_negocio: int):
    """
    Probar consulta de negocio por código usando BusinessService.

    PRINCIPIO SRP: Endpoint específico para testing de consultas de negocio
    """
    if not business_service:
        return JSONResponse(
            status_code=503,
            content={
                "error": "BusinessService no está disponible",
                "details": "Error en inicialización del sistema de base de datos",
                "service": "BusinessDataService"
            }
        )

    try:
        # Usar el servicio para la consulta (SRP + DIP)
        resultado = business_service.obtener_datos_negocio(codigo_negocio)

        return {
            "resultado": resultado,
            "service": "BusinessDataService",
            "architecture": "SOLID + Clean Architecture",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Error consultando negocio: {str(e)}",
                "codigo_consultado": codigo_negocio,
                "service": "BusinessDataService",
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/api/diagnostico")
async def diagnostico_completo():
    """Endpoint de diagnóstico completo para verificar todos los componentes del sistema"""
    diagnostico = {
        "timestamp": datetime.now().isoformat(),
        "version": "2.4.0",
        "sistema": "integrado_retefuente_estampilla",
        "estado_general": "VERIFICANDO",
        "componentes": {}
    }
    
    try:
        # 1. VERIFICAR VARIABLES DE ENTORNO
        diagnostico["componentes"]["variables_entorno"] = {
            "gemini_api_key": {
                "configurado": bool(GEMINI_API_KEY),
                "status": "OK" if GEMINI_API_KEY else "ERROR",
                "mensaje": "Configurado" if GEMINI_API_KEY else "FALTA GEMINI_API_KEY en .env"
            },
            "google_credentials": {
                "configurado": bool(GOOGLE_CLOUD_CREDENTIALS),
                "archivo_existe": bool(GOOGLE_CLOUD_CREDENTIALS and os.path.exists(GOOGLE_CLOUD_CREDENTIALS)),
                "status": "OK" if (GOOGLE_CLOUD_CREDENTIALS and os.path.exists(GOOGLE_CLOUD_CREDENTIALS)) else "WARNING",
                "mensaje": "Configurado correctamente" if (GOOGLE_CLOUD_CREDENTIALS and os.path.exists(GOOGLE_CLOUD_CREDENTIALS)) else "Vision no disponible (opcional)"
            }
        }
        
        # 2. VERIFICAR IMPORTACIONES DE MÓDULOS
        modulos_status = {}
        
        # Extraccion
        try:
            extractor = ProcesadorArchivos()
            modulos_status["extraccion"] = {
                "importacion": "OK",
                "instanciacion": "OK",
                "mensaje": "Módulo funcionando correctamente"
            }
        except Exception as e:
            modulos_status["extraccion"] = {
                "importacion": "ERROR",
                "instanciacion": "ERROR",
                "mensaje": f"Error: {str(e)}",
                "error_completo": str(e)
            }
            
        # Clasificador
        try:
            clasificador = ProcesadorGemini()
            modulos_status["clasificador"] = {
                "importacion": "OK",
                "instanciacion": "OK",
                "mensaje": "Módulo funcionando correctamente"
            }
        except Exception as e:
            modulos_status["clasificador"] = {
                "importacion": "ERROR",
                "instanciacion": "ERROR",
                "mensaje": f"Error: {str(e)}",
                "error_completo": str(e)
            }
            
        # Liquidador
        try:
            liquidador = LiquidadorRetencion()
            modulos_status["liquidador"] = {
                "importacion": "OK",
                "instanciacion": "OK",
                "mensaje": "Módulo funcionando correctamente"
            }
        except Exception as e:
            modulos_status["liquidador"] = {
                "importacion": "ERROR",
                "instanciacion": "ERROR",
                "mensaje": f"Error: {str(e)}",
                "error_completo": str(e)
            }
            
        diagnostico["componentes"]["modulos"] = modulos_status
        
        # 3. VERIFICAR FUNCIONES DE CONFIG
        config_status = {}
        
        try:
            # Probar obtener NITs
            nits = obtener_nits_disponibles()
            config_status["obtener_nits"] = {
                "status": "OK",
                "cantidad_nits": len(nits),
                "mensaje": f"Se encontraron {len(nits)} NITs configurados"
            }
            
            # Probar validación de NIT (con el primer NIT disponible)
            if nits:
                primer_nit = list(nits.keys())[0]
                es_valido, nombre, impuestos = validar_nit_administrativo(primer_nit)
                config_status["validar_nit"] = {
                    "status": "OK" if es_valido else "ERROR",
                    "nit_prueba": primer_nit,
                    "es_valido": es_valido,
                    "nombre_entidad": nombre if es_valido else None,
                    "mensaje": "Validación de NIT funcionando" if es_valido else "Error en validación"
                }
                
                # Probar verificación retención fuente
                aplica_rf = nit_aplica_retencion_fuente(primer_nit)
                config_status["retencion_fuente"] = {
                    "status": "OK",
                    "aplica_retencion": aplica_rf,
                    "mensaje": f"NIT {primer_nit} {'SÍ' if aplica_rf else 'NO'} aplica retención fuente"
                }
                
         
                #  VERIFICAR DETECCIÓN AUTOMÁTICA INTEGRADA
                try:
                    deteccion_auto = detectar_impuestos_aplicables(primer_nit)
                    config_status["deteccion_automatica"] = {
                        "status": "OK",
                        "impuestos_detectados": deteccion_auto['impuestos_aplicables'],
                        "mensaje": f"Detección automática funcionando: {len(deteccion_auto['impuestos_aplicables'])} impuestos detectados"
                    }
                except Exception as e:
                    config_status["deteccion_automatica"] = {
                        "status": "ERROR",
                        "mensaje": f"Error en detección automática: {str(e)}"
                    }
            else:
                config_status["validar_nit"] = {
                    "status": "WARNING",
                    "mensaje": "No hay NITs para probar validación"
                }
                
        except Exception as e:
            config_status["error_general"] = {
                "status": "ERROR",
                "mensaje": f"Error en funciones de config: {str(e)}",
                "error_completo": str(e)
            }
            
        diagnostico["componentes"]["configuracion"] = config_status
        
        # 4. VERIFICAR ESTRUCTURA DE ARCHIVOS
        archivos_status = {
            "carpetas_requeridas": {},
            "archivos_criticos": {}
        }
        
        carpetas_requeridas = ["Clasificador", "Liquidador", "Extraccion", "Static", "Results"]
        for carpeta in carpetas_requeridas:
            existe = os.path.exists(carpeta)
            archivos_py = []
            if existe:
                try:
                    archivos_py = [f.name for f in Path(carpeta).glob("*.py")]
                except:
                    pass
                    
            archivos_status["carpetas_requeridas"][carpeta] = {
                "existe": existe,
                "archivos_python": len(archivos_py),
                "archivos_lista": archivos_py[:5],  # Solo primeros 5
                "status": "OK" if existe else "ERROR"
            }
            
        # Verificar archivos críticos
        archivos_criticos = [".env", "config.py", "RETEFUENTE_CONCEPTOS.xlsx"]
        for archivo in archivos_criticos:
            existe = os.path.exists(archivo)
            archivos_status["archivos_criticos"][archivo] = {
                "existe": existe,
                "status": "OK" if existe else "ERROR"
            }
            
        diagnostico["componentes"]["estructura_archivos"] = archivos_status
        
        # 5. VERIFICAR CONCEPTOS CARGADOS
        diagnostico["componentes"]["conceptos"] = {
            "total_cargados": len(CONCEPTOS_RETEFUENTE),
            "ejemplos": list(CONCEPTOS_RETEFUENTE.keys())[:3],
            "status": "OK" if len(CONCEPTOS_RETEFUENTE) > 0 else "ERROR",
            "mensaje": f"Se cargaron {len(CONCEPTOS_RETEFUENTE)} conceptos de retefuente"
        }
        
        # 6. DETERMINAR ESTADO GENERAL
        errores_criticos = []
        
        # Verificar errores críticos
        if not GEMINI_API_KEY:
            errores_criticos.append("GEMINI_API_KEY no configurado")
            
        for modulo, status in modulos_status.items():
            if status["importacion"] == "ERROR":
                errores_criticos.append(f"Módulo {modulo} no se puede importar")
                
        if len(CONCEPTOS_RETEFUENTE) == 0:
            errores_criticos.append("No se cargaron conceptos de retefuente")
            
        # Estado final
        if errores_criticos:
            diagnostico["estado_general"] = "ERROR"
            diagnostico["errores_criticos"] = errores_criticos
            diagnostico["mensaje"] = f"Se encontraron {len(errores_criticos)} errores críticos"
        else:
            diagnostico["estado_general"] = "OK"
            diagnostico["mensaje"] = "Sistema integrado funcionando correctamente - Retefuente + Estampilla + Obra Pública"
            
        return diagnostico
        
    except Exception as e:
        logger.error(f"Error en diagnóstico: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "estado_general": "ERROR_DIAGNOSTICO",
            "mensaje": f"Error ejecutando diagnóstico: {str(e)}",
            "error_completo": str(e)
        }

# ===============================
# EJECUCIÓN PRINCIPAL
# ===============================

if __name__ == "__main__":
    import uvicorn
    

    logger.info(" Iniciando Preliquidador de Retefuente v2.0 - Sistema Integrado")
    logger.info(" Funcionalidades: Retención en la fuente + Estampilla universidad + Obra pública 5%")
    logger.info(f" Gemini configurado: {bool(GEMINI_API_KEY)}")
    #logger.info(f" Vision configurado: {bool(GOOGLE_CLOUD_CREDENTIALS)}")
    
    # Verificar estructura de carpetas
    carpetas_requeridas = ["Clasificador", "Liquidador", "Extraccion",  "Results"]
    for carpeta in carpetas_requeridas:
        if os.path.exists(carpeta):
            logger.info(f" Módulo {carpeta}/ encontrado")
        else:
            logger.warning(f" Módulo {carpeta}/ no encontrado")
    

    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        timeout_keep_alive=120,
        limit_max_requests=1000,
        limit_concurrency=100
    )
