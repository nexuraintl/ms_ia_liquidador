"""
CLASIFICADOR DE TASA PRODEPORTE 
==========================

Módulo especializado para análisis de Tasa Prodeporte
usando Google Gemini AI.

"""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, TYPE_CHECKING
from pathlib import Path
import traceback

# Utilidades compartidas (NUEVO v3.0)
from utils.utils_archivos import obtener_nombre_archivo

# Google Gemini (nuevo SDK v2.0)
from google import genai

# FastAPI
from fastapi import UploadFile

# Pydantic
from pydantic import BaseModel

from prompts.prompt_tasa_prodeporte import PROMPT_ANALISIS_TASA_PRODEPORTE


logger = logging.getLogger(__name__)

# Type checking para evitar imports circulares
if TYPE_CHECKING:
    from .clasificador import ProcesadorGemini


class ClasificadorTasaProdeporte:
    
    def __init__ (self, 
                  procesador_gemini: 'ProcesadorGemini',
                  ):
        self.procesador_gemini = procesador_gemini
        logger.info("ClasificadorTasaProdeporte inicializado correctamente.") 
        
        

    async def analizar_tasa_prodeporte(
        self,
        documentos_clasificados: Dict[str, Dict],
        archivos_directos: list[UploadFile] = None,
        cache_archivos: Dict[str, bytes] = None,
        observaciones_tp: str = None
    ) -> Dict[str, Any]:
        """
        Analiza documentos para extracción de datos de Tasa Prodeporte usando Gemini AI.

        ARQUITECTURA: Separación IA-Validación
        - Gemini: SOLO extrae datos (factura, IVA, menciones, municipio)
        - Python: Realiza todas las validaciones y cálculos (en liquidador_TP.py)

        SRP: Solo coordina el análisis con Gemini para Tasa Prodeporte

        Args:
            documentos_clasificados: Diccionario de documentos clasificados
            archivos_directos: Lista de archivos directos para procesamiento multimodal
            cache_archivos: Cache de archivos para workers paralelos
            observaciones_tp: Observaciones del usuario (opcional)

        Returns:
            Dict con análisis de Gemini: {
                "factura_con_iva": float,
                "factura_sin_iva": float,
                "iva": float,
                "aplica_tasa_prodeporte": bool,
                "texto_mencion_tasa": str,
                "municipio_identificado": str,
                "texto_municipio": str
            }
        """
        logger.info("Analizando Tasa Prodeporte con Gemini AI...")

        # USAR CACHE SI ESTÁ DISPONIBLE (igual que estampillas_generales)
        archivos_directos = archivos_directos or []
        if cache_archivos:
            logger.info(f"Tasa Prodeporte usando cache de archivos: {len(cache_archivos)} archivos")
            archivos_directos = self.procesador_gemini._obtener_archivos_clonados_desde_cache(cache_archivos)
        elif archivos_directos:
            logger.info(f"Tasa Prodeporte usando archivos directos originales: {len(archivos_directos)} archivos")

        try:
            # Extraer textos de documentos clasificados
            factura_texto = ""
            anexos_texto = ""

            for nombre_archivo, datos_doc in documentos_clasificados.items():
                categoria = datos_doc.get("categoria", "")
                texto = datos_doc.get("texto", "")

                if categoria == "FACTURA":
                    factura_texto += f"\n=== {nombre_archivo} ===\n{texto}\n"
                    logger.info(f"Factura encontrada para análisis Tasa Prodeporte: {nombre_archivo}")
                elif categoria in ["ANEXO", "ANEXO_CONTRATO", "ANEXO CONCEPTO CONTRATO"]:
                    anexos_texto += f"\n=== {nombre_archivo} ===\n{texto}\n"

            # Normalizar textos vacíos
            factura_texto = factura_texto.strip() if factura_texto else "NO DISPONIBLE"
            anexos_texto = anexos_texto.strip() if anexos_texto else "NO DISPONIBLE"

            # Obtener nombres de archivos directos (compatible con cache)
            nombres_archivos_directos = []
            if archivos_directos:
                # Obtener nombres de archivos (NUEVO v3.0: soporta Files API)
                nombres_archivos_directos = [obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]

            # Generar prompt especializado


            prompt = PROMPT_ANALISIS_TASA_PRODEPORTE(
                factura_texto=factura_texto,
                anexos_texto=anexos_texto,
                observaciones_texto=observaciones_tp if observaciones_tp else "",
                nombres_archivos_directos=nombres_archivos_directos
            )

            logger.info(f"Prompt generado para Tasa Prodeporte ({len(prompt)} caracteres)")

            # Llamar a Gemini con soporte multimodal
            respuesta = await self.procesador_gemini._llamar_gemini_hibrido_factura(prompt, archivos_directos)
            logger.info(f"Respuesta análisis Tasa Prodeporte: {respuesta[:500]}...")

            # Limpiar respuesta
            respuesta_limpia = self.procesador_gemini._limpiar_respuesta_json(respuesta)

            # Parsear JSON
            analisis_dict = json.loads(respuesta_limpia)

            # Guardar respuesta de análisis en Results
            await self.procesador_gemini._guardar_respuesta("analisis_tasa_prodeporte.json", analisis_dict)

            # Validar estructura esperada
            campos_esperados = [
                "factura_con_iva", "factura_sin_iva", "iva",
                "aplica_tasa_prodeporte", "texto_mencion_tasa",
                "municipio_identificado", "texto_municipio"
            ]

            campos_faltantes = [campo for campo in campos_esperados if campo not in analisis_dict]

            if campos_faltantes:
                logger.warning(f"Campos faltantes en análisis Tasa Prodeporte: {campos_faltantes}")
                # Agregar campos faltantes con valores por defecto
                for campo in campos_faltantes:
                    if campo in ["factura_con_iva", "factura_sin_iva", "iva"]:
                        analisis_dict[campo] = 0.0
                    elif campo == "aplica_tasa_prodeporte":
                        analisis_dict[campo] = False
                    else:
                        analisis_dict[campo] = ""

            logger.info("Análisis Tasa Prodeporte completado:")
            logger.info(f"- Factura sin IVA: ${analisis_dict.get('factura_sin_iva', 0):,.2f}")
            logger.info(f"- Aplica Tasa Prodeporte: {analisis_dict.get('aplica_tasa_prodeporte', False)}")
            logger.info(f"- Municipio identificado: {analisis_dict.get('municipio_identificado', 'N/A')}")

            return analisis_dict

        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de Tasa Prodeporte: {e}")
            logger.error(f"Respuesta recibida: {respuesta_limpia[:500]}...")

            # Retornar estructura por defecto
            return {
                "factura_con_iva": 0.0,
                "factura_sin_iva": 0.0,
                "iva": 0.0,
                "aplica_tasa_prodeporte": False,
                "texto_mencion_tasa": "",
                "municipio_identificado": "",
                "texto_municipio": "",
                "error": f"Error parseando respuesta de IA: {str(e)}"
            }

        except Exception as e:
            logger.error(f"Error analizando Tasa Prodeporte: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Retornar estructura por defecto en caso de error
            return {
                "factura_con_iva": 0.0,
                "factura_sin_iva": 0.0,
                "iva": 0.0,
                "aplica_tasa_prodeporte": False,
                "texto_mencion_tasa": "",
                "municipio_identificado": "",
                "texto_municipio": "",
                "error": f"Error técnico: {str(e)}"
            }
