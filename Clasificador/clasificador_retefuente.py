"""
CLASIFICADOR DE RETEFUENTE
==========================

Módulo especializado para análisis de Retención en la Fuente usando Google Gemini AI.
Separado del clasificador general siguiendo el principio SRP (Single Responsibility Principle).

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo análisis de retefuente
- DIP: Inyección de dependencias - usa composición con ProcesadorGemini
- OCP: Abierto para extensión - fácil agregar nuevas funciones

Arquitectura: Composición > Herencia
- NO hereda de ProcesadorGemini (evita acoplamiento)
- Recibe instancia de ProcesadorGemini (inyección de dependencias)
- Delega llamadas a Gemini al procesador general

Autor: Sistema Preliquidador
Versión: 3.1.0
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, TYPE_CHECKING
from pathlib import Path

# Google Gemini (nuevo SDK v2.0)
from google import genai

# FastAPI
from fastapi import UploadFile

# Pydantic
from pydantic import BaseModel

# Prompts retefuente
from prompts.prompt_retefuente import (
    PROMPT_ANALISIS_FACTURA,
    PROMPT_ANALISIS_ART_383,
    PROMPT_ANALISIS_FACTURA_EXTRANJERA
)

# Modelos de dominio
from modelos import (
    ConceptoIdentificado,
    NaturalezaTercero,
    ConceptoIdentificadoArt383,
    CondicionesArticulo383,
    InteresesVivienda,
    DependientesEconomicos,
    MedicinaPrepagada,
    AFCInfo,
    PlanillaSeguridadSocial,
    DeduccionesArticulo383,
    InformacionArticulo383,
    AnalisisFactura,
)

# Configuración de logging
logger = logging.getLogger(__name__)

# Utilidades compartidas (NUEVO v3.0)
from utils.utils_archivos import obtener_nombre_archivo as _obtener_nombre_archivo

# Type checking para evitar imports circulares
if TYPE_CHECKING:
    from .clasificador import ProcesadorGemini


class ClasificadorRetefuente:
    """
    Clasificador especializado para Retención en la Fuente.

    Usa COMPOSICIÓN en lugar de herencia para mayor flexibilidad y testabilidad.
    Recibe una instancia de ProcesadorGemini mediante inyección de dependencias.

    Responsabilidad única (SRP): Solo análisis de retefuente
    - Facturación nacional
    - Facturación extranjera
    - Artículo 383 (personas naturales)
    """

    def __init__(self,
                 procesador_gemini: 'ProcesadorGemini',
                 estructura_contable: int = None,
                 db_manager = None):
        """
        Constructor con inyección de dependencias.

        Args:
            procesador_gemini: Instancia de ProcesadorGemini para delegación de llamadas a Gemini
            estructura_contable: ID de estructura contable (opcional)
            db_manager: Gestor de base de datos (opcional)
        """
        self.procesador_gemini = procesador_gemini
        self.estructura_contable = estructura_contable
        self.db_manager = db_manager
        logger.info(f"ClasificadorRetefuente inicializado con estructura_contable={estructura_contable}")

    # ===============================
    # FUNCIONES PRINCIPALES
    # ===============================

    async def analizar_factura(
        self,
        documentos_clasificados: Dict[str, Dict],
        es_facturacion_extranjera: bool = False,
        archivos_directos: List[UploadFile] = None,
        cache_archivos: Dict[str, bytes] = None,
        proveedor: str = None
    ) -> AnalisisFactura:
        """
        ANÁLISIS HÍBRIDO MULTIMODAL: Analizar factura con archivos directos + textos preprocesados.

        FUNCIONALIDAD HÍBRIDA CON CACHE:
        - Archivos directos (PDFs/imágenes): Enviados nativamente a Gemini
        - Textos preprocesados: Documentos ya extraidos localmente
        - Cache para workers: Solución a problemas de concurrencia en workers paralelos
        - Combinación inteligente: Una sola llamada con contenido mixto

        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            es_facturacion_extranjera: Si es facturación extranjera (usa prompts especializados)
            archivos_directos: Lista de archivos para envío directo a Gemini (PDFs/imágenes)
            cache_archivos: Cache de archivos para workers paralelos (evita problemas de concurrencia)
            proveedor: Nombre del proveedor que emite la factura (v3.0)

        Returns:
            AnalisisFactura: Análisis completo de la factura

        Raises:
            ValueError: Si no se encuentra factura o hay error en procesamiento
        """
        # LOGGING HÍBRIDO CON CACHE: Identificar estrategia de procesamiento
        archivos_directos = archivos_directos or []
        cache_archivos = cache_archivos or {}

        # USAR CACHE SI ESTÁ DISPONIBLE (para workers paralelos)
        if cache_archivos:
            logger.info(f"Usando cache de archivos para análisis (workers paralelos): {len(cache_archivos)} archivos")
            archivos_directos = self.procesador_gemini._obtener_archivos_clonados_desde_cache(cache_archivos)
            total_archivos_directos = len(archivos_directos)
        else:
            total_archivos_directos = len(archivos_directos)
            logger.info(f"Usando archivos directos originales (sin cache): {total_archivos_directos} archivos")

        total_textos_preprocesados = len(documentos_clasificados)

        if total_archivos_directos > 0:
            logger.info(f"Analizando factura HÍBRIDO: {total_archivos_directos} directos + {total_textos_preprocesados} preprocesados")
        else:
            logger.info(f"Analizando factura TRADICIONAL: {total_textos_preprocesados} textos preprocesados")

        # Extraer documentos por categoría
        factura_texto = ""
        rut_texto = ""
        anexos_texto = ""
        cotizaciones_texto = ""
        anexo_contrato = ""

        for nombre_archivo, info in documentos_clasificados.items():
            if info["categoria"] == "FACTURA":
                factura_texto = info["texto"]
                logger.info(f"Factura encontrada: {nombre_archivo}")
                logger.info(f"Extracto factura: {factura_texto[:30]}")
            elif info["categoria"] == "RUT":
                rut_texto = info["texto"]
                logger.info(f"RUT encontrado: {nombre_archivo}")
                logger.info(f"Extracto RUT: {rut_texto[:30]}")
            elif info["categoria"] == "ANEXO":
                anexos_texto += f"\n\n--- ANEXO: {nombre_archivo} ---\n{info['texto']}"
                logger.info(f"Anexo encontrado: {nombre_archivo}")
                logger.info(f"Extracto anexo: {info['texto'][:30]}")
            elif info["categoria"] == "COTIZACION":
                cotizaciones_texto += f"\n\n--- COTIZACIÓN: {nombre_archivo} ---\n{info['texto']}"
                logger.info(f"Cotización encontrada: {nombre_archivo}")
                logger.info(f"Extracto cotización: {info['texto'][:30]}")
            elif info["categoria"] == "ANEXO CONCEPTO DE CONTRATO":
                anexo_contrato += f"\n\n--- ANEXO CONCEPTO DE CONTRATO {nombre_archivo} ---\n{info['texto']}"
                logger.info(f"Anexo concepto de contrato encontrado: {nombre_archivo}")
                logger.info(f"Extracto anexo concepto de contrato: {info['texto'][:30]}")

        # VALIDACIÓN HÍBRIDA: Verificar que hay factura (en texto o archivo directo)
        hay_factura_texto = bool(factura_texto.strip()) if factura_texto else False
        nombres_archivos_directos = [_obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]
        posibles_facturas_directas = [nombre for nombre in nombres_archivos_directos if 'factura' in nombre.lower()]

        if not hay_factura_texto and not posibles_facturas_directas:
            raise ValueError("No se encontró una FACTURA en los documentos (ni texto ni archivo directo)")

        try:
            # DECIDIR ESTRATEGIA: HÍBRIDO vs TRADICIONAL
            usar_hibrido = total_archivos_directos > 0 or bool(cache_archivos)

            if usar_hibrido:
                logger.info("Usando análisis HÍBRIDO con archivos directos + textos preprocesados")

                # CREAR LISTA DE NOMBRES DE ARCHIVOS DIRECTOS PARA PROMPT (NUEVO v3.0: soporta Files API)
                nombres_archivos_directos = [_obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]

                # GENERAR PROMPT HÍBRIDO
                if es_facturacion_extranjera:
                    logger.info("Prompt híbrido para facturación extranjera (v3.0 - SOLO IDENTIFICACIÓN)")
                    conceptos_extranjeros_simplificado = self._obtener_conceptos_extranjeros_simplificado()

                    prompt = PROMPT_ANALISIS_FACTURA_EXTRANJERA(
                        factura_texto, rut_texto, anexos_texto,
                        cotizaciones_texto, anexo_contrato,
                        conceptos_extranjeros_simplificado,
                        nombres_archivos_directos,
                        proveedor
                    )
                else:
                    logger.info("Prompt híbrido para facturación nacional")
                    conceptos_dict = self._obtener_conceptos_retefuente()

                    prompt = PROMPT_ANALISIS_FACTURA(
                        factura_texto, rut_texto, anexos_texto,
                        cotizaciones_texto, anexo_contrato, conceptos_dict,
                        nombres_archivos_directos,
                        proveedor
                    )

                # LLAMAR A GEMINI HÍBRIDO (delegación)
                respuesta = await self.procesador_gemini._llamar_gemini_hibrido_factura(prompt, archivos_directos)

            else:
                # FLUJO TRADICIONAL (solo textos preprocesados)
                logger.info("Usando análisis TRADICIONAL con solo textos preprocesados")

                if es_facturacion_extranjera:
                    logger.info("Usando prompt especializado para facturación extranjera (v3.0 - SOLO IDENTIFICACIÓN)")
                    conceptos_extranjeros_simplificado = self._obtener_conceptos_extranjeros_simplificado()

                    prompt = PROMPT_ANALISIS_FACTURA_EXTRANJERA(
                        factura_texto, rut_texto, anexos_texto,
                        cotizaciones_texto, anexo_contrato,
                        conceptos_extranjeros_simplificado,
                        None,
                        proveedor
                    )
                else:
                    logger.info("Usando prompt para facturación nacional")
                    conceptos_dict = self._obtener_conceptos_retefuente()

                    prompt = PROMPT_ANALISIS_FACTURA(
                        factura_texto, rut_texto, anexos_texto,
                        cotizaciones_texto, anexo_contrato, conceptos_dict,
                        None,
                        proveedor
                    )

                # LLAMAR A GEMINI TRADICIONAL (delegación)
                respuesta = await self.procesador_gemini._llamar_gemini(prompt)

            # LOG DE RESPUESTA SEGÚN ESTRATEGIA
            if usar_hibrido:
                logger.info(f"Respuesta análisis HÍBRIDO: {len(respuesta):,} caracteres")
            else:
                logger.info(f"Respuesta análisis tradicional: {len(respuesta):,} caracteres")

            # Log de muestra para debugging (primeros 500 caracteres)
            logger.info(f"Muestra de respuesta: {respuesta[:500]}...")

            # Limpiar respuesta si viene con texto extra (delegación)
            respuesta_limpia = self.procesador_gemini._limpiar_respuesta_json(respuesta)

            # Parsear JSON
            resultado = json.loads(respuesta_limpia)

            # Guardar respuesta de análisis en Results (delegación)
            await self.procesador_gemini._guardar_respuesta("analisis_factura.json", resultado)

            # NUEVO: ANÁLISIS SEPARADO DEL ARTÍCULO 383 PARA PERSONAS NATURALES
            if (resultado.get("naturaleza_tercero") and
                resultado["naturaleza_tercero"].get("es_persona_natural") == True):

                logger.info("PERSONA NATURAL detectada - Iniciando análisis separado del Artículo 383")

                try:
                    # Segunda llamada a Gemini con prompt específico de Art 383
                    # CORRECCIÓN: Convertir objetos ConceptoIdentificado a diccionarios para evitar error de serialización JSON
                    conceptos_identificados_objetos = [ConceptoIdentificado(**c) for c in resultado.get("conceptos_identificados", [])]
                    conceptos_identificados_dict = [concepto.dict() for concepto in conceptos_identificados_objetos] if conceptos_identificados_objetos else []

                    logger.info(f"Pasando {len(conceptos_identificados_dict)} conceptos como diccionarios al Art 383")

                    analisis_art383 = await self._analizar_articulo_383(
                        factura_texto, rut_texto, anexos_texto,
                        cotizaciones_texto, anexo_contrato, archivos_directos, cache_archivos, conceptos_identificados_dict
                    )

                    # Integrar resultado del Art 383 en el resultado principal
                    resultado["articulo_383"] = analisis_art383

                    # Guardar análisis combinado
                    resultado_combinado = {
                        "timestamp": datetime.now().isoformat(),
                        "analisis_retefuente": resultado,
                        "analisis_art383_separado": analisis_art383,
                        "persona_natural_detectada": True
                    }
                    await self.procesador_gemini._guardar_respuesta("analisis_factura_con_art383.json", resultado_combinado)

                    logger.info(f"Análisis Art 383 completado: aplica={analisis_art383.get('aplica', False)}")

                except Exception as e:
                    logger.error(f"Error en análisis Art 383: {e}")
                    # Si falla el análisis del Art 383, continuar sin él
                    resultado["articulo_383"] = {
                        "aplica": False,
                        "error": str(e),
                        "observaciones": ["Error procesando Artículo 383 - usar tarifa convencional"]
                    }
            else:
                # No es persona natural, no se analiza Art 383
                resultado["articulo_383"] = {
                    "aplica": False,
                    "razon": "No es persona natural o no se pudo determinar"
                }
                logger.info("NO es persona natural - Artículo 383 no aplica")

            # CORRECCIÓN v3.0: Para facturación extranjera, agregar naturaleza_tercero como None si no existe
            if es_facturacion_extranjera and "naturaleza_tercero" not in resultado:
                resultado["naturaleza_tercero"] = None
                logger.info("Facturación extranjera: naturaleza_tercero establecido en None")

            # Crear objeto AnalisisFactura
            analisis = AnalisisFactura(**resultado)
            logger.info(f"Análisis exitoso: {len(analisis.conceptos_identificados)} conceptos identificados")

            return analisis

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de análisis: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            # Fallback: crear análisis básico
            return self._analisis_fallback()
        except Exception as e:
            logger.error(f"Error en análisis de factura: {e}")
            raise ValueError(f"Error analizando factura: {str(e)}")

    # ===============================
    # ANÁLISIS ARTÍCULO 383
    # ===============================

    async def _analizar_articulo_383(
        self,
        factura_texto: str,
        rut_texto: str,
        anexos_texto: str,
        cotizaciones_texto: str,
        anexo_contrato: str,
        archivos_directos: List[UploadFile] = None,
        cache_archivos: Dict[str, bytes] = None,
        conceptos_identificados: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        NUEVA FUNCIÓN: Análisis separado del Artículo 383 para personas naturales.

        Esta función realiza una segunda llamada a Gemini específicamente para analizar
        si aplica el Artículo 383 del Estatuto Tributario con tarifas progresivas.

        CORREGIDO: Ahora acepta conceptos como diccionarios para evitar errores de serialización JSON.

        Args:
            factura_texto: Texto extraído de la factura principal
            rut_texto: Texto del RUT (si está disponible)
            anexos_texto: Texto de anexos adicionales
            cotizaciones_texto: Texto de cotizaciones
            anexo_contrato: Texto del anexo de concepto de contrato
            archivos_directos: Lista de archivos para envío directo a Gemini
            cache_archivos: Cache de archivos para workers paralelos
            conceptos_identificados: Lista de conceptos como diccionarios (no objetos Pydantic)

        Returns:
            Dict[str, Any]: Análisis completo del Artículo 383

        Raises:
            ValueError: Si hay error en el procesamiento con Gemini
        """
        logger.info("Iniciando análisis separado del Artículo 383")

        try:
            # USAR CACHE SI ESTÁ DISPONIBLE (para workers paralelos)
            archivos_directos = archivos_directos or []
            if cache_archivos:
                logger.info(f"Art 383 usando cache de archivos: {len(cache_archivos)} archivos")
                archivos_directos = self.procesador_gemini._obtener_archivos_clonados_desde_cache(cache_archivos)
            elif archivos_directos:
                logger.info(f"Art 383 usando archivos directos originales: {len(archivos_directos)} archivos")

            # CREAR LISTA DE NOMBRES DE ARCHIVOS DIRECTOS PARA PROMPT (NUEVO v3.0: soporta Files API)
            nombres_archivos_directos = [_obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]

            # Generar prompt específico para Art 383
            prompt_art383 = PROMPT_ANALISIS_ART_383(
                factura_texto, rut_texto, anexos_texto,
                cotizaciones_texto, anexo_contrato, nombres_archivos_directos, conceptos_identificados
            )

            logger.info("Llamando a Gemini para análisis específico del Artículo 383")

            # Decidir estrategia: HÍBRIDO vs TRADICIONAL
            usar_hibrido = len(archivos_directos) > 0 or bool(cache_archivos)

            if usar_hibrido:
                logger.info("Usando análisis HÍBRIDO para Art 383")
                respuesta = await self.procesador_gemini._llamar_gemini_hibrido_factura(prompt_art383, archivos_directos)
            else:
                logger.info("Usando análisis TRADICIONAL para Art 383")
                respuesta = await self.procesador_gemini._llamar_gemini(prompt_art383)

            logger.info(f"Respuesta Art 383 recibida: {len(respuesta):,} caracteres")

            # Limpiar respuesta si viene con texto extra (delegación)
            respuesta_limpia = self.procesador_gemini._limpiar_respuesta_json(respuesta)

            # Parsear JSON
            resultado_art383 = json.loads(respuesta_limpia)

            # Guardar respuesta de análisis Art 383 por separado (delegación)
            await self.procesador_gemini._guardar_respuesta("analisis_art383_separado.json", resultado_art383)

            # Extraer el diccionario del Art 383
            resultado_art383 = resultado_art383["articulo_383"]

            # Validar estructura mínima del resultado
            campos_requeridos = ["condiciones_cumplidas", "deducciones_identificadas"]
            for campo in campos_requeridos:
                if campo not in resultado_art383:
                    logger.warning(f"Campo '{campo}' no encontrado en respuesta Art 383")
                    resultado_art383[campo] = self._obtener_campo_art383_default(campo)

            # Extraer información clave para logging
            condiciones = resultado_art383.get("condiciones_cumplidas", {})
            deducciones = resultado_art383.get("deducciones_identificadas", {})
            logger.info(f"Condiciones cumplidas: {condiciones}")
            logger.info(f"Deducciones identificadas: {deducciones}")

            return resultado_art383

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de Art 383: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            return self._art383_fallback("Error parseando respuesta JSON de Gemini")
        except Exception as e:
            logger.error(f"Error en análisis Art 383: {e}")
            return self._art383_fallback(str(e))

    def _obtener_campo_art383_default(self, campo: str) -> Dict[str, Any]:
        """
        Obtiene valores por defecto para campos faltantes en análisis del Art 383.

        Args:
            campo: Nombre del campo faltante

        Returns:
            Dict con estructura por defecto
        """
        defaults = {
            "aplica": False,
            "condiciones_cumplidas": {
                "es_persona_natural": False,
                "concepto_aplicable": False,
                "es_primer_pago": False,
                "planilla_seguridad_social": False,
                "cuenta_cobro": False
            },
            "deducciones_identificadas": {
                "intereses_vivienda": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                },
                "dependientes_economicos": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                },
                "medicina_prepagada": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                },
                "rentas_exentas": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                }
            }
        }

        return defaults.get(campo, {})

    def _art383_fallback(self, error_msg: str = "Error procesando Art 383") -> Dict[str, Any]:
        """
        Respuesta de emergencia cuando falla el procesamiento del Art 383.

        Args:
            error_msg: Mensaje de error

        Returns:
            Dict[str, Any]: Respuesta básica del Art 383
        """
        logger.warning(f"Usando fallback de Art 383: {error_msg}")

        return {
            "aplica": False,
            "condiciones_cumplidas": {
                "es_persona_natural": False,
                "concepto_aplicable": False,
                "es_primer_pago": False,
                "planilla_seguridad_social": False,
                "cuenta_cobro": False
            },
            "deducciones_identificadas": {
                "intereses_vivienda": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                },
                "dependientes_economicos": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                },
                "medicina_prepagada": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                },
                "rentas_exentas": {
                    "valor": 0.0,
                    "tiene_soporte": False,
                    "limite_aplicable": 0.0
                }
            },
            "error": error_msg,
            "observaciones": [
                f"Error procesando Artículo 383: {error_msg}",
                "Se aplicará tarifa convencional",
                "Revise manualmente si aplica Art 383"
            ]
        }

    # ===============================
    # FALLBACK GENERAL
    # ===============================

    def _analisis_fallback(self) -> AnalisisFactura:
        """
        Análisis de emergencia cuando falla Gemini.

        Returns:
            AnalisisFactura: Análisis básico de fallback
        """
        logger.warning("Usando análisis fallback - Gemini no pudo procesar")

        return AnalisisFactura(
            conceptos_identificados=[
                ConceptoIdentificado(
                    concepto="CONCEPTO_NO_IDENTIFICADO",
                    base_gravable=None,
                    concepto_index=None
                )
            ],
            naturaleza_tercero=NaturalezaTercero(
                es_responsable_iva=None
            ),
            es_facturacion_exterior=False,
            valor_total=None,
            observaciones=[
                "Error procesando con Gemini - No se pudo extraer información",
                "Por favor revise manualmente los documentos",
                "IMPORTANTE: Verifique si el tercero es responsable de IVA en el RUT"
            ]
        )

    # ===============================
    # OBTENCIÓN DE CONCEPTOS NACIONALES
    # ===============================

    def _obtener_conceptos_retefuente(self) -> dict:
        """
        Obtiene los conceptos de retefuente desde la base de datos.

        Returns:
            dict: Conceptos formateados para Gemini con estructura {descripcion_concepto: index}
        """
        try:
            # Verificar que tenemos db_manager y estructura_contable
            if not self.db_manager or self.estructura_contable is None:
                logger.warning("db_manager o estructura_contable no configurados, usando fallback")
                return self._conceptos_hardcodeados()

            # Consultar BD para obtener conceptos
            logger.info(f"Consultando conceptos desde BD para estructura_contable={self.estructura_contable}")
            resultado = self.db_manager.obtener_conceptos_retefuente(self.estructura_contable)

            if not resultado['success']:
                logger.warning(f"No se encontraron conceptos en BD: {resultado['message']}")
                return self._conceptos_hardcodeados()

            # Formatear para Gemini: {descripcion_concepto: index}
            conceptos_dict = {}
            for concepto in resultado['data']:
                descripcion = concepto['descripcion_concepto']
                index = concepto['index']
                conceptos_dict[descripcion] = index

            logger.info(f"CONCEPTOS_RETEFUENTE obtenidos desde BD: {len(conceptos_dict)} conceptos")
            return conceptos_dict

        except Exception as e:
            logger.error(f"Error obteniendo conceptos desde BD: {e}")
            return self._conceptos_hardcodeados()

    def _conceptos_hardcodeados(self) -> dict:
        """
        Conceptos de emergencia si no se puede acceder a la BD.

        Returns:
            dict: Conceptos básicos hardcodeados con formato {descripcion: index}
        """
        return {
            "Servicios generales (declarantes)": 1,
            "Honorarios y comisiones por servicios (declarantes)": 2,
            "Compras": 3,
            "Arrendamiento de bienes inmuebles": 4,
            "Arrendamiento de bienes muebles": 5
        }

    def _obtener_conceptos_completos(self) -> dict:
        """
        Obtiene los conceptos completos de retefuente con bases mínimas y tarifas.

        Returns:
            dict: Conceptos con estructura completa {concepto: {base_pesos, tarifa_retencion}}
        """
        try:
            # Importar directamente CONCEPTOS_RETEFUENTE desde config.py
            from config import CONCEPTOS_RETEFUENTE
            logger.info(f"CONCEPTOS_RETEFUENTE importados exitosamente desde config.py: {len(CONCEPTOS_RETEFUENTE)} conceptos")
            return CONCEPTOS_RETEFUENTE

        except ImportError as e:
            logger.warning(f"No se pudo importar desde config.py: {e}")
            logger.warning("Usando conceptos completos hardcodeados como fallback")
            return self._conceptos_completos_hardcodeados()
        except Exception as e:
            logger.error(f"Error obteniendo conceptos completos: {e}")
            return self._conceptos_completos_hardcodeados()

    def _conceptos_completos_hardcodeados(self) -> dict:
        """
        Conceptos completos de emergencia con bases mínimas y tarifas.

        Returns:
            dict: Conceptos básicos con estructura completa
        """
        return {
            "Servicios generales (declarantes)": {
                "base_pesos": 498000,
                "tarifa_retencion": 0.04
            },
            "Honorarios y comisiones por servicios (declarantes)": {
                "base_pesos": 2490000,
                "tarifa_retencion": 0.11
            },
            "Servicios de construcción y urbanización (declarantes)": {
                "base_pesos": 1490000,
                "tarifa_retencion": 0.01
            }
        }

    # ===============================
    # FACTURACIÓN EXTRANJERA
    # ===============================

    def _obtener_conceptos_extranjeros(self) -> dict:
        """
        Obtiene los conceptos de retención para facturación extranjera.

        Returns:
            dict: Conceptos extranjeros con tarifas normal y convenio
        """
        try:
            from config import obtener_conceptos_extranjeros
            return obtener_conceptos_extranjeros()
        except ImportError:
            logger.warning("No se pudo importar conceptos extranjeros, usando hardcodeados")
            return self._conceptos_extranjeros_hardcodeados()
        except Exception as e:
            logger.error(f"Error obteniendo conceptos extranjeros: {e}")
            return self._conceptos_extranjeros_hardcodeados()

    def _obtener_conceptos_extranjeros_simplificado(self) -> dict:
        """
        Obtiene conceptos extranjeros SIMPLIFICADOS (solo index y nombre) desde la BD.

        v3.0: Gemini SOLO identifica, NO calcula. Solo necesita {index: nombre}.

        Returns:
            dict: {index: nombre_concepto} para identificación en Gemini
        """
        try:
            if not self.db_manager:
                logger.warning("DatabaseManager no disponible, usando conceptos hardcodeados simplificados")
                return self._conceptos_extranjeros_simplificados_hardcodeados()

            # Obtener conceptos desde BD
            resultado = self.db_manager.obtener_conceptos_extranjeros()

            if not resultado.get("success", False):
                logger.error(f"Error consultando conceptos extranjeros: {resultado.get('error')}")
                return self._conceptos_extranjeros_simplificados_hardcodeados()

            # Crear diccionario simplificado: {index: nombre_concepto}
            conceptos_simplificados = {}
            for concepto in resultado.get("data", []):
                index = concepto.get("index")
                nombre = concepto.get("nombre_concepto")
                if index is not None and nombre:
                    conceptos_simplificados[index] = nombre

            logger.info(f"Conceptos extranjeros simplificados obtenidos de BD: {len(conceptos_simplificados)}")
            return conceptos_simplificados

        except Exception as e:
            logger.error(f"Error obteniendo conceptos simplificados: {e}")
            return self._conceptos_extranjeros_simplificados_hardcodeados()

    def _conceptos_extranjeros_simplificados_hardcodeados(self) -> dict:
        """
        Fallback: Conceptos extranjeros simplificados hardcodeados.

        Returns:
            dict: {index: nombre_concepto}
        """
        logger.warning("Usando conceptos extranjeros simplificados hardcodeados")
        return {
            1: "Dividendos y participaciones",
            2: "Intereses",
            3: "Regalías",
            4: "Consultorías, servicios técnicos y de asistencia técnica",
            5: "Arrendamiento de equipos industriales, comerciales o científicos",
            6: "Honorarios",
            7: "Compensación por servicios personales",
            8: "Otros ingresos",
        }

    def _obtener_paises_convenio(self) -> list:
        """
        Obtiene la lista de países con convenio de doble tributación.

        Returns:
            list: Lista de países con convenio
        """
        try:
            from config import obtener_paises_con_convenio
            return obtener_paises_con_convenio()
        except ImportError:
            logger.warning("No se pudo importar países con convenio, usando hardcodeados")
            return self._paises_convenio_hardcodeados()
        except Exception as e:
            logger.error(f"Error obteniendo países con convenio: {e}")
            return self._paises_convenio_hardcodeados()

    def _obtener_preguntas_fuente_nacional(self) -> list:
        """
        Obtiene las preguntas para determinar fuente nacional.

        Returns:
            list: Lista de preguntas para validar fuente nacional
        """
        try:
            from config import obtener_preguntas_fuente_nacional
            return obtener_preguntas_fuente_nacional()
        except ImportError:
            logger.warning("No se pudo importar preguntas fuente nacional, usando hardcodeadas")
            return self._preguntas_fuente_hardcodeadas()
        except Exception as e:
            logger.error(f"Error obteniendo preguntas fuente nacional: {e}")
            return self._preguntas_fuente_hardcodeadas()

    def _conceptos_extranjeros_hardcodeados(self) -> dict:
        """
        Conceptos extranjeros de emergencia.

        Returns:
            dict: Conceptos básicos extranjeros
        """
        return {
            "Pagos por servicios al exterior": {
                "base_pesos": 0,
                "tarifa_normal": 0.20,
                "tarifa_convenio": 0.10
            }
        }

    def _paises_convenio_hardcodeados(self) -> list:
        """
        Países con convenio de emergencia.

        Returns:
            list: Lista básica de países
        """
        return ["España", "Francia", "Italia", "Chile", "México", "Perú", "Ecuador", "Bolivia"]

    def _preguntas_fuente_hardcodeadas(self) -> list:
        """
        Preguntas de fuente nacional de emergencia.

        Returns:
            list: Lista básica de preguntas
        """
        return [
            "¿El servicio tiene uso o beneficio económico en Colombia?",
            "¿La actividad se ejecutó en Colombia?",
            "¿Es asistencia técnica usada en Colombia?",
            "¿El bien está ubicado en Colombia?"
        ]
