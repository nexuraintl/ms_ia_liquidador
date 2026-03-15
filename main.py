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
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
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
    inicializar_database_manager,  # INFRASTRUCTURE SETUP
    obtener_uvt_desde_api,  # OBTENER UVT DESDE API EXTERNA
)

# Cargar configuración global - INCLUYE ESTAMPILLA Y OBRA PÚBLICA
from config import (
    inicializar_configuracion,
    establecer_uvt,
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



# Importar modulo de procesamiento asincrono (Background)
from Background import WebhookPublisher, BackgroundProcessor

# Dependencias para preprocesamiento Excel
import pandas as pd
import io

# Importar utilidades - Respuestas mock para validaciones (SRP)
from utils.error_handlers import registrar_exception_handler

# ===============================
# INICIALIZACIÓN DE BASE DE DATOS
# ===============================

# Variables globales para el gestor de base de datos y servicio de negocio
# NOTA: Inicializadas en el lifespan de FastAPI
db_manager = None
business_service = None

# Variables globales para procesamiento asincrono (Background)
# NOTA: Inicializadas en el lifespan de FastAPI
webhook_publisher = None
background_processor = None

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

    MODIFICADO v3.13.0:
    - Elimina autenticacion en startup
    - La autenticacion se realiza por tarea en BackgroundProcessor
    - WebhookPublisher se crea sin token inicial
    """
    # Código que se ejecuta ANTES de que la aplicación inicie
    configurar_logging()
    global logger, db_manager, business_service, webhook_publisher, background_processor
    logger = logging.getLogger(__name__)

    logger.info(" Worker de FastAPI iniciándose...")
    if not inicializar_configuracion():
        logger.critical(" FALLO EN CONFIGURACION")
        raise RuntimeError("Configuracion invalida")

    # Obtener valor UVT desde API externa (obligatorio para continuar)
    try:
        valor_uvt = await obtener_uvt_desde_api()
        establecer_uvt(valor_uvt)
    except RuntimeError as e:
        logger.critical(f"No se pudo obtener el valor UVT desde la API: {e}")
        raise

    # MODIFICADO v3.13.0: inicializar_database_manager() YA NO hace login
    try:
        db_manager, business_service = await inicializar_database_manager()

        if not db_manager:
            logger.critical(" DatabaseManager no inicializado")
            raise RuntimeError("Database manager requerido")

        logger.info(" Database manager inicializado")

    except Exception as e:
        logger.critical(f" ERROR EN STARTUP: {e}")
        logger.exception("Traceback:")
        raise

    # ELIMINADO v3.13.0: Ya NO extraer token desde auth_provider
    # El token se obtendrá por tarea en BackgroundProcessor

    # MODIFICADO v3.13.0: Crear WebhookPublisher SIN token inicial
    webhook_publisher = WebhookPublisher(
        auth_type="bearer",
        auth_token=None  # Token se actualizará por tarea
    )
    logger.info(" WebhookPublisher creado (sin token inicial)")

    background_processor = BackgroundProcessor(
        webhook_publisher=webhook_publisher,
        business_service=business_service,
        db_manager=db_manager
    )
    logger.info(" BackgroundProcessor inicializado")
    logger.info("  La autenticacion se ejecutara al inicio de cada tarea")

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
    background_tasks: BackgroundTasks,
    facturaId: int = Form(...),
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
    ENDPOINT PRINCIPAL - SISTEMA INTEGRADO v3.0 (PROCESAMIENTO ASINCRONO)

    Procesa facturas y calcula multiples impuestos en background:
    - RETENCION EN LA FUENTE (funcionalidad original)
    - ESTAMPILLA PRO UNIVERSIDAD NACIONAL (integrada)
    - CONTRIBUCION A OBRA PUBLICA 5% (integrada)
    - IVA Y RETEIVA (nueva funcionalidad)
    - PROCESAMIENTO PARALELO cuando multiples impuestos aplican
    - GUARDADO AUTOMATICO de JSONs en Results/
    - ENVIO A WEBHOOK al finalizar procesamiento

    FLUJO ASINCRONO v2.0:
    1. Recibe facturaId del cliente (identificador unico)
    2. Responde 200 INMEDIATO con facturaId confirmado
    3. Procesa en background (30-60 segundos)
    4. Al finalizar: hace POST a servicio externo con resultado y facturaId

    Args:
        background_tasks: Gestor de tareas en background de FastAPI
        facturaId: ID unico de la factura enviado por el cliente (entero obligatorio)
        archivos: Lista de archivos (facturas, RUTs, anexos, contratos)
        codigo_del_negocio: Codigo del negocio para consultar en base de datos
        proveedor: Nombre del proveedor que emite la factura
        ... (otros parametros del formulario)

    Returns:
        JSONResponse: Respuesta inmediata con facturaId confirmado y status "processing"
    """
    logger.info(f"ENDPOINT ASINCRONO v3.0 - Recibidos {len(archivos)} archivos")
    logger.info(f"Factura {facturaId} | Codigo negocio: {codigo_del_negocio} | Proveedor: {proveedor}")

    try:
        # =================================
        # FASE 1: LEER ARCHIVOS A BYTES
        # =================================
        # IMPORTANTE: UploadFile puede cerrarse antes que background task termine
        # Solucion: leer archivos a bytes ahora y pasar bytes al background
        archivos_data = []
        for archivo in archivos:
            contenido = await archivo.read()
            archivos_data.append({
                "filename": archivo.filename,
                "content_type": archivo.content_type,
                "content": contenido
            })
            await archivo.seek(0)  # Reset para posible uso posterior

        logger.info(f"Factura {facturaId}: Archivos leidos a bytes ({len(archivos_data)} archivos)")

        # =================================
        # FASE 2: PREPARAR PARAMETROS
        # =================================
        parametros = {
            "codigo_del_negocio": codigo_del_negocio,
            "proveedor": proveedor,
            "nit_proveedor": nit_proveedor,
            "estructura_contable": estructura_contable,
            "observaciones_tp": observaciones_tp,
            "genera_presupuesto": genera_presupuesto,
            "rubro": rubro,
            "centro_costos": centro_costos,
            "numero_contrato": numero_contrato,
            "valor_contrato_municipio": valor_contrato_municipio,
            "tipoMoneda": tipoMoneda
        }

        # =================================
        # FASE 3: AGREGAR TAREA BACKGROUND
        # =================================
        background_tasks.add_task(
            background_processor.procesar_factura_background,
            factura_id=facturaId,
            archivos_data=archivos_data,
            parametros=parametros
        )

        logger.info(f"Factura {facturaId}: Tarea agregada al background - Respondiendo inmediatamente")

        # =================================
        # FASE 4: RESPONDER 200 INMEDIATO
        # =================================
        return JSONResponse(
            status_code=200,
            content={
                "factura_id": facturaId,
                "status": "processing",
                "message": "Procesamiento iniciado en background",
                "timestamp": datetime.now().isoformat(),
                "archivos_recibidos": len(archivos),
                "codigo_negocio": codigo_del_negocio,
                "proveedor": proveedor
            }
        )

    except Exception as e:
        # Manejo de errores en la inicializacion del job
        error_msg = f"Error iniciando procesamiento asincrono: {str(e)}"
        logger.error(f"{error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")

        raise HTTPException(
            status_code=500,
            detail={
                "error": "Error iniciando procesamiento",
                "mensaje": "No se pudo iniciar el procesamiento en background",
                "detalle_tecnico": error_msg,
                "tipo": "INITIALIZATION_ERROR",
                "version": "3.0.0",
                "timestamp": datetime.now().isoformat()
            }
        )


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
