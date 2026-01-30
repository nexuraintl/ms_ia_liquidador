"""modulo especializado para el analisis de estampilla pro universidad nacional y obre publica
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
from prompts.prompt_estampilla_obra_publica import PROMPT_ANALISIS_OBRA_PUBLICA_ESTAMPILLA_INTEGRADO

logger = logging.getLogger(__name__)

class ClasificadorObraUni:
    
    def __init__ (self, 
                  procesador_gemini: 'ProcesadorGemini',
                  ):
        self.procesador_gemini = procesador_gemini
        logger.info("ClasificadorObraUni inicializado correctamente.")
        
        
    async def analizar_estampilla(self, documentos_clasificados: Dict[str, Dict], archivos_directos: List[str] = None, cache_archivos: Dict[str, bytes] = None) -> Dict[str, Any]:
        """
        Análisis integrado de impuestos especiales (estampilla + obra pública) Multimodal CON CACHE.
        
        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            archivos_directos: Lista de archivos directos (para compatibilidad)
            cache_archivos: Cache de archivos para workers paralelos
            
        Returns:
            Dict[str, Any]: Análisis completo integrado
            
        Raises:
            ValueError: Si hay error en el procesamiento
        """
        logger.info(" Analizando IMPUESTOS ESPECIALES INTEGRADOS con Gemini")
        logger.info(" Impuestos: ESTAMPILLA_UNIVERSIDAD + CONTRIBUCION_OBRA_PUBLICA")
        
        #  USAR CACHE SI ESTÁ DISPONIBLE
        archivos_directos = archivos_directos or []
        if cache_archivos:
            logger.info(f"Estampillas usando cache de archivos: {len(cache_archivos)} archivos")
            archivos_directos = self.procesador_gemini._obtener_archivos_clonados_desde_cache(cache_archivos)
        elif archivos_directos:
            logger.info(f" Estampillas usando archivos directos originales: {len(archivos_directos)} archivos")
        
        # Importar liquidador integrado
        try:
            from Liquidador.liquidador_estampilla import LiquidadorEstampilla
            liquidador = LiquidadorEstampilla()
        except ImportError:
            logger.error("No se pudo importar LiquidadorEstampilla")
            raise ValueError("Error cargando liquidador de impuestos especiales")
        
        # Combinar todo el texto de los documentos
        texto_completo = ""
        for nombre_archivo, info in documentos_clasificados.items():
            texto_completo += f"\n\n--- {info['categoria']}: {nombre_archivo} ---\n{info['texto']}"
        
        logger.info(f" Analizando impuestos especiales con TEXTO COMPLETO: {len(texto_completo):,} caracteres (sin límites)")
        
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
                elif info["categoria"] == "RUT":
                    rut_texto = info["texto"]
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
        
            if not hay_factura_texto and not posibles_facturas_directas:
                raise ValueError("No se encontró una FACTURA en los documentos (ni texto ni archivo directo)")
            
            # Crear lista de nombres de archivos directos para el prompt (NUEVO v3.0: soporta Files API)
            nombres_archivos_directos = [obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]


            # Modo multimodal
            prompt = liquidador.obtener_prompt_integrado_desde_clasificador(
                factura_texto=factura_texto,
                rut_texto=rut_texto,
                anexos_texto=anexos_texto,
                cotizaciones_texto=cotizaciones_texto,
                anexo_contrato=anexo_contrato,
                nit_administrativo="", nombres_archivos_directos=nombres_archivos_directos # Se puede obtener del contexto si es necesario
            )
            
            # Llamar a Gemini
            respuesta = await self.procesador_gemini._llamar_gemini_hibrido_factura(prompt, archivos_directos)
            logger.info(f"Respuesta análisis impuestos especiales: {respuesta[:500]}...")
            
            # Limpiar respuesta
            respuesta_limpia = self.procesador_gemini._limpiar_respuesta_json(respuesta)
            # Parsear JSON
            resultado = json.loads(respuesta_limpia)

            # Guardar respuesta de análisis en Results
            await self.procesador_gemini._guardar_respuesta("analisis_impuestos_especiales.json", resultado)

            #  ARQUITECTURA v3.0: Retornar JSON simple de extracción y clasificación
            # El liquidador hará todas las validaciones manuales con Python
            logger.info(" Análisis de Gemini completado - Retornando extracción y clasificación para validaciones Python")
            logger.info(f" Estructura: extraccion={bool(resultado.get('extraccion'))}, clasificacion={bool(resultado.get('clasificacion'))}")

            # Validar que la estructura sea la correcta
            if "extraccion" not in resultado or "clasificacion" not in resultado:
                logger.warning(" Respuesta de Gemini no tiene estructura esperada v3.0")
                logger.warning(f"Claves encontradas: {list(resultado.keys())}")

            return resultado
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de impuestos especiales: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            raise ValueError(f"Error parseando respuesta para impuestos especiales: {str(e)}")
        except Exception as e:
            logger.error(f"Error en análisis de impuestos especiales: {e}")
            raise ValueError(f"Error analizando impuestos especiales: {str(e)}")
       