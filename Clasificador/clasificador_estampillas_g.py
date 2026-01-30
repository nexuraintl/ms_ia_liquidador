"""
Nodulo especializado para el analisis de estampillas generales 
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

# Google Gemini (nuevo SDK v2.0)
from google import genai

# FastAPI
from fastapi import UploadFile

# Pydantic
from pydantic import BaseModel



if TYPE_CHECKING:
    from .clasificador import ProcesadorGemini

from prompts.prompt_estampillas_generales import PROMPT_ANALISIS_ESTAMPILLAS_GENERALES

logger = logging.getLogger(__name__)


class ClasificadorEstampillasGenerales:
    def __init__(self,
                 procesador_gemini: 'ProcesadorGemini',
                 ):
        self.procesador_gemini = procesador_gemini
        logger.info(f"ClasificadorEstampillasGenerales inicializado correctamente.")
    


    async def analizar_estampillas_generales(self, documentos_clasificados: Dict[str, Dict], archivos_directos: list[UploadFile] = None, cache_archivos: Dict[str, bytes] = None) -> Dict[str, Any]:
        """
         Nueva funcionalidad: Análisis de 6 Estampillas Generales.
        
        Analiza documentos para identificar información de estampillas:
        - Procultura
        - Bienestar
        - Adulto Mayor
        - Prouniversidad Pedagógica
        - Francisco José de Caldas
        - Prodeporte
        
        Solo identificación, NO cálculos.
        
        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            
        Returns:
            Dict[str, Any]: Análisis completo de estampillas generales
            
        Raises:
            ValueError: Si hay error en el procesamiento
        """
        logger.info(" Analizando 6 estampillas generales con Gemini")
        
        #  USAR CACHE SI ESTÁ DISPONIBLE (igual que otras funciones)
        archivos_directos = archivos_directos or []
        if cache_archivos:
            logger.info(f" Estampillas generales usando cache de archivos: {len(cache_archivos)} archivos")
            archivos_directos = self.procesador_gemini._obtener_archivos_clonados_desde_cache(cache_archivos)
        elif archivos_directos:
            logger.info(f" Estampillas generales usando archivos directos originales: {len(archivos_directos)} archivos")
        
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
                    logger.info(f" Factura encontrada para análisis estampillas: {nombre_archivo}")
                elif info["categoria"] == "RUT":
                    rut_texto = info["texto"]
                    logger.info(f" RUT encontrado para análisis estampillas: {nombre_archivo}")
                elif info["categoria"] == "ANEXO":
                    anexos_texto += f"\n\n--- ANEXO: {nombre_archivo} ---\n{info['texto']}"
                elif info["categoria"] == "COTIZACION":
                    cotizaciones_texto += f"\n\n--- COTIZACIÓN: {nombre_archivo} ---\n{info['texto']}"
                elif info["categoria"] == "ANEXO CONCEPTO DE CONTRATO":
                    anexo_contrato += f"\n\n--- ANEXO CONCEPTO DE CONTRATO {nombre_archivo} ---\n{info['texto']}"
            
            #  VALIDACIÓN HÍBRIDA: Verificar que hay factura (en texto o archivo directo)
            hay_factura_texto = bool(factura_texto.strip()) if factura_texto else False
            
            #  OBTENER NOMBRES DE ARCHIVOS (compatible con cache)
            nombres_archivos_directos = []
            if archivos_directos:
                # Obtener nombres de archivos (NUEVO v3.0: soporta Files API)
                nombres_archivos_directos = [obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]
            
            posibles_facturas_directas = [nombre for nombre in nombres_archivos_directos if 'factura' in nombre.lower()]
            
            if not hay_factura_texto and not posibles_facturas_directas:
                raise ValueError("No se encontró una FACTURA en los documentos para análisis de estampillas")
            logger.info(f"Factura encontrada para análisis estampillas generales")
            
            # Generar prompt especializado de estampillas generales
            prompt = PROMPT_ANALISIS_ESTAMPILLAS_GENERALES(
                factura_texto=factura_texto,
                rut_texto=rut_texto,
                anexos_texto=anexos_texto,
                cotizaciones_texto=cotizaciones_texto,
                anexo_contrato=anexo_contrato,
                nombres_archivos_directos=nombres_archivos_directos
            )
            
            # Llamar a Gemini
            respuesta = await self.procesador_gemini._llamar_gemini_hibrido_factura(prompt,archivos_directos)
            logger.info(f" Respuesta análisis estampillas: {respuesta[:500]}...")
            
            # Limpiar respuesta
            respuesta_limpia = self.procesador_gemini._limpiar_respuesta_json(respuesta)
            
            # Parsear JSON
            resultado = json.loads(respuesta_limpia)
            
            # Guardar respuesta de análisis en Results
            await self.procesador_gemini._guardar_respuesta("analisis_estampillas_generales.json", resultado)
            
            # Validar estructura mínima requerida
            if "estampillas_generales" not in resultado:
                logger.warning(" Campo 'estampillas_generales' no encontrado en respuesta")
                resultado["estampillas_generales"] = self._obtener_estampillas_default()

            # Extraer información clave para logging (usar resumen interno si existe)
            estampillas_data = resultado.get("estampillas_generales", [])
            resumen_data = resultado.get("resumen_analisis", {})

            # Si no hay resumen en la respuesta de Gemini, generarlo solo para logging
            if not resumen_data:
                resumen_data = self._obtener_resumen_default(estampillas_data)

            total_identificadas = resumen_data.get("total_estampillas_identificadas", 0)
            completas = resumen_data.get("estampillas_completas", 0)
            incompletas = resumen_data.get("estampillas_incompletas", 0)

            logger.info(f" Análisis estampillas completado: {total_identificadas} identificadas, {completas} completas, {incompletas} incompletas")

            # Eliminar resumen_analisis del resultado final - solo se usa internamente para logging
            if "resumen_analisis" in resultado:
                del resultado["resumen_analisis"]

            return resultado
            
        except json.JSONDecodeError as e:
            logger.error(f" Error parseando JSON de análisis estampillas: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            return self._estampillas_fallback("Error parseando respuesta JSON de IA")
        except Exception as e:
            logger.error(f" Error en análisis de estampillas: {e}")
            return self._estampillas_fallback(str(e))
    
    def _obtener_estampillas_default(self) -> List[Dict[str, Any]]:
        """
        Obtiene estructura por defecto para las 6 estampillas generales.

        NOTA: Los estados se asignan después en el liquidador mediante validaciones Python.

        Returns:
            List con estructura por defecto de las 6 estampillas (sin estado)
        """
        estampillas_nombres = [
            "Procultura",
            "Bienestar",
            "Adulto Mayor",
            "Prouniversidad Pedagógica",
            "Francisco José de Caldas",
            "Prodeporte"
        ]

        return [
            {
                "nombre_estampilla": nombre,
                "porcentaje": 0.0,  # Default 0
                "valor_base": 0.0,   # Default 0
                "valor": 0.0,        # Default 0
                "texto_referencia": None,
                "observaciones": "Error en procesamiento - no se pudo analizar"  # Se mantiene para casos de error
            }
            for nombre in estampillas_nombres
        ]
    
    def _obtener_resumen_default(self, estampillas: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Genera resumen por defecto basado en lista de estampillas.
        
        Args:
            estampillas: Lista de estampillas procesadas
            
        Returns:
            Dict con resumen por defecto
        """
        total = len(estampillas)
        completas = sum(1 for e in estampillas if e.get("estado") == "preliquidado")
        incompletas = sum(1 for e in estampillas if e.get("estado") == "preliquidacion_sin_finalizar")
        no_aplican = sum(1 for e in estampillas if e.get("estado") == "no_aplica_impuesto")
        
        return {
            "total_estampillas_identificadas": completas + incompletas,
            "estampillas_completas": completas,
            "estampillas_incompletas": incompletas,
            "estampillas_no_aplican": no_aplican,
            "documentos_revisados": ["FACTURA", "ANEXOS", "ANEXO_CONTRATO", "RUT"]
        }
    
    def _estampillas_fallback(self, error_msg: str = "Error procesando estampillas") -> Dict[str, Any]:
        """
        Respuesta de emergencia cuando falla el procesamiento de estampillas.

        Args:
            error_msg: Mensaje de error

        Returns:
            Dict[str, Any]: Respuesta básica de estampillas
        """
        logger.warning(f"Usando fallback de estampillas: {error_msg}")

        estampillas_default = self._obtener_estampillas_default()

        return {
            "estampillas_generales": estampillas_default,
            "tipo_procesamiento": "ESTAMPILLAS_FALLBACK",
            "error": error_msg,
            "observaciones": [
                f"Error procesando estampillas: {error_msg}",
                "Por favor revise manualmente los documentos",
                "Verifique si los documentos contienen información de estampillas",
                "Busque menciones de: Procultura, Bienestar, Adulto Mayor, Universidad Pedagógica, Caldas, Prodeporte"
            ]
        }
