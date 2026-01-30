"""
Modulo especializado ara el analisis de iva y reteiva con Google Gemini AI."""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, TYPE_CHECKING
from pathlib import Path

# Utilidades compartidas (NUEVO v3.0)
from utils.utils_archivos import obtener_nombre_archivo

# Google Gemini (nuevo SDK v2.0)
from google import genai

# FastAPI
from fastapi import UploadFile

# Pydantic
from pydantic import BaseModel

from prompts.prompt_iva import PROMPT_ANALISIS_IVA


logger = logging.getLogger(__name__)

# Type checking para evitar imports circulares
if TYPE_CHECKING:
    from .clasificador import ProcesadorGemini






class ClasificadorIva:
    def __init__ (self, 
                  procesador_gemini: 'ProcesadorGemini',
                  ):
        self.procesador_gemini = procesador_gemini
        
        logger.info("Clasificador Iva inicializado correctamente.")
    
    async def analizar_iva(self, documentos_clasificados: Dict[str, Dict], archivos_directos: List[UploadFile] = None, cache_archivos: Dict[str, bytes] = None) -> Dict[str, Any]:
        
        """
        Nueva funcionalidad: Análisis especializado de IVA y ReteIVA CON CACHE.
        
        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            archivos_directos: Lista de archivos directos (para compatibilidad)
            cache_archivos: Cache de archivos para workers paralelos
            
            
        Returns:
            Dict[str, Any]: Análisis completo de IVA y ReteIVA
            
        Raises:
            ValueError: Si hay error en el procesamiento
        """
        logger.info(" Analizando IVA y ReteIVA con Gemini")
        
        #  USAR CACHE SI ESTÁ DISPONIBLE
        archivos_directos = archivos_directos or []
        if cache_archivos:
            logger.info(f" IVA usando cache de archivos: {len(cache_archivos)} archivos")
            archivos_directos = self.procesador_gemini._obtener_archivos_clonados_desde_cache(cache_archivos)
        elif archivos_directos:
            logger.info(f" IVA usando archivos directos originales: {len(archivos_directos)} archivos")
        
        try:
            # Extraer documentos por categoría
            factura_texto = ""
            rut_texto = ""
            anexos_texto = ""
            cotizaciones_texto = ""
            anexo_contrato = ""
            
            for nombre_archivo, info in documentos_clasificados.items():
                if info["categoria"] == "FACTURA":
                    factura_texto = info["texto"]
                    logger.info(f" Factura encontrada para análisis IVA: {nombre_archivo}")
                elif info["categoria"] == "RUT":
                    rut_texto = info["texto"]
                    logger.info(f" RUT encontrado para análisis IVA: {nombre_archivo}")
                elif info["categoria"] == "ANEXO":
                    anexos_texto += f"\n\n--- ANEXO: {nombre_archivo} ---\n{info['texto']}"
                elif info["categoria"] == "COTIZACION":
                    cotizaciones_texto += f"\n\n--- COTIZACIÓN: {nombre_archivo} ---\n{info['texto']}"
                elif info["categoria"] == "ANEXO CONCEPTO DE CONTRATO":
                    anexo_contrato += f"\n\n--- ANEXO CONCEPTO DE CONTRATO {nombre_archivo} ---\n{info['texto']}"
            
                    #  VALIDACIÓN HÍBRIDA: Verificar que hay factura (en texto o archivo directo)

            hay_factura_texto = bool(factura_texto.strip()) if factura_texto else False
            nombres_archivos_directos = [obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]
            posibles_facturas_directas = [nombre for nombre in nombres_archivos_directos if 'factura' in nombre.lower()]
            
            if not factura_texto and not posibles_facturas_directas:
                raise ValueError("No se encontró una FACTURA en los documentos para análisis de IVA")

            logger.info("Factura encontrada para analisis IVA")
            # Nombres de archivos ya fueron obtenidos arriba (línea 98) usando obtener_nombre_archivo

            # Generar prompt especializado de IVA
            prompt = PROMPT_ANALISIS_IVA(
                factura_texto=factura_texto,
                rut_texto=rut_texto,
                anexos_texto=anexos_texto,
                cotizaciones_texto=cotizaciones_texto,
                anexo_contrato=anexo_contrato,
                nombres_archivos_directos=nombres_archivos_directos
            )
            
            # Llamar a Gemini
            respuesta = await self.procesador_gemini._llamar_gemini_hibrido_factura(prompt, archivos_directos)
            logger.info(f"Respuesta análisis IVA: {respuesta[:500]}...")
            
            # Limpiar respuesta
            respuesta_limpia = self.procesador_gemini._limpiar_respuesta_json(respuesta)
            
            # Parsear JSON
            resultado = json.loads(respuesta_limpia)
            
            # Guardar respuesta de análisis en Results
            await self.procesador_gemini._guardar_respuesta("analisis_iva_reteiva.json", resultado)
            
            # Validar estructura NUEVA del PROMPT_ANALISIS_IVA (v2.0 - SOLID)
            campos_requeridos = ["extraccion_rut", "extraccion_factura", "clasificacion_concepto", "validaciones"]
            campos_faltantes = [campo for campo in campos_requeridos if campo not in resultado]

            if campos_faltantes:
                logger.warning(f" Campos faltantes en respuesta de IVA: {campos_faltantes}")
                # Agregar campos por defecto para los faltantes
                for campo in campos_faltantes:
                    resultado[campo] = self._obtener_campo_iva_default_v2(campo)

            # Extraer información clave para logging (NUEVA ESTRUCTURA)
            extraccion_factura = resultado.get("extraccion_factura", {})
            extraccion_rut = resultado.get("extraccion_rut", {})
            validaciones = resultado.get("validaciones", {})

            valor_iva = extraccion_factura.get("valor_iva", 0.0)
            es_responsable_iva = extraccion_rut.get("es_responsable_iva")
            rut_disponible = validaciones.get("rut_disponible", False)

            logger.info(" Análisis IVA completado (v2.0 SOLID):")
            logger.info(f"   - Valor IVA: ${valor_iva:,.2f}")
            logger.info(f"   - Responsable IVA: {es_responsable_iva}")
            logger.info(f"   - RUT disponible: {rut_disponible}")

            return resultado
            
        except json.JSONDecodeError as e:
            logger.error(f" Error parseando JSON de análisis IVA: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            return self._iva_fallback("Error parseando respuesta JSON de IA")
        except Exception as e:
            logger.error(f" Error en análisis de IVA: {e}")
            return self._iva_fallback(str(e))
    

    def _obtener_campo_iva_default_v2(self, campo: str) -> Dict[str, Any]:
        """
        Obtiene valores por defecto para campos faltantes en análisis de IVA v2.0 (SOLID).

        Nueva estructura del PROMPT_ANALISIS_IVA refactorizado.

        Args:
            campo: Nombre del campo faltante

        Returns:
            Dict con estructura por defecto v2.0
        """
        defaults = {
            "extraccion_rut": {
                "es_responsable_iva": None,
                "texto_evidencia": "No disponible"
            },
            "extraccion_factura": {
                "valor_iva": 0.0,
                "porcentaje_iva": 0,
                "valor_subtotal_sin_iva": 0.0,
                "valor_total_con_iva": 0.0,
                "concepto_facturado": "No identificado"
            },
            "clasificacion_concepto": {
                "categoria": "no_clasificado",
                "justificacion": "Campo faltante en respuesta de IA",
                "coincidencia_encontrada": ""
            },
            "validaciones": {
                "rut_disponible": False
            }
        }

        return defaults.get(campo, {})

    def _iva_fallback(self, error_msg: str = "Error procesando IVA") -> Dict[str, Any]:
        """
        Respuesta de emergencia cuando falla el procesamiento de IVA v2.0 (SOLID).

        Retorna estructura compatible con PROMPT_ANALISIS_IVA refactorizado.

        Args:
            error_msg: Mensaje de error

        Returns:
            Dict[str, Any]: Respuesta básica de IVA con nueva estructura v2.0
        """
        logger.warning(f"Usando fallback de IVA v2.0 (SOLID): {error_msg}")

        return {
            "extraccion_rut": {
                "es_responsable_iva": None,
                "texto_evidencia": f"Error en procesamiento: {error_msg}"
            },
            "extraccion_factura": {
                "valor_iva": 0.0,
                "porcentaje_iva": 0,
                "valor_subtotal_sin_iva": 0.0,
                "valor_total_con_iva": 0.0,
                "concepto_facturado": "Error en identificación"
            },
            "clasificacion_concepto": {
                "categoria": "error",
                "justificacion": f"Error en análisis: {error_msg}",
                "coincidencia_encontrada": ""
            },
            "validaciones": {
                "rut_disponible": False
            },
            "tipo_procesamiento": "IVA_FALLBACK_v2.0",
            "error": error_msg,
            "observaciones": [
                f"Error procesando IVA: {error_msg}",
                "Por favor revise manualmente los documentos",
                "Verifique responsabilidad de IVA en el RUT",
                "Valide conceptos facturados y aplicabilidad de IVA"
            ]
        }
    
    
    
    
        
        