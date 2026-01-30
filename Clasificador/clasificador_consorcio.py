"""
CLASIFICADOR DE CONSORCIOS
===========================

Módulo especializado para análisis de Consorcios usando Google Gemini AI.
Separado del clasificador general siguiendo el principio SRP (Single Responsibility Principle).

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo análisis de consorcios
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

# Utilidades compartidas (NUEVO v3.0)
from utils.utils_archivos import obtener_nombre_archivo

# FastAPI
from fastapi import UploadFile

# Prompts consorcio
from prompts.prompt_retefuente import (
    PROMPT_EXTRACCION_CONSORCIO,
    PROMPT_MATCHING_CONCEPTOS
)

# Configuración de logging
logger = logging.getLogger(__name__)

# Type checking para evitar imports circulares
if TYPE_CHECKING:
    from .clasificador import ProcesadorGemini
    from .clasificador_retefuente import ClasificadorRetefuente


class ClasificadorConsorcio:
    """
    Clasificador especializado para análisis de Consorcios.

    Usa COMPOSICIÓN en lugar de herencia para mayor flexibilidad y testabilidad.
    Recibe instancias de ProcesadorGemini y ClasificadorRetefuente mediante inyección de dependencias.

    Responsabilidad única (SRP): Solo análisis de consorcios
    - Extracción de datos de consorciados
    - Matching de conceptos con base de datos
    - Validación de estructura de consorcio
    """

    def __init__(self,
                 procesador_gemini: 'ProcesadorGemini',
                 clasificador_retefuente: 'ClasificadorRetefuente'):
        """
        Constructor con inyección de dependencias.

        Args:
            procesador_gemini: Instancia de ProcesadorGemini para delegación de llamadas a Gemini
            clasificador_retefuente: Instancia de ClasificadorRetefuente para obtener conceptos
        """
        self.procesador_gemini = procesador_gemini
        self.clasificador_retefuente = clasificador_retefuente
        logger.info("ClasificadorConsorcio inicializado con inyección de dependencias")

    # ===============================
    # ANÁLISIS PRINCIPAL DE CONSORCIO
    # ===============================

    async def analizar_consorcio(self,
                                  documentos_clasificados: Dict[str, Dict],
                                  es_facturacion_extranjera: bool = False,
                                  archivos_directos: List[UploadFile] = None,
                                  cache_archivos: Dict[str, bytes] = None,
                                  proveedor: str = None) -> Dict[str, Any]:
        """
        Llamada a Gemini especializada para analizar consorcios CON CACHE.

        ARQUITECTURA v3.0: Dos llamadas separadas
        1. Extracción de datos crudos (consorciados, conceptos literales)
        2. Matching de conceptos con base de datos

        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            es_facturacion_extranjera: Si es facturación extranjera (usa prompts especializados)
            archivos_directos: Lista de archivos directos (para compatibilidad)
            cache_archivos: Cache de archivos para workers paralelos
            proveedor: Nombre del proveedor/consorcio (v3.0)

        Returns:
            Dict[str, Any]: Análisis completo del consorcio en formato compatible

        Raises:
            ValueError: Si no se encuentra factura o hay error en procesamiento
        """
        logger.info("Analizando CONSORCIO con IA")

        # USAR CACHE SI ESTÁ DISPONIBLE
        archivos_directos = archivos_directos or []
        if cache_archivos:
            logger.info(f"Consorcio usando cache de archivos: {len(cache_archivos)} archivos")
            archivos_directos = self.procesador_gemini._obtener_archivos_clonados_desde_cache(cache_archivos)
        elif archivos_directos:
            logger.info(f"Consorcio usando archivos directos originales: {len(archivos_directos)} archivos")

        # Extraer documentos por categoría (mismo proceso que factura normal)
        factura_texto = ""
        rut_texto = ""
        anexos_texto = ""
        cotizaciones_texto = ""
        anexo_contrato = ""

        for nombre_archivo, info in documentos_clasificados.items():
            if info["categoria"] == "FACTURA":
                factura_texto = info["texto"]
                logger.info(f"Factura de consorcio encontrada: {nombre_archivo}")
            elif info["categoria"] == "RUT":
                rut_texto = info["texto"]
                logger.info(f"RUT encontrado: {nombre_archivo}")
            elif info["categoria"] == "ANEXO":
                anexos_texto += f"\n\n--- ANEXO: {nombre_archivo} ---\n{info['texto']}"
            elif info["categoria"] == "COTIZACION":
                cotizaciones_texto += f"\n\n--- COTIZACIÓN: {nombre_archivo} ---\n{info['texto']}"
            elif info["categoria"] == "ANEXO CONCEPTO DE CONTRATO":
                anexo_contrato += f"\n\n--- ANEXO CONCEPTO DE CONTRATO {nombre_archivo} ---\n{info['texto']}"

        hay_factura_texto = bool(factura_texto.strip()) if factura_texto else False
        nombres_archivos_directos = [obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]
        posibles_facturas_directas = [nombre for nombre in nombres_archivos_directos if 'factura' in nombre.lower()]

        if not factura_texto and not posibles_facturas_directas:
            raise ValueError("No se encontró una FACTURA en los documentos del consorcio")
        logger.info("Se identificó correctamente la factura del consorcio")

        # Nombres de archivos ya fueron obtenidos arriba (línea 140) usando obtener_nombre_archivo

        try:
            # NUEVO FLUJO v3.0.10: Dos llamadas separadas para mayor precision
            logger.info("=== INICIANDO ANALISIS DE CONSORCIO CON DOS LLAMADAS ===")

            # ==========================================
            # LLAMADA 1: EXTRACCION DE DATOS CRUDOS
            # ==========================================
            logger.info("LLAMADA 1: Extrayendo datos crudos del consorcio...")

            prompt_extraccion = PROMPT_EXTRACCION_CONSORCIO(
                factura_texto, rut_texto, anexos_texto,
                cotizaciones_texto, anexo_contrato,
                nombres_archivos_directos=nombres_archivos_directos,
                proveedor=proveedor
            )

            respuesta_extraccion = await self.procesador_gemini._llamar_gemini_hibrido_factura(
                prompt_extraccion,
                archivos_directos=archivos_directos
            )
            logger.info(f"Respuesta extraccion recibida (primeros 200 chars): {respuesta_extraccion[:200]}...")

            # Limpiar y parsear respuesta de extraccion
            respuesta_extraccion_limpia = self.procesador_gemini._limpiar_respuesta_json(respuesta_extraccion)

            try:
                datos_extraidos = json.loads(respuesta_extraccion_limpia)
            except json.JSONDecodeError as first_error:
                logger.warning(f"JSON de extraccion malformado, intentando reparar: {first_error}")
                respuesta_reparada = self.procesador_gemini._reparar_json_malformado(respuesta_extraccion_limpia)
                datos_extraidos = json.loads(respuesta_reparada)

            # Guardar resultado de extraccion
            logger.info(f"Extraccion exitosa: {len(datos_extraidos.get('consorciados', []))} consorciados identificados")
            logger.info(f"Conceptos literales extraidos: {len(datos_extraidos.get('conceptos_literales', []))}")

            # ==========================================
            # LLAMADA 2: MATCHING DE CONCEPTOS
            # ==========================================
            conceptos_literales = datos_extraidos.get("conceptos_literales", [])

            if not conceptos_literales:
                logger.warning("No se extrajeron conceptos literales, usando concepto no identificado")
                conceptos_mapeados = {
                    "conceptos_mapeados": [{
                        "nombre_concepto": "CONCEPTO_NO_IDENTIFICADO",
                        "concepto": "CONCEPTO_NO_IDENTIFICADO",
                        "concepto_index": 0,
                        "justificacion": "No se identificaron conceptos en la primera llamada"
                    }]
                }
            else:
                logger.info("LLAMADA 2: Haciendo matching de conceptos con base de datos...")

                # DIP: Usar ClasificadorRetefuente para obtener conceptos
                conceptos_dict = self.clasificador_retefuente._obtener_conceptos_retefuente()
                prompt_matching = PROMPT_MATCHING_CONCEPTOS(conceptos_literales, conceptos_dict)

                respuesta_matching = await self.procesador_gemini._llamar_gemini(
                    prompt_matching,
                    usar_modelo_consorcio=False  # Matching es mas simple, no necesita modelo grande
                )
                logger.info(f"Respuesta matching recibida (primeros 200 chars): {respuesta_matching[:200]}...")

                # Limpiar y parsear respuesta de matching
                respuesta_matching_limpia = self.procesador_gemini._limpiar_respuesta_json(respuesta_matching)

                try:
                    conceptos_mapeados = json.loads(respuesta_matching_limpia)
                except json.JSONDecodeError as matching_error:
                    logger.warning(f"JSON de matching malformado, intentando reparar: {matching_error}")
                    respuesta_reparada = self.procesador_gemini._reparar_json_malformado(respuesta_matching_limpia)
                    conceptos_mapeados = json.loads(respuesta_reparada)


                logger.info(f"Matching exitoso: {len(conceptos_mapeados.get('conceptos_mapeados', []))} conceptos mapeados")

            # ==========================================
            # MERGE: COMBINAR RESULTADOS
            # ==========================================
            logger.info("MERGE: Combinando resultados de ambas llamadas...")

            # Crear estructura final compatible con el formato actual
            conceptos_identificados = []
            conceptos_mapeados_list = conceptos_mapeados.get("conceptos_mapeados", [])

            for concepto_mapeado in conceptos_mapeados_list:
                # Buscar base_gravable del concepto literal correspondiente
                nombre_concepto = concepto_mapeado.get("nombre_concepto", "")
                base_gravable = 0.0

                for concepto_literal in conceptos_literales:
                    if concepto_literal.get("nombre_concepto") == nombre_concepto:
                        base_gravable = concepto_literal.get("base_gravable", 0.0)
                        break

                # Construir objeto en formato esperado
                # NOTA: tarifa_retencion NO se incluye aqui porque se obtiene de la BD
                # usando concepto_index en liquidador_consorcios.py
                concepto_identificado = {
                    "nombre_concepto": nombre_concepto,
                    "concepto": concepto_mapeado.get("concepto", "CONCEPTO_NO_IDENTIFICADO"),
                    "concepto_index": concepto_mapeado.get("concepto_index", 0),
                    "base_gravable": base_gravable
                }
                conceptos_identificados.append(concepto_identificado)

            # Construir resultado final con misma estructura que antes
            resultado = {
                "es_consorcio": datos_extraidos.get("es_consorcio", True),
                "nombre_consorcio": datos_extraidos.get("nombre_consorcio", ""),
                "conceptos_identificados": conceptos_identificados,
                "consorciados": datos_extraidos.get("consorciados", []),
                "valor_total": datos_extraidos.get("valor_total", 0.0),
                "observaciones": datos_extraidos.get("observaciones", [])
            }

            # Agregar observacion sobre el nuevo metodo
            if "observaciones" not in resultado:
                resultado["observaciones"] = []
            resultado["observaciones"].append("Analisis realizado con metodo de dos llamadas (extraccion + matching)")

            # Guardar resultado final consolidado
            await self.procesador_gemini._guardar_respuesta("analisis_consorcio.json", resultado)

            # Validar cantidad de consorciados
            if 'consorciados' in resultado and len(resultado['consorciados']) > 20:
                logger.warning(f"Consorcio muy grande ({len(resultado['consorciados'])} consorciados), puede requerir procesamiento especial")

            # Log final
            logger.info(f"=== ANALISIS COMPLETO ===")
            logger.info(f"Consorciados identificados: {len(resultado.get('consorciados', []))}")
            logger.info(f"Conceptos mapeados: {len(conceptos_identificados)}")
            logger.info(f"Valor total: ${resultado.get('valor_total', 0):,.2f}")
            logger.info("Datos extraidos por IA - Validaciones y calculos seran realizados por liquidador_consorcios.py")

            return resultado

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de consorcio (dos llamadas): {e}")
            logger.error("JSON malformado en extraccion o matching")
            return self._consorcio_fallback()
        except Exception as e:
            logger.error(f"Error en analisis de consorcio (dos llamadas): {e}")
            import traceback
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            return self._consorcio_fallback(str(e))

    # ===============================
    # MÉTODO FALLBACK
    # ===============================

    def _consorcio_fallback(self, error_msg: str = "Error procesando consorcio") -> Dict[str, Any]:
        """
        Respuesta de emergencia cuando falla el procesamiento de consorcio.
        NUEVA ESTRUCTURA v3.1.2: Compatible con liquidador_consorcios.py

        Args:
            error_msg: Mensaje de error

        Returns:
            Dict[str, Any]: Respuesta básica de consorcio compatible con nuevo liquidador
        """
        logger.warning(f"Usando fallback de consorcio: {error_msg}")

        return {
            "es_consorcio": True,
            "nombre_consorcio": "Consorcio no identificado",
            "tipo_entidad": "CONSORCIO",
            "conceptos_identificados": [
                {
                    "nombre_concepto": "CONCEPTO_NO_IDENTIFICADO",
                    "concepto": "CONCEPTO_NO_IDENTIFICADO",
                    "tarifa_retencion": 0.0,
                    "base_gravable": 0.0
                }
            ],
            "consorciados": [],
            "validacion_porcentajes": {
                "suma_total": 0.0,
                "es_valido": False
            },
            "valor_total_factura": 0.0,
            "observaciones": [
                f"Error procesando consorcio: {error_msg}",
                "Por favor revise manualmente los documentos",
                "Verifique porcentajes de participación en anexos"
            ],
            "tipo_procesamiento": "CONSORCIO_FALLBACK",
            "error": error_msg
        }
