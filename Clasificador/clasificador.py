"""
PROCESADOR GEMINI - CLASIFICADOR DE DOCUMENTOS
==============================================

Maneja todas las interacciones con Google Gemini AI para:
1. Clasificar documentos en categorías (FACTURA, RUT, COTIZACION, ANEXO, etc.)
2. Analizar facturas y extraer información para retención en la fuente

Autor: Miguel Angel Jaramillo Durango
"""

import os
import json
import asyncio
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Tuple
from pathlib import Path

# Google Gemini (nuevo SDK v2.0)
from google import genai
from google.genai import types
from .gemini_files_manager import GeminiFilesManager

# Modelos de datos (importar desde main)
from pydantic import BaseModel
from typing import List, Optional

# Importación adicional para archivos directos y manejo de errores HTTP
from fastapi import UploadFile, HTTPException

#  NUEVAS IMPORTACIONES PARA VALIDACIÓN ROBUSTA DE PDF
import PyPDF2
from io import BytesIO

# Configuración de logging
logger = logging.getLogger(__name__)

# Importar prompts clasificador general
from prompts.prompt_clasificador import PROMPT_CLASIFICACION

# Importar prompts retefuente
from prompts.prompt_retefuente import (
    PROMPT_ANALISIS_FACTURA,
    PROMPT_EXTRACCION_CONSORCIO,  # NUEVO: Primera llamada extraccion
    PROMPT_MATCHING_CONCEPTOS,    # NUEVO: Segunda llamada matching
    PROMPT_ANALISIS_FACTURA_EXTRANJERA
)

# Importar prompts especializados
from prompts.prompt_iva import PROMPT_ANALISIS_IVA
from prompts.prompt_estampillas_generales import PROMPT_ANALISIS_ESTAMPILLAS_GENERALES

# ===============================
# IMPORTAR MODELOS DESDE DOMAIN LAYER (Clean Architecture - SRP)
# ===============================

from modelos import (
    # Modelos para Retencion General
    ConceptoIdentificado,
    NaturalezaTercero,

    # Modelos para Articulo 383 - Deducciones Personales
    ConceptoIdentificadoArt383,
    CondicionesArticulo383,
    InteresesVivienda,
    DependientesEconomicos,
    MedicinaPrepagada,
    AFCInfo,
    PlanillaSeguridadSocial,
    DeduccionesArticulo383,
    InformacionArticulo383,

    # Modelos Agregadores - Entrada/Salida
    AnalisisFactura,
)

# ===============================
# PROCESADOR GEMINI
# ===============================

class ProcesadorGemini:
    """Maneja las llamadas a la API de Gemini para clasificación y análisis"""
    
    def __init__(self, estructura_contable: int = None, db_manager = None):
        """
        Inicializa el procesador con configuración de Gemini

        Args:
            estructura_contable: Código de estructura contable para consultas de conceptos
            db_manager: Instancia de DatabaseManager para consultas a BD
        """
        # Cargar API key desde variables de entorno
        from dotenv import load_dotenv
        load_dotenv()

        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no está configurada en el archivo .env")

        # NUEVO SDK v2.0: Inicializar cliente
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = 'gemini-2.5-flash-preview-09-2025'

        # NUEVO: Inicializar Files Manager (SRP: gestión de archivos)
        self.files_manager = GeminiFilesManager(api_key=self.api_key)

        # Configuración de generación estándar
        self.generation_config = {
            'temperature': 0.4,
            'max_output_tokens': 65536,
            'candidate_count': 1
        }

        # Configuración especial para consorcios (más tokens)
        self.generation_config_consorcio = {
            'temperature': 0.7,
            'max_output_tokens': 65536,
            'candidate_count': 1
        }

        # Nuevos parámetros para consultas BD
        self.estructura_contable = estructura_contable
        self.db_manager = db_manager

        logger.info("ProcesadorGemini inicializado correctamente con nuevo SDK v2.0 + Files API")

        # ARQUITECTURA SOLID: Inyección de dependencias para clasificadores especializados
        # Inicializar después de que self esté completamente configurado
        self.clasificador_retefuente = None
        self.clasificador_consorcio = None
        self._inicializar_clasificadores_especializados()

    def _inicializar_clasificadores_especializados(self):
        """
        Inicializa clasificadores especializados con inyección de dependencias.
        Siguiendo principio DIP (Dependency Inversion Principle).
        """
        try:
            # Importar clasificadores especializados
            from .clasificador_retefuente import ClasificadorRetefuente
            from .clasificador_consorcio import ClasificadorConsorcio
            from .clasificador_tp import ClasificadorTasaProdeporte
            from .clasificador_estampillas_g import ClasificadorEstampillasGenerales
            from .clasificador_iva  import ClasificadorIva
            
            from .clasificador_obra_uni import ClasificadorObraUni
            # Crear instancia de ClasificadorRetefuente
            self.clasificador_retefuente = ClasificadorRetefuente(
                procesador_gemini=self,
                estructura_contable=self.estructura_contable,
                db_manager=self.db_manager
            )
            logger.info("ClasificadorRetefuente inicializado correctamente")

            # Crear instancia de ClasificadorConsorcio (depende de ClasificadorRetefuente)
            self.clasificador_consorcio = ClasificadorConsorcio(
                procesador_gemini=self,
                clasificador_retefuente=self.clasificador_retefuente
            )
            logger.info("ClasificadorConsorcio inicializado correctamente")
            
            # crear instancia de ClasificadorTasaProdeporte
            self.clasificador_tasa_prodeporte = ClasificadorTasaProdeporte(procesador_gemini=self)
            
            logger.info("ClasificadorTasaProdeporte inicializado correctamente")
            
            self.clasificador_estampillas_generales = ClasificadorEstampillasGenerales(procesador_gemini=self)
            
            logger.info("ClasificadorEstampillasGenerales inicializado correctamente")
            
            self.clasificador_iva = ClasificadorIva(procesador_gemini=self)
            logger.info("Clasificador IVA inicializado correctamente")
            
            self.clasificador_obra_uni = ClasificadorObraUni(procesador_gemini=self)
            
            logger.info("ClasificadorObraUni inicializado correctamente")
            

        except Exception as e:
            logger.error(f"Error inicializando clasificadores especializados: {e}")
            raise

    async def clasificar_documentos(
        self,
        textos_archivos_o_directos = None,  #  COMPATIBILIDAD TOTAL: Acepta cualquier tipo
        archivos_directos: List[UploadFile] = None,  #  NUEVO: Archivos directos
        textos_preprocesados: Dict[str, str] = None,  #  NUEVO: Textos preprocesados
        proveedor: str = None  #  v3.0: Nombre del proveedor para mejor identificacion
    ) -> Tuple[Dict[str, str], bool, bool, bool]:
        """
         FUNCIÓN HÍBRIDA CON COMPATIBILIDAD: Clasificación con archivos directos + textos preprocesados.
        
        MODOS DE USO:
         MODO LEGACY: clasificar_documentos(textos_archivos) - Funciona como antes
         MODO HÍBRIDO: clasificar_documentos(archivos_directos=[], textos_preprocesados={})
        
        ENFOQUE HÍBRIDO IMPLEMENTADO:
         PDFs e Imágenes → Enviados directamente a Gemini (multimodal)
         Excel/Email/Word → Procesados localmente y enviados como texto
         Límite: Máximo 20 archivos directos
         Mantener prompts existentes con modificaciones mínimas
        
        Args:
            textos_archivos: [LEGACY] Diccionario {nombre_archivo: texto_extraido} - Compatibilidad
            archivos_directos: [NUEVO] Lista de archivos para envío directo (PDFs e imágenes)
            textos_preprocesados: [NUEVO] Diccionario {nombre_archivo: texto_extraido} para archivos preprocesados
            
        Returns:
            Tuple[Dict[str, str], bool, bool]: (clasificacion_documentos, es_consorcio, es_facturacion_extranjera)
            
        Raises:
            ValueError: Si hay error en el procesamiento con Gemini
            HTTPException: Si se excede límite de archivos directos
        """
        #  DETECCIÓN AUTOMÁTICA DE MODO MEJORADA
        if textos_archivos_o_directos is not None:
            # DETECTAR TIPO DE ENTRADA
            if isinstance(textos_archivos_o_directos, dict):
                # MODO LEGACY: Dict[str, str] -  original de main.py
                logger.info(f" MODO LEGACY detectado: {len(textos_archivos_o_directos)} textos recibidos")
                logger.info(" Convirtiendo a modo híbrido interno...")
                
                archivos_directos = []
                textos_preprocesados = textos_archivos_o_directos
                
            elif isinstance(textos_archivos_o_directos, list):
                # MODO HÍBRIDO: List[UploadFile] - nueva signatura híbrida
                logger.info(f" MODO HÍBRIDO detectado: {len(textos_archivos_o_directos)} archivos directos")
                
                archivos_directos = textos_archivos_o_directos
                textos_preprocesados = textos_preprocesados or {}
                
            else:
                # MODO DESCONOCIDO: Error
                tipo_recibido = type(textos_archivos_o_directos).__name__
                error_msg = f"Tipo de entrada no soportado: {tipo_recibido}. Se esperaba Dict[str, str] (legacy) o List[UploadFile] (híbrido)"
                logger.error(f"{error_msg}")
                raise ValueError(error_msg)
        
        else:
            # MODO HÍBRIDO EXPLÍCITO: usar parámetros específicos
            logger.info(" MODO HÍBRIDO EXPLÍCITO detectado")
            archivos_directos = archivos_directos or []
            textos_preprocesados = textos_preprocesados or {}
        
        # Continuar con lógica híbrida usando variables normalizadas
        archivos_directos = archivos_directos or []
        textos_preprocesados = textos_preprocesados or {}        
        total_archivos = len(archivos_directos) + len(textos_preprocesados)
        
        logger.info(f" CLASIFICACIÓN HÍBRIDA iniciada:")
        logger.info(f" Archivos directos (PDFs/Imágenes): {len(archivos_directos)}")
        logger.info(f"Textos preprocesados (Excel/Email/Word): {len(textos_preprocesados)}")
        logger.info(f" Total archivos a clasificar: {total_archivos}")
        
        #  VALIDACIÓN: Límite de archivos directos (20)
        if len(archivos_directos) > 20:
            error_msg = f"Límite excedido: {len(archivos_directos)} archivos directos (máximo 20)"
            logger.error(f" {error_msg}")
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Demasiados archivos directos",
                    "detalle": error_msg,
                    "limite_maximo": 20,
                    "archivos_recibidos": len(archivos_directos),
                    "sugerencia": "Reduzca el número de archivos directos"
                }
            )

        #  VALIDACIÓN: Al menos un archivo debe estar presente
        if total_archivos == 0:
            error_msg = "No se recibieron archivos para clasificar"
            logger.error(f" {error_msg}")
            raise ValueError(error_msg)
        
        try:
            # PASO 1: Crear lista de nombres de archivos directos para el prompt (NUEVO v3.0: soporta Files API)
            from utils.utils_archivos import obtener_nombre_archivo
            nombres_archivos_directos = [obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]
            
            logger.info(f" Archivos directos para Gemini: {nombres_archivos_directos}")
            logger.info(f" Textos preprocesados: {list(textos_preprocesados.keys())}")

            # PASO 2: Generar prompt híbrido usando función modificada (v3.0: con proveedor)
            prompt = PROMPT_CLASIFICACION(textos_preprocesados, nombres_archivos_directos, proveedor)

            # PASO 3: NUEVO v3.0 - Subir archivos a Files API (no bytes inline)
            contents = [prompt]
            uploaded_files_refs = []

            if archivos_directos:
                logger.info(f"Subiendo {len(archivos_directos)} archivos a Files API...")

                for i, archivo in enumerate(archivos_directos):
                    try:
                        # Subir archivo a Files API usando GeminiFilesManager
                        file_result = await self.files_manager.upload_file(
                            archivo=archivo,
                            wait_for_active=True,
                            timeout_seconds=300
                        )

                        uploaded_files_refs.append(file_result)

                        nombre_archivo = file_result.display_name
                        logger.info(f"Archivo subido a Files API: {nombre_archivo} -> {file_result.name}")

                    except Exception as e:
                        logger.error(f"Error subiendo archivo {i+1} a Files API: {e}")
                        logger.warning(f"Fallback: intentando envío inline para archivo {i+1}")

                        # Fallback: si Files API falla, enviar como bytes inline
                        try:
                            if hasattr(archivo, 'seek'):
                                await archivo.seek(0)
                            if hasattr(archivo, 'read'):
                                archivo_bytes = await archivo.read()
                            else:
                                archivo_bytes = archivo if isinstance(archivo, bytes) else bytes(archivo)

                            # Detectar MIME type por nombre de archivo
                            nombre_archivo = getattr(archivo, 'filename', f'archivo_{i+1}')
                            extension = nombre_archivo.split('.')[-1].lower()
                            mime_type_map = {
                                'pdf': 'application/pdf',
                                'jpg': 'image/jpeg',
                                'jpeg': 'image/jpeg',
                                'png': 'image/png',
                                'gif': 'image/gif',
                                'txt': 'text/plain'
                            }
                            mime_type = mime_type_map.get(extension, 'application/octet-stream')

                            # Crear Part con tipos correctos
                            part_inline = types.Part.from_bytes(
                                data=archivo_bytes,
                                mime_type=mime_type
                            )

                            contents.append(part_inline)
                            logger.info(f"Archivo {i+1} ({mime_type}) enviado inline (fallback): {len(archivo_bytes):,} bytes")
                        except Exception as fallback_error:
                            logger.error(f"Error en fallback inline: {fallback_error}")
                            continue

                # Agregar referencias de Files API al contenido
                for file_ref in uploaded_files_refs:
                    # Obtener objeto File usando la referencia
                    file_obj = self.client.files.get(name=file_ref.name)
                    contents.append(file_obj)
                    logger.info(f"Referencia Files API agregada: {file_ref.name}")
            
            # PASO 4: Llamar a Gemini con contenido híbrido
            logger.info(f"Llamando a Gemini con {len(contents)} elementos: 1 prompt + {len(archivos_directos)} archivos")
            
            # Usar el modelo directamente en lugar de _llamar_gemini para archivos directos
            respuesta = await self._llamar_gemini_hibrido(contents)
            
            logger.info(f" Respuesta híbrida de Gemini recibida: {respuesta[:500]}...")
            
            # PASO 5: Procesar respuesta (igual que antes)
            # Limpiar respuesta si viene con texto extra
            respuesta_limpia = self._limpiar_respuesta_json(respuesta)
            
            # Parsear JSON
            resultado = json.loads(respuesta_limpia)
            
            # Extraer clasificación y detección de consorcio
            factura_identificada = resultado.get("factura_identificada", False)
            rut_identificado = resultado.get("rut_identificado", False)
            clasificacion = resultado.get("clasificacion", resultado)  # Fallback para formato anterior
            # NUEVO v3.1.2: Detectar consorcio directamente del resultado de Gemini
            es_consorcio = resultado.get("es_consorcio", False)

            # Detectar tipo recurso extranjero usando validación manual (SRP)
            es_recurso_extranjero = self._evaluar_tipo_recurso(resultado)
            indicadores_extranjera = resultado.get("indicadores_extranjera", [])
            
            
            # Determinar facturación extranjera basada en ubicación del proveedor
            es_facturacion_extranjera = self._determinar_facturacion_extranjera(resultado)
            
            # PASO 6: Guardar respuesta con metadatos del procesamiento híbrido
            clasificacion_data_hibrida = {
                **resultado,
                "metadatos_hibridos": {
                    "procesamiento_hibrido": True,
                    "archivos_directos": nombres_archivos_directos,
                    "archivos_preprocesados": list(textos_preprocesados.keys()),
                    "total_archivos": total_archivos,
                    "timestamp": datetime.now().isoformat(),
                    "version": "2.4.0_hibrido"
                }
            }
            
            await self._guardar_respuesta("clasificacion_documentos_hibrido.json", clasificacion_data_hibrida)
            
            # PASO 7: Logging de resultados
            logger.info(f"factura_identificada: {factura_identificada}, rut_identificado: {rut_identificado}")
            logger.info(f" Clasificación híbrida exitosa: {len(clasificacion)} documentos clasificados")
            logger.info(f" Consorcio detectado: {es_consorcio}")
            logger.info(f" Tipo recurso extranjero detectado: {es_recurso_extranjero}")
            logger.info(f" Facturación extranjera detectada: {es_facturacion_extranjera}")
            if es_recurso_extranjero and indicadores_extranjera:
                logger.info(f" Indicadores extranjera: {indicadores_extranjera}")
            
            # PASO 8: Logging detallado por archivo
            for nombre_archivo, categoria in clasificacion.items():
                origen = "DIRECTO" if nombre_archivo in nombres_archivos_directos else "PREPROCESADO"
                logger.info(f" {nombre_archivo} → {categoria} ({origen})")
            
            return clasificacion, es_consorcio, es_recurso_extranjero, es_facturacion_extranjera
            
        except json.JSONDecodeError as e:
            logger.error(f" Error parseando JSON híbrido de Gemini: {e}")
            logger.error(f"Respuesta problemática: {respuesta}")
            
            raise ValueError(f"Error en JSON clasificación híbrida: {str(e)}")
        
        except Exception as e:
            logger.error(f" Error en clasificación híbrida de documentos: {e}")
            # Logging seguro de archivos directos fallidos (NUEVO v3.0: soporta Files API)
            from utils.utils_archivos import obtener_nombre_archivo
            archivos_fallidos_nombres = [obtener_nombre_archivo(archivo, i) for i, archivo in enumerate(archivos_directos)]
            
            logger.error(f" Archivos directos fallidos: {archivos_fallidos_nombres}")
            logger.error(f" Textos preprocesados fallidos: {list(textos_preprocesados.keys())}")
            raise ValueError(f"Error en clasificación híbrida: {str(e)}")

        finally:
            # PASO 9 (NUEVO v3.0): Cleanup automático de Files API
            try:
                if hasattr(self, 'files_manager') and self.files_manager:
                    await self.files_manager.cleanup_all(ignore_errors=True)
                    logger.info(" Cleanup de Files API completado")
            except Exception as cleanup_error:
                logger.warning(f" Error en cleanup de Files API: {cleanup_error}")


    async def _llamar_gemini_hibrido(self, contents: List) -> str:
        """
        Llamada especial a Gemini para contenido híbrido (prompt + archivos directos).
        
        CORREGIDO: Ahora crea objetos con formato correcto para Gemini multimodal.
        
        Args:
            contents: Lista con prompt + archivos UploadFile [prompt_str, archivo1_UploadFile, archivo2_UploadFile, ...]
            
        Returns:
            str: Respuesta de Gemini
            
        Raises:
            ValueError: Si hay error en la llamada a Gemini
        """
        try:
            timeout_segundos = 120.0
            
            logger.info(f" Llamada híbrida a Gemini con timeout de {timeout_segundos}s")
            logger.info(f" Contenido: 1 prompt + {len(contents) - 1} archivos directos")
            
            #  CREAR CONTENIDO MULTIMODAL CORRECTO
            contenido_multimodal = []
            
            # Agregar prompt (primer elemento)
            if contents:
                prompt_texto = contents[0]
                contenido_multimodal.append(prompt_texto)
                logger.info(f" Prompt agregado: {len(prompt_texto):,} caracteres")
            
            #  PROCESAR ARCHIVOS DIRECTOS CORRECTAMENTE
            archivos_directos = contents[1:] if len(contents) > 1 else []
            for i, archivo_elemento in enumerate(archivos_directos):
                try:
                    # NUEVO v3.0: Si es objeto File de Files API, crear Part correcto
                    if hasattr(archivo_elemento, 'name') and hasattr(archivo_elemento, 'uri') and hasattr(archivo_elemento, 'mime_type'):
                        # Es un objeto File de Files API - crear Part con file_data
                        file_part = types.Part(
                            file_data=types.FileData(
                                mime_type=archivo_elemento.mime_type,
                                file_uri=archivo_elemento.uri
                            )
                        )
                        contenido_multimodal.append(file_part)
                        logger.info(f" Archivo Files API agregado: {archivo_elemento.name} ({archivo_elemento.mime_type})")
                        continue

                    # Si es bytes (resultado de archivo.read()), necesitamos crear objeto correcto
                    elif isinstance(archivo_elemento, bytes):
                        # Detectar tipo de archivo por magic bytes
                        if archivo_elemento.startswith(b'%PDF'):
                            mime_type = "application/pdf"
                            logger.info(f" PDF detectado por magic bytes: {len(archivo_elemento):,} bytes")
                        elif archivo_elemento.startswith((b'\xff\xd8\xff', b'\x89PNG')):
                            # Es imagen JPEG o PNG
                            if archivo_elemento.startswith(b'\xff\xd8\xff'):
                                mime_type = "image/jpeg"
                            else:
                                mime_type = "image/png"
                            logger.info(f" Imagen detectada por magic bytes: {mime_type}, {len(archivo_elemento):,} bytes")
                        else:
                            # Tipo genérico
                            mime_type = "application/octet-stream"
                            logger.info(f" Archivo genérico: {len(archivo_elemento):,} bytes")

                        # Crear Part usando types.Part.from_bytes()
                        archivo_objeto = types.Part.from_bytes(
                            data=archivo_elemento,
                            mime_type=mime_type
                        )

                    elif hasattr(archivo_elemento, 'read'):
                        # Es un UploadFile que no se ha leído aún
                        await archivo_elemento.seek(0)
                        archivo_bytes = await archivo_elemento.read()

                        # Determinar MIME type por extension
                        nombre_archivo = getattr(archivo_elemento, 'filename', f'archivo_{i+1}')
                        extension = nombre_archivo.split('.')[-1].lower() if '.' in nombre_archivo else ''

                        if extension == 'pdf':
                            mime_type = "application/pdf"
                        elif extension in ['jpg', 'jpeg']:
                            mime_type = "image/jpeg"
                        elif extension == 'png':
                            mime_type = "image/png"
                        elif extension == 'gif':
                            mime_type = "image/gif"
                        elif extension in ['bmp']:
                            mime_type = "image/bmp"
                        elif extension in ['tiff', 'tif']:
                            mime_type = "image/tiff"
                        elif extension == 'webp':
                            mime_type = "image/webp"
                        else:
                            mime_type = "application/octet-stream"

                        # Crear Part usando types.Part.from_bytes()
                        archivo_objeto = types.Part.from_bytes(
                            data=archivo_bytes,
                            mime_type=mime_type
                        )
                        logger.info(f" Archivo {i+1} procesado: {nombre_archivo} ({len(archivo_bytes):,} bytes, {mime_type})")

                    else:
                        # Tipo desconocido, intentar convertir
                        logger.warning(f" Tipo de archivo desconocido: {type(archivo_elemento)}")
                        bytes_data = bytes(archivo_elemento) if not isinstance(archivo_elemento, bytes) else archivo_elemento
                        archivo_objeto = types.Part.from_bytes(
                            data=bytes_data,
                            mime_type="application/octet-stream"
                        )

                    contenido_multimodal.append(archivo_objeto)

                except Exception as e:
                    logger.error(f" Error procesando archivo {i+1}: {e}")
                    continue
            
            # NUEVO SDK v2.0: Llamar a Gemini con contenido multimodal
            logger.info(f"Enviando a Gemini (nuevo SDK): {len(contenido_multimodal)} elementos")

            loop = asyncio.get_event_loop()

            respuesta = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model=self.model_name,
                        contents=contenido_multimodal,
                        config=self.generation_config
                    )
                ),
                timeout=timeout_segundos
            )

            if not respuesta:
                raise ValueError("Gemini devolvió respuesta None en modo híbrido")

            if not hasattr(respuesta, 'text') or not respuesta.text:
                raise ValueError("Gemini devolvió respuesta sin texto en modo híbrido")

            texto_respuesta = respuesta.text.strip()

            if not texto_respuesta:
                raise ValueError("Gemini devolvió texto vacío en modo híbrido")

            logger.info(f"Respuesta híbrida de Gemini recibida: {len(texto_respuesta):,} caracteres")
            return texto_respuesta
            
        except asyncio.TimeoutError:
            # Gateway Timeout - El servicio de IA no respondió a tiempo en modo híbrido
            error_msg = f"IA tardó más de {timeout_segundos}s en procesar archivos directos"
            logger.error(f"Timeout híbrido: {error_msg}")
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "Timeout en clasificación híbrida de documentos",
                    "tipo": "gateway_timeout",
                    "servicio_externo": "Google Gemini API",
                    "timeout_configurado": timeout_segundos,
                    "mensaje": error_msg,
                    "modo_procesamiento": "hibrido_multimodal",
                    "sugerencia": "El servicio de IA no respondió a tiempo. Intente con menos archivos o archivos más pequeños.",
                    "retry_sugerido": True
                }
            )
        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"Error llamando a Gemini en modo híbrido: {e}")
            logger.error(f"Tipo de contenido enviado: {[type(item) for item in contents[:2]]}")

            # Manejo específico según tipo de error de Gemini
            if "quota" in error_str or "rate limit" in error_str or "429" in error_str:
                # Too Many Requests - Límite de rate/quota excedido
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Límite de uso del servicio de IA excedido",
                        "tipo": "quota_exceeded",
                        "servicio_externo": "Google Gemini API",
                        "mensaje": str(e),
                        "modo_procesamiento": "hibrido_multimodal",
                        "sugerencia": "Se ha excedido la cuota de la API. Intente nuevamente más tarde.",
                        "retry_sugerido": True
                    }
                )
            elif "authentication" in error_str or "unauthorized" in error_str or "api key" in error_str:
                # Bad Gateway - Error de autenticación con servicio externo
                raise HTTPException(
                    status_code=502,
                    detail={
                        "error": "Error de autenticación con servicio de IA",
                        "tipo": "authentication_error",
                        "servicio_externo": "Google Gemini API",
                        "mensaje": "Problema con las credenciales del servicio de IA",
                        "sugerencia": "Contacte al administrador del sistema.",
                        "retry_sugerido": False
                    }
                )
            else:
                # Bad Gateway - Otros errores del servicio externo
                raise HTTPException(
                    status_code=502,
                    detail={
                        "error": "Error en clasificación híbrida de documentos",
                        "tipo": "bad_gateway",
                        "servicio_externo": "Google Gemini API",
                        "mensaje": str(e),
                        "modo_procesamiento": "hibrido_multimodal",
                        "sugerencia": "Error en el servicio de IA. Verifique los archivos e intente nuevamente.",
                        "retry_sugerido": True
                    }
                )


    async def analizar_consorcio(self,
                                  documentos_clasificados: Dict[str, Dict],
                                  es_facturacion_extranjera: bool = False,
                                  archivos_directos: List[UploadFile] = None,
                                  cache_archivos: Dict[str, bytes] = None,
                                  proveedor: str = None) -> Dict[str, Any]:
        """
        DELEGACIÓN A CLASIFICADOR ESPECIALIZADO (Principio SRP + DIP).

        Delega el análisis de consorcios al ClasificadorConsorcio especializado.
        Siguiendo arquitectura SOLID con separación de responsabilidades.

        Args:
            documentos_clasificados: Diccionario {nombre_archivo: {categoria, texto}}
            es_facturacion_extranjera: Si es facturación extranjera
            archivos_directos: Lista de archivos directos
            cache_archivos: Cache de archivos para workers paralelos
            proveedor: Nombre del proveedor/consorcio

        Returns:
            Dict[str, Any]: Análisis completo del consorcio

        Raises:
            ValueError: Si no se encuentra factura o hay error en procesamiento
        """
        logger.info("DELEGANDO análisis de consorcio a ClasificadorConsorcio (SOLID - SRP)")

        # DIP: Delegar a clasificador especializado
        return await self.clasificador_consorcio.analizar_consorcio(
            documentos_clasificados=documentos_clasificados,
            es_facturacion_extranjera=es_facturacion_extranjera,
            archivos_directos=archivos_directos,
            cache_archivos=cache_archivos,
            proveedor=proveedor
        )

        
    async def _llamar_gemini_hibrido_factura(self, prompt: str, archivos_directos: List[UploadFile]) -> str:
        
             
        """
         FUNCIÓN HÍBRIDA PARA ANÁLISIS DE FACTURA: Prompt + Archivos directos para análisis de retefuente.
         
         FUNCIONALIDAD:
         ✅ Análisis especializado de facturas con multimodalidad
         ✅ Combina prompt de análisis + archivos PDFs/imágenes
         ✅ Optimizado para análisis de retefuente, consorcios y extranjera
         ✅ Reutilizable para todos los tipos de análisis de facturas
         ✅ Timeout extendido para análisis complejo
         
         Args:
             prompt: Prompt especializado para análisis (PROMPT_ANALISIS_FACTURA, etc.)
             archivos_directos: Lista de archivos para envío directo a Gemini
             
         Returns:
             str: Respuesta de Gemini con análisis completo
             
         Raises:
             ValueError: Si hay error en la llamada a Gemini
         """
        try:
            # Normalizar archivos_directos (puede ser None)
            if archivos_directos is None:
                archivos_directos = []

            # Timeout extendido para análisis de facturas (más complejo que clasificación)
            timeout_segundos = 280.0  # 4 minutos para análisis detallado

            logger.info(f" Análisis híbrido de factura con timeout de {timeout_segundos}s")
            logger.info(f" Contenido: 1 prompt de análisis + {len(archivos_directos)} archivos directos")

            #  CREAR CONTENIDO MULTIMODAL CORRECTO PARA ANÁLISIS
            contenido_multimodal = []

            # Agregar prompt de análisis (primer elemento)
            contenido_multimodal.append(prompt)
            logger.info(f"Prompt de análisis agregado: {len(prompt):,} caracteres")

            # NUEVO v3.0: PROCESAR ARCHIVOS CON FILES API + VALIDACIÓN ROBUSTA
            uploaded_files_refs = []

            for i, archivo in enumerate(archivos_directos):
                try:
                    #  LOGGING INICIAL PARA DIAGNÓSTICO
                    tipo_archivo = type(archivo).__name__

                    # NUEVO v3.0: DETECTAR OBJETOS FILE DE GOOGLE FILES API
                    if hasattr(archivo, 'uri') and hasattr(archivo, 'mime_type'):
                        # Ya está en Files API, crear Part directamente sin leer bytes
                        file_part = types.Part(
                            file_data=types.FileData(
                                mime_type=archivo.mime_type,
                                file_uri=archivo.uri
                            )
                        )
                        contenido_multimodal.append(file_part)

                        # Obtener nombre seguro
                        from utils.utils_archivos import obtener_nombre_archivo
                        nombre_archivo = obtener_nombre_archivo(archivo, i)

                        logger.info(f" Archivo {i+1}/{len(archivos_directos)} reutilizado desde Files API: {nombre_archivo} ({tipo_archivo})")
                        continue  # Pasar al siguiente archivo, este ya está procesado

                    # Para UploadFile normales, continuar con flujo de validación y upload
                    nombre_archivo_debug = getattr(archivo, 'filename', f'archivo_sin_nombre_{i+1}')
                    logger.info(f" Procesando archivo {i+1}/{len(archivos_directos)}: {nombre_archivo_debug} (Tipo: {tipo_archivo})")

                    #  PASO 1: LECTURA SEGURA CON RETRY MEJORADA
                    archivo_bytes, nombre_archivo = await self._leer_archivo_seguro(archivo)

                    #  PASO 2: VALIDACIÓN ESPECÍFICA PARA PDFs
                    if archivo_bytes.startswith(b'%PDF') or nombre_archivo.lower().endswith('.pdf'):
                        #  VALIDACIÓN CRÍTICA: Verificar que el PDF tiene páginas
                        if not await self._validar_pdf_tiene_paginas(archivo_bytes, nombre_archivo):
                            logger.error(f"PDF inválido o sin páginas, omitiendo: {nombre_archivo}")
                            continue  # Saltar este archivo problemático
                        logger.info(f" PDF VALIDADO para análisis: {nombre_archivo} ({len(archivo_bytes):,} bytes)")

                    # PASO 3: INTENTAR UPLOAD A FILES API
                    try:
                        await archivo.seek(0)  # Resetear antes de upload
                        file_result = await self.files_manager.upload_file(
                            archivo=archivo,
                            wait_for_active=True,
                            timeout_seconds=300
                        )
                        uploaded_files_refs.append(file_result)
                        logger.info(f"Archivo subido a Files API: {nombre_archivo} -> {file_result.name}")

                    except Exception as upload_error:
                        logger.warning(f"Error en Files API para {nombre_archivo}: {upload_error}")
                        logger.info(f"Fallback: enviando {nombre_archivo} inline")

                        # FALLBACK: Envío inline con types.Part.from_bytes()
                        extension = nombre_archivo.split('.')[-1].lower() if '.' in nombre_archivo else ''
                        mime_type_map = {
                            'pdf': 'application/pdf',
                            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                            'png': 'image/png', 'gif': 'image/gif',
                            'bmp': 'image/bmp', 'tiff': 'image/tiff', 'tif': 'image/tiff',
                            'webp': 'image/webp'
                        }

                        # Detectar MIME type por magic bytes o extensión
                        if archivo_bytes.startswith(b'%PDF'):
                            mime_type = 'application/pdf'
                        elif archivo_bytes.startswith(b'\xff\xd8\xff'):
                            mime_type = 'image/jpeg'
                        elif archivo_bytes.startswith(b'\x89PNG'):
                            mime_type = 'image/png'
                        else:
                            mime_type = mime_type_map.get(extension, 'application/octet-stream')

                        # Crear Part inline
                        part_inline = types.Part.from_bytes(
                            data=archivo_bytes,
                            mime_type=mime_type
                        )
                        contenido_multimodal.append(part_inline)
                        logger.info(f" Archivo inline: {nombre_archivo} ({mime_type}, {len(archivo_bytes):,} bytes)")

                except ValueError as ve:
                    # Errores específicos de validación
                    logger.error(f" Error de validación en archivo {i+1}: {ve}")
                    logger.warning(f" Omitiendo archivo problemático: {getattr(archivo, 'filename', f'archivo_{i+1}')}")
                    continue
                except Exception as e:
                    # Otros errores inesperados
                    logger.error(f" Error inesperado procesando archivo {i+1}: {e}")
                    logger.warning(f" Omitiendo archivo con error: {getattr(archivo, 'filename', f'archivo_{i+1}')}")
                    continue

            # PASO 4: Agregar referencias de archivos SUBIDOS en este flujo
            # NOTA: Los archivos File de Google (desde cache) ya fueron agregados directamente en el loop
            for file_ref in uploaded_files_refs:
                file_obj = self.client.files.get(name=file_ref.name)
                file_part = types.Part(
                    file_data=types.FileData(
                        mime_type=file_obj.mime_type,
                        file_uri=file_obj.uri
                    )
                )
                contenido_multimodal.append(file_part)
                logger.info(f" Referencia Files API agregada (recién subido): {file_ref.name}")
            
            #  VALIDACIÓN FINAL: Verificar que tenemos contenido válido para enviar
            archivos_validos = len(contenido_multimodal) - 1  # -1 porque el primer elemento es el prompt

            if archivos_validos == 0 and len(archivos_directos) > 0:
                # Solo lanzar error si se esperaban archivos pero ninguno fue validado
                error_msg = "No se pudo validar ningún archivo para análisis - todos los archivos presentaron problemas"
                logger.error(f" {error_msg}")
                raise ValueError(error_msg)
            elif archivos_validos == 0:
                # Análisis solo con texto preprocesado (XML, Excel, Word, etc.)
                logger.info(" Análisis híbrido: Solo texto preprocesado, sin archivos multimodales")

            if archivos_validos < len(archivos_directos):
                archivos_omitidos = len(archivos_directos) - archivos_validos
                logger.warning(f"Se omitieron {archivos_omitidos} archivos problemáticos de {len(archivos_directos)} archivos totales")
            
            # ✅ LLAMAR A GEMINI CON CONTENIDO MULTIMODAL VALIDADO (NUEVO SDK v3.0)
            logger.info(f" Enviando análisis a Gemini (nuevo SDK + Files API): {len(contenido_multimodal)} elementos ({archivos_validos} archivos validados)")

            loop = asyncio.get_event_loop()

            respuesta = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model=self.model_name,
                        contents=contenido_multimodal,
                        config=self.generation_config
                    )
                ),
                timeout=timeout_segundos
            )
            
            if not respuesta:
                raise ValueError("IA devolvió respuesta None en análisis híbrido - posible problema de validación de archivos")
                
            if not hasattr(respuesta, 'text') or not respuesta.text:
                raise ValueError(" IA devolvió respuesta sin texto - archivos validados correctamente pero sin respuesta")
                
            texto_respuesta = respuesta.text.strip()
            
            if not texto_respuesta:
                raise ValueError(" IA devolvió texto vacío - validación exitosa pero respuesta vacía")
                
            logger.info(f" Análisis híbrido de factura completado: {len(texto_respuesta):,} caracteres")
            return texto_respuesta
            
        except asyncio.TimeoutError:
            # Gateway Timeout - El servicio de IA no respondió a tiempo en análisis de factura
            error_msg = f"Análisis híbrido tardó más de {timeout_segundos}s en completarse"
            logger.error(f"Timeout en análisis híbrido: {error_msg}")
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "Timeout en análisis de factura",
                    "tipo": "gateway_timeout",
                    "servicio_externo": "Google Gemini API",
                    "timeout_configurado": timeout_segundos,
                    "mensaje": error_msg,
                    "modo_procesamiento": "analisis_factura_multimodal",
                    "sugerencia": "El análisis de factura excedió el tiempo límite. Intente con documentos más pequeños o menos archivos.",
                    "retry_sugerido": True
                }
            )
        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"Error en análisis híbrido de factura: {e}")

            # Manejar archivos_directos que puede ser None
            archivos_info = []
            if archivos_directos:
                archivos_info = [getattr(archivo, 'filename', 'sin_nombre') for archivo in archivos_directos]
            logger.error(f"Archivos enviados: {archivos_info}")

            # Manejo específico según tipo de error de Gemini
            if "quota" in error_str or "rate limit" in error_str or "429" in error_str:
                # Too Many Requests - Límite de rate/quota excedido
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Límite de uso del servicio de IA excedido",
                        "tipo": "quota_exceeded",
                        "servicio_externo": "Google Gemini API",
                        "mensaje": str(e),
                        "archivos_procesados": archivos_info,
                        "modo_procesamiento": "analisis_factura_multimodal",
                        "sugerencia": "Se ha excedido la cuota de la API. Intente nuevamente más tarde.",
                        "retry_sugerido": True
                    }
                )
            elif "authentication" in error_str or "unauthorized" in error_str or "api key" in error_str:
                # Bad Gateway - Error de autenticación con servicio externo
                raise HTTPException(
                    status_code=502,
                    detail={
                        "error": "Error de autenticación con servicio de IA",
                        "tipo": "authentication_error",
                        "servicio_externo": "Google Gemini API",
                        "mensaje": "Problema con las credenciales del servicio de IA",
                        "sugerencia": "Contacte al administrador del sistema.",
                        "retry_sugerido": False
                    }
                )
            else:
                # Bad Gateway - Otros errores del servicio externo
                raise HTTPException(
                    status_code=502,
                    detail={
                        "error": "Error en análisis de factura",
                        "tipo": "bad_gateway",
                        "servicio_externo": "Google Gemini API",
                        "mensaje": str(e),
                        "archivos_procesados": archivos_info,
                        "modo_procesamiento": "analisis_factura_multimodal",
                        "sugerencia": "Error en el servicio de IA. Verifique los archivos e intente nuevamente.",
                        "retry_sugerido": True
                    }
                )

        finally:
            # PASO 5 (NUEVO v3.0): Cleanup automático de Files API
            try:
                if hasattr(self, 'files_manager') and self.files_manager and uploaded_files_refs:
                    await self.files_manager.cleanup_all(ignore_errors=True)
                    logger.info(f" Cleanup Files API: {len(uploaded_files_refs)} archivos eliminados")
            except Exception as cleanup_error:
                logger.warning(f" Error en cleanup Files API: {cleanup_error}")

    def _obtener_archivos_clonados_desde_cache(self, cache_archivos):
        """
        NUEVO v3.0 - FILES API: Retorna referencias de Files API desde cache (no clona).

        Con Files API, los workers pueden reutilizar las mismas referencias sin clonar.
        Cada worker usa la misma referencia de archivo en Files API.

        Args:
            cache_archivos: Dict[str, FileUploadResult] - Cache de referencias Files API

        Returns:
            List[File]: Lista de objetos File de Files API para reutilizar
        """
        from .gemini_files_manager import FileUploadResult

        archivos_referencias = []

        for nombre_archivo, file_ref in cache_archivos.items():
            try:
                # Si es FileUploadResult (nuevo cache Files API)
                if isinstance(file_ref, FileUploadResult):
                    # Obtener objeto File de Files API
                    file_obj = self.client.files.get(name=file_ref.name)
                    archivos_referencias.append(file_obj)
                    logger.info(f" Referencia Files API reutilizada: {nombre_archivo} -> {file_ref.name}")

                # Si es bytes (cache legacy - fallback)
                elif isinstance(file_ref, bytes):
                    logger.warning(f" Cache legacy (bytes) detectado para {nombre_archivo}, creando clon")
                    archivo_clonado = self.crear_archivo_clon_para_worker(file_ref, nombre_archivo)
                    archivos_referencias.append(archivo_clonado)

                else:
                    logger.error(f" Tipo de cache desconocido para {nombre_archivo}: {type(file_ref)}")
                    continue

            except Exception as e:
                logger.error(f" Error obteniendo referencia {nombre_archivo}: {e}")
                continue

        logger.info(f" {len(archivos_referencias)} referencias Files API listas para worker")
        return archivos_referencias
    
    # ===============================
    #  FUNCIÓN COORDINADORA PARA CONCURRENCIA
    # ===============================
    
    async def preparar_archivos_para_workers_paralelos(self, archivos_directos: List[UploadFile]):
        """
        NUEVO v3.0 - FILES API: Sube archivos UNA VEZ a Files API y crea cache de referencias.

        En lugar de leer bytes y pasarlos a cada worker, ahora:
        1. Sube archivos a Files API una sola vez
        2. Cachea las referencias FileUploadResult
        3. Workers reutilizan las mismas referencias (no re-upload)

        BENEFICIOS:
        - Archivos hasta 2GB (vs 20MB inline)
        - Una sola transferencia (vs N transfers para N workers)
        - Reutilización de referencias en análisis paralelos

        Args:
            archivos_directos: Lista de archivos UploadFile originales

        Returns:
            Dict[str, FileUploadResult]: Cache {nombre_archivo: FileUploadResult}
        """
        from .gemini_files_manager import FileUploadResult

        if not archivos_directos:
            return {}

        logger.info(f"NUEVO CACHE FILES API: Subiendo {len(archivos_directos)} archivos a Files API")

        cache_archivos = {}

        # Upload en paralelo para mejor performance
        upload_tasks = []
        for archivo in archivos_directos:
            try:
                # Validar archivo antes de subir
                archivo_bytes, nombre_archivo = await self._leer_archivo_seguro(archivo)

                # Validar PDF si es necesario
                if archivo_bytes.startswith(b'%PDF'):
                    if not await self._validar_pdf_tiene_paginas(archivo_bytes, nombre_archivo):
                        logger.error(f"PDF inválido omitido: {nombre_archivo}")
                        continue

                # Resetear puntero para upload
                await archivo.seek(0)

                # Crear tarea de upload
                task = self.files_manager.upload_file(
                    archivo=archivo,
                    wait_for_active=True,
                    timeout_seconds=300
                )
                upload_tasks.append((nombre_archivo, task))

            except Exception as e:
                from utils.utils_archivos import obtener_nombre_archivo
                nombre_error = obtener_nombre_archivo(archivo, 0)
                logger.error(f"Error validando archivo {nombre_error}: {e}")
                continue

        # Ejecutar uploads en paralelo
        if upload_tasks:
            results = await asyncio.gather(
                *[task for _, task in upload_tasks],
                return_exceptions=True
            )

            for (nombre, _), result in zip(upload_tasks, results):
                if isinstance(result, Exception):
                    logger.error(f"Error subiendo {nombre} a Files API: {result}")
                    continue

                if isinstance(result, FileUploadResult):
                    cache_archivos[nombre] = result
                    logger.info(f"Archivo cacheado en Files API: {nombre} -> {result.name}")

        logger.info(f"Cache Files API preparado: {len(cache_archivos)} archivos listos para workers")
        return cache_archivos
    
    def crear_archivo_clon_para_worker(self, archivo_bytes: bytes, nombre_archivo: str) -> UploadFile:
        """
        Crea un UploadFile independiente para un worker específico.
        
        CORREGIDO: Compatible con todas las versiones de Starlette/FastAPI.
        
        Args:
            archivo_bytes: Contenido del archivo
            nombre_archivo: Nombre del archivo
            
        Returns:
            UploadFile: Archivo clonado independiente
        """
        from io import BytesIO
        from starlette.datastructures import UploadFile
        
        # Stream independiente para este worker 
        stream = BytesIO(archivo_bytes)
        
        # ✅ SOLUCIÓN: UploadFile sin content_type (compatible con todas las versiones)
        try:
            # Intentar con content_type (versiones más nuevas)
            archivo_clonado = UploadFile(
                filename=nombre_archivo,
                file=stream,
                content_type="application/pdf" if nombre_archivo.lower().endswith('.pdf') else "application/octet-stream"
            )
        except TypeError:
            # Fallback sin content_type (versiones más antiguas)
            archivo_clonado = UploadFile(
                filename=nombre_archivo,
                file=stream
            )
        
        return archivo_clonado
    
    async def _leer_archivo_seguro(self, archivo: UploadFile) -> tuple[bytes, str]:
        """
        Lectura segura de archivo con single retry para prevenir errores de "archivo sin páginas".
        
        CORREGIDO: Manejo mejorado de UploadFile para evitar falsos positivos de "archivo vacío".
        
        Returns:
            tuple: (archivo_bytes, nombre_archivo)
            
        Raises:
            ValueError: Si no se pudo leer el archivo después del retry
        """
        nombre_archivo = getattr(archivo, 'filename', 'sin_nombre')
        
        #  SINGLE RETRY como solicitado 
        for intento in range(1, 3):  # Solo 2 intentos
            try:
                # 🔧 RESETEAR POSICIÓN DE FORMA MÁS ROBUSTA
                if hasattr(archivo, 'seek'):
                    try:
                        await archivo.seek(0)
                        logger.info(f" Archivo posicionado al inicio: {nombre_archivo} - Intento {intento}")
                    except Exception as seek_error:
                        logger.warning(f" Error en seek para {nombre_archivo}: {seek_error}")
                        # Continuar de todas formas, algunos UploadFile no soportan seek
                
                # 📖 LEER CONTENIDO CON MANEJO MEJORADO
                if hasattr(archivo, 'read'):
                    archivo_bytes = await archivo.read()
                elif hasattr(archivo, 'file') and hasattr(archivo.file, 'read'):
                    # Algunos UploadFile tienen el contenido en .file
                    archivo_bytes = archivo.file.read()
                    if not isinstance(archivo_bytes, bytes):
                        archivo_bytes = archivo_bytes.encode('utf-8') if isinstance(archivo_bytes, str) else bytes(archivo_bytes)
                else:
                    # Fallback: intentar convertir directamente
                    archivo_bytes = bytes(archivo) if not isinstance(archivo, bytes) else archivo
                
                logger.info(f" Lectura completada: {nombre_archivo} - {len(archivo_bytes) if archivo_bytes else 0} bytes leídos")
                
                #  VALIDACIÓN CRÍTICA MEJORADA
                if not archivo_bytes:
                    logger.error(f"Archivo vacío en intento {intento}: {nombre_archivo} - 0 bytes")
                    if intento < 2:  # Solo un retry más
                        logger.info(f" Reintentando lectura para: {nombre_archivo}")
                        await asyncio.sleep(0.1)  # Pequeña pausa
                        continue
                    else:
                        raise ValueError(f"Archivo {nombre_archivo} está vacío después de {intento} intentos")
                
                if len(archivo_bytes) < 50:  # Reducido de 100 a 50 para ser menos restrictivo
                    logger.error(f" Archivo demasiado pequeño en intento {intento}: {nombre_archivo} ({len(archivo_bytes)} bytes)")
                    if intento < 2:
                        await asyncio.sleep(0.1)
                        continue
                    else:
                        raise ValueError(f"Archivo {nombre_archivo} demasiado pequeño: {len(archivo_bytes)} bytes")
                
                # ✅ VALIDACIÓN ADICIONAL PARA PDFs
                if archivo_bytes.startswith(b'%PDF'):
                    logger.info(f" PDF detectado con magic bytes: {nombre_archivo}")
                elif nombre_archivo.lower().endswith('.pdf'):
                    logger.warning(f" Archivo con extensión PDF pero sin magic bytes: {nombre_archivo}")
                    # Aún así intentar procesarlo
                
                logger.info(f" Archivo leído exitosamente: {nombre_archivo} ({len(archivo_bytes):,} bytes) - Intento {intento}")
                return archivo_bytes, nombre_archivo
                
            except Exception as e:
                logger.error(f" Error leyendo archivo en intento {intento}: {e}")
                logger.error(f"Tipo de archivo: {type(archivo)}, Atributos: {dir(archivo)[:5]}...")  # Limitar debug info
                if intento < 2:  # Solo un retry más
                    await asyncio.sleep(0.2)
                    continue
                else:
                    raise ValueError(f"No se pudo leer el archivo {nombre_archivo}: {str(e)}")
        
        raise ValueError(f"Error inesperado leyendo archivo {nombre_archivo}")                
    
    async def _validar_pdf_tiene_paginas(self, pdf_bytes: bytes, nombre_archivo: str) -> bool:
        """
        Valida que el PDF tenga páginas antes de enviarlo a Gemini para prevenir error "no tiene páginas".
        
        Args:
            pdf_bytes: Contenido del PDF en bytes
            nombre_archivo: Nombre del archivo para logging
            
        Returns:
            bool: True si el PDF es válido y tiene páginas
            
        Raises:
            ValueError: Si hay error crítico en la validación
        """
        try:
            pdf_stream = BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
            
            # 🚨 VALIDACIÓN CRÍTICA: Verificar número de páginas
            num_paginas = len(pdf_reader.pages)
            
            if num_paginas == 0:
                logger.error(f" PDF sin páginas: {nombre_archivo}")
                return False
            
            # ✅ VALIDACIÓN ADICIONAL: Verificar que al menos una página tenga contenido
            try:
                primera_pagina = pdf_reader.pages[0]
                contenido = primera_pagina.extract_text()
                
                if not contenido.strip():
                    logger.warning(f" PDF posiblemente escaneado (sin texto extraíble): {nombre_archivo}")
                    # ✅ Aún así es válido para Gemini (puede leer imágenes en PDFs)
                    logger.info(f" PDF escaneado aceptado para Gemini: {nombre_archivo}")
                else:
                    logger.info(f" PDF con texto extraíble validado: {nombre_archivo}")
                    
            except Exception as e:
                logger.warning(f" No se pudo extraer texto de {nombre_archivo}: {e}")
                # No es crítico, Gemini puede procesar PDFs sin texto extraíble
            
            # ✅ VALIDACIÓN FINAL EXITOSA
            logger.info(f" PDF validado correctamente: {nombre_archivo} - {num_paginas} páginas")
            return True
            
        except Exception as e:
            logger.error(f" Error validando PDF {nombre_archivo}: {e}")
            # 🚨 Por seguridad, considerar inválido si no se puede validar
            return False
        finally:
            # Limpiar stream
            try:
                pdf_stream.close()
            except:
                pass
    
    async def _llamar_gemini(self, prompt: str, usar_modelo_consorcio: bool = False) -> str:
        """
        NUEVO SDK v2.0: Llamada a Gemini con manejo de errores y timeout.

        Args:
            prompt: Prompt para enviar a Gemini
            usar_modelo_consorcio: Si usar config con más tokens para consorcios

        Returns:
            str: Respuesta de Gemini

        Raises:
            HTTPException: 504 para timeout, 429 para quota excedida, 502 para otros errores
        """
        try:
            # Seleccionar configuración según el caso
            config = self.generation_config_consorcio if usar_modelo_consorcio else self.generation_config

            # Timeout escalonado según complejidad
            if usar_modelo_consorcio:
                timeout_segundos = 120.0  # 2 minutos para consorcios grandes
            elif "impuestos_especiales" in prompt.lower() or "estampilla" in prompt.lower():
                timeout_segundos = 120.0   # 90s para análisis de impuestos especiales
            else:
                timeout_segundos = 120.0   # 60s para análisis estándar

            logger.info(f"Llamando a Gemini (nuevo SDK) con timeout de {timeout_segundos}s")

            # Crear tarea con timeout
            loop = asyncio.get_event_loop()

            # NUEVO SDK v2.0: usar client.models.generate_content
            respuesta = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.client.models.generate_content(
                        model=self.model_name,
                        contents=[prompt],
                        config=config
                    )
                ),
                timeout=timeout_segundos
            )

            if not respuesta:
                raise ValueError("IA devolvió respuesta None")

            if not hasattr(respuesta, 'text') or not respuesta.text:
                raise ValueError("IA devolvió respuesta sin texto")

            texto_respuesta = respuesta.text.strip()

            if not texto_respuesta:
                raise ValueError("IA devolvió texto vacío")

            logger.info(f"Respuesta de Gemini recibida: {len(texto_respuesta):,} caracteres")
            return texto_respuesta

        except asyncio.TimeoutError:
            # Gateway Timeout - El servicio de IA no respondió a tiempo
            error_msg = f"IA tardó más de {timeout_segundos}s en responder"
            logger.error(f"Timeout llamando a Gemini ({timeout_segundos}s)")
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "Timeout comunicándose con servicio de IA",
                    "tipo": "gateway_timeout",
                    "servicio_externo": "Google Gemini API",
                    "timeout_configurado": timeout_segundos,
                    "mensaje": error_msg,
                    "sugerencia": "El servicio de IA no respondió a tiempo. Intente nuevamente en unos momentos.",
                    "retry_sugerido": True
                }
            )
        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"Error llamando a IA: {e}")

            # Manejo específico según tipo de error de Gemini
            if "quota" in error_str or "rate limit" in error_str or "429" in error_str:
                # Too Many Requests - Límite de rate/quota excedido
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Límite de uso del servicio de IA excedido",
                        "tipo": "quota_exceeded",
                        "servicio_externo": "Google Gemini API",
                        "mensaje": str(e),
                        "sugerencia": "Se ha excedido la cuota de la API. Intente nuevamente más tarde.",
                        "retry_sugerido": True
                    }
                )
            elif "authentication" in error_str or "unauthorized" in error_str or "api key" in error_str:
                # Bad Gateway - Error de autenticación con servicio externo
                raise HTTPException(
                    status_code=502,
                    detail={
                        "error": "Error de autenticación con servicio de IA",
                        "tipo": "authentication_error",
                        "servicio_externo": "Google Gemini API",
                        "mensaje": "Problema con las credenciales del servicio de IA",
                        "sugerencia": "Contacte al administrador del sistema.",
                        "retry_sugerido": False
                    }
                )
            else:
                # Bad Gateway - Otros errores del servicio externo
                raise HTTPException(
                    status_code=502,
                    detail={
                        "error": "Error comunicándose con servicio de IA",
                        "tipo": "bad_gateway",
                        "servicio_externo": "Google Gemini API",
                        "mensaje": str(e),
                        "sugerencia": "Error en el servicio de IA. Intente nuevamente.",
                        "retry_sugerido": True
                    }
                )

    def _evaluar_tipo_recurso(self, resultado: Dict[str, Any]) -> bool:
        """
        Evalua si es tipo de recurso extranjero basado en analisis_fuente_ingreso.

        SRP: Unica responsabilidad - determinar tipo de recurso extranjero segun reglas de negocio.

        REGLA DE DECISION:
        - Si TODAS las respuestas son false (con evidencia) -> es_recurso_extranjero = true
        - Si ALGUNA respuesta es true -> es_recurso_extranjero = false
        - Si alguna respuesta es null (sin info clara) -> es_recurso_extranjero = false

        Campos evaluados de analisis_fuente_ingreso:
        - servicio_uso_colombia: Servicio usado en Colombia
        - ejecutado_en_colombia: Servicio ejecutado en Colombia
        - asistencia_tecnica_colombia: Asistencia tecnica prestada en Colombia
        - bien_ubicado_colombia: Bien ubicado fisicamente en Colombia

        Args:
            resultado: Diccionario con respuesta completa de Gemini

        Returns:
            bool: True si es facturacion extranjera, False en caso contrario

        Examples:
            >>> # Caso 1: Todo false (con evidencia) -> Extranjera
            >>> resultado = {"analisis_fuente_ingreso": {
            ...     "servicio_uso_colombia": False,
            ...     "ejecutado_en_colombia": False,
            ...     "asistencia_tecnica_colombia": False,
            ...     "bien_ubicado_colombia": False
            ... }}
            >>> self._evaluar_facturacion_extranjera(resultado)
            True

            >>> # Caso 2: Alguno true -> NO extranjera
            >>> resultado = {"analisis_fuente_ingreso": {
            ...     "servicio_uso_colombia": True,
            ...     "ejecutado_en_colombia": False,
            ...     "asistencia_tecnica_colombia": False,
            ...     "bien_ubicado_colombia": False
            ... }}
            >>> self._evaluar_facturacion_extranjera(resultado)
            False

            >>> # Caso 3: Alguno null (sin info) -> NO extranjera (conservador)
            >>> resultado = {"analisis_fuente_ingreso": {
            ...     "servicio_uso_colombia": None,
            ...     "ejecutado_en_colombia": False,
            ...     "asistencia_tecnica_colombia": False,
            ...     "bien_ubicado_colombia": False
            ... }}
            >>> self._evaluar_facturacion_extranjera(resultado)
            False
        """
        # Obtener analisis_fuente_ingreso del resultado de Gemini
        analisis = resultado.get("analisis_fuente_ingreso", {})

        # Fallback: Si no existe analisis_fuente_ingreso, usar campo legacy (compatibilidad)
        if not analisis:
            legacy_value = resultado.get("es_facturacion_extranjera", False)
            logger.warning(" analisis_fuente_ingreso no encontrado, usando valor legacy")
            return legacy_value

        # Extraer los 4 criterios de evaluacion
        servicio_uso = analisis.get("servicio_uso_colombia")
        ejecutado = analisis.get("ejecutado_en_colombia")
        asistencia = analisis.get("asistencia_tecnica_colombia")
        bien_ubicado = analisis.get("bien_ubicado_colombia")

        criterios = [servicio_uso, ejecutado, asistencia, bien_ubicado]

        # REGLA 1: Si ALGUNO es true -> NO es recurso extranjero
        if any(criterio is True for criterio in criterios):
            logger.info(" recurso NACIONAL detectada: al menos un criterio es true")
            return False

        # REGLA 2: Si ALGUNO es null -> NO es recurso extranjero (enfoque conservador)
        if any(criterio is None for criterio in criterios):
            logger.info(" recurso NACIONAL por defecto: informacion incompleta (null detectado)")
            return False

        # REGLA 3: Si TODOS son false -> ES recurso extranjero  
        if all(criterio is False for criterio in criterios):
            logger.info(" recurso EXTRANJERO confirmada: todos los criterios son false")
            logger.info(f" Evidencias: servicio_uso={servicio_uso}, ejecutado={ejecutado}, "
                       f"asistencia={asistencia}, bien_ubicado={bien_ubicado}")
            return True

        # Fallback: No deberia llegar aqui, pero por seguridad retornar False
        logger.warning(" Caso no contemplado en evaluacion, retornando False por defecto")
        return False

    def _determinar_facturacion_extranjera(self, resultado: Dict[str, Any]) -> bool:
        """
        Determina si es facturación extranjera basándose en la ubicación del proveedor.

        SRP: Responsabilidad única - evaluar si el proveedor está fuera de Colombia.

        Args:
            resultado: Resultado completo de Gemini con ubicacion_proveedor y es_fuera_colombia

        Returns:
            bool: True si es facturación extranjera, False en caso contrario
        """
        # Extraer campos de ubicación del proveedor
        ubicacion_proveedor = resultado.get("ubicacion_proveedor", "")
        es_fuera_colombia = resultado.get("es_fuera_colombia", False)

        # Mostrar ubicación en logs
        if ubicacion_proveedor:
            logger.info(f" Ubicación proveedor: {ubicacion_proveedor}")
        else:
            logger.info(" Ubicación proveedor: No especificada")

        # Determinar si es facturación extranjera
        if es_fuera_colombia:
            logger.info(" Facturación extranjera detectada: Proveedor fuera de Colombia")
            return True
        else:
            logger.info("🇨🇴 Facturación nacional: Proveedor en Colombia")
            return False

    def _limpiar_respuesta_json(self, respuesta: str) -> str:
        """
        Limpia la respuesta de Gemini para extraer y corregir JSON.

        Correcciones aplicadas:
        1. Extrae JSON de bloques markdown (mejorado con regex)
        2. Limpia caracteres de control no validos en JSON
        3. Corrige comillas dobles duplicadas
        4. Remueve comas antes de } o ]
        5. Corrige guiones Unicode (– a -)
        6. Normaliza strings vacios problematicos

        Args:
            respuesta: Respuesta cruda de Gemini

        Returns:
            str: JSON limpio y corregido

        Raises:
            ValueError: Si no se puede extraer JSON valido
        """
        try:
            import re

            # PASO 1 MEJORADO: Eliminar bloques markdown con regex robusto
            # Elimina ```json seguido de espacios/saltos de linea
            respuesta = re.sub(r'```json\s*', '', respuesta)
            # Elimina ``` final seguido de espacios/saltos de linea
            respuesta = re.sub(r'```\s*$', '', respuesta)
            # Elimina posibles ``` intermedios
            respuesta = re.sub(r'```', '', respuesta)

            # PASO 2: Buscar el primer { y el ultimo }
            inicio = respuesta.find('{')
            fin = respuesta.rfind('}') + 1

            if inicio != -1 and fin != 0:
                json_limpio = respuesta[inicio:fin]

                # PASO 3: Correcciones de sintaxis JSON comunes
                # 3.1: Corregir comillas dobles duplicadas SOLO despues de texto (CHOCO"" -> CHOCO")
                # NO afecta strings vacios validos como ": ""
                json_limpio = re.sub(r'([a-zA-ZÁ-ú0-9\s])""+', r'\1"', json_limpio)

                # 3.2: Remover comas antes de cierre de objeto o array
                json_limpio = re.sub(r',\s*}', '}', json_limpio)  # , } -> }
                json_limpio = re.sub(r',\s*]', ']', json_limpio)  # , ] -> ]

                # 3.3: Corregir guiones Unicode (– a -)
                json_limpio = json_limpio.replace('–', '-')

                # 3.4 NUEVO: Limpiar caracteres de control no validos dentro de strings
                # Esto elimina \n, \r, \t, etc. que causan "Invalid control character"
                json_limpio = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_limpio)

                # 3.5 NUEVO: Normalizar strings vacios problematicos
                # "  " -> "" y "   " -> ""
                json_limpio = re.sub(r':\s*"\s+"', ': ""', json_limpio)

                # PASO 4: Verificar que sea JSON valido
                json.loads(json_limpio)
                logger.info(" JSON limpio y validado correctamente")
                return json_limpio
            else:
                raise ValueError("No se encontro JSON valido en la respuesta")

        except json.JSONDecodeError as e:
            # Intentar correcciones adicionales
            logger.warning(f"Error de sintaxis JSON: {e}")
            logger.warning(f"JSON problematico (primeros 500 chars): {json_limpio[:500] if 'json_limpio' in locals() else respuesta[:500]}")

            try:
                # Intento de correccion agresiva: remover lineas problematicas
                if 'json_limpio' in locals():
                    logger.info(" Intentando correccion agresiva de JSON...")
                    # Remover saltos de linea y espacios extras
                    json_limpio_agresivo = ' '.join(json_limpio.split())
                    json.loads(json_limpio_agresivo)
                    logger.info(" Correccion agresiva exitosa")
                    return json_limpio_agresivo
            except:
                pass

            # Si todo falla, intentar limpiar la respuesta original sin markdown
            try:
                logger.info(" Intentando limpiar respuesta original sin markdown...")
                respuesta_sin_markdown = re.sub(r'```json\s*', '', respuesta)
                respuesta_sin_markdown = re.sub(r'```\s*', '', respuesta_sin_markdown)

                # Buscar JSON en respuesta sin markdown
                inicio = respuesta_sin_markdown.find('{')
                fin = respuesta_sin_markdown.rfind('}') + 1

                if inicio != -1 and fin != 0:
                    json_final = respuesta_sin_markdown[inicio:fin]
                    # Aplicar limpieza de caracteres de control
                    json_final = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_final)
                    json.loads(json_final)
                    logger.info(" Limpieza de respuesta original exitosa")
                    return json_final
            except:
                pass

            # Si todo falla, devolver respuesta original limpia de markdown
            logger.error(" No se pudo corregir el JSON, usando respuesta con limpieza basica")
            respuesta_limpia = re.sub(r'```json\s*', '', respuesta)
            respuesta_limpia = re.sub(r'```\s*', '', respuesta_limpia)
            return respuesta_limpia.strip()

        except Exception as e:
            logger.error(f" Error limpiando JSON: {e}")
            return respuesta

    def _reparar_json_malformado(self, json_str: str) -> str:
        """
        Repara errores comunes en JSON generado por Gemini.

        Args:
            json_str: JSON string potencialmente malformado

        Returns:
            str: JSON string reparado
        """
        try:
            # Reparaciones comunes para errores de Gemini
            json_reparado = json_str

            # 1. Reparar llaves faltantes al final de objetos en arrays
            # Buscar patrones como: "valor": 123.45, seguido directamente por {
            import re

            # Patrón: número o string seguido de coma y luego { (falta })
            patron_llave_faltante = r'(\"[^\"]+\":\s*[0-9.]+)\s*,\s*\n\s*\{'
            coincidencias = list(re.finditer(patron_llave_faltante, json_reparado))

            # Reparar desde el final hacia el inicio para no afectar posiciones
            for match in reversed(coincidencias):
                inicio = match.start()
                fin = match.end()
                # Insertar } antes de la coma
                posicion_coma = json_reparado.find(',', inicio)
                if posicion_coma != -1:
                    json_reparado = json_reparado[:posicion_coma] + '\n    }' + json_reparado[posicion_coma:]

            # 2. Reparar números de punto flotante malformados
            # Convertir 3.5000000000000004 a 3.5
            patron_float_largo = r'(\d+\.\d{10,})'
            def reparar_float(match):
                numero = float(match.group(1))
                return str(round(numero, 2))

            json_reparado = re.sub(patron_float_largo, reparar_float, json_reparado)

            # 3. Verificar si el JSON es válido ahora
            json.loads(json_reparado)
            logger.info("✅ JSON reparado exitosamente")
            return json_reparado

        except json.JSONDecodeError as e:
            logger.warning(f"No se pudo reparar JSON: {e}")
            return json_str
        except Exception as e:
            logger.error(f"Error reparando JSON: {e}")
            return json_str

    async def _guardar_respuesta(self, nombre_archivo: str, contenido: dict):
        """
        Guarda la respuesta de Gemini en archivo JSON en la carpeta Results.
        
        Args:
            nombre_archivo: Nombre del archivo JSON
            contenido: Contenido a guardar
        """
        try:
            # ✅ CORREGIDO: Usar rutas absolutas para evitar errores de subpath
            directorio_base = Path.cwd()  # Directorio actual del proyecto
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            
            # Crear carpeta Results en el directorio base
            carpeta_results = directorio_base / "Results" / fecha_hoy
            carpeta_results.mkdir(parents=True, exist_ok=True)
            
            # Generar timestamp para nombre único
            timestamp = datetime.now().strftime("%H-%M-%S")
            nombre_base = nombre_archivo.replace('.json', '')
            nombre_final = f"{nombre_base}_{timestamp}.json"
            
            # Guardar archivo con ruta absoluta
            ruta_archivo = carpeta_results / nombre_final
            
            with open(ruta_archivo, "w", encoding="utf-8") as f:
                json.dump(contenido, f, indent=2, ensure_ascii=False)
            
            logger.info(f" Respuesta guardada en {ruta_archivo}")
            
        except Exception as e:
            logger.error(f" Error guardando respuesta: {e}")
            # Fallback mejorado: usar directorio actual
            try:
                timestamp = datetime.now().strftime("%H-%M-%S")
                nombre_fallback = f"fallback_{nombre_archivo.replace('.json', '')}_{timestamp}.json"
                ruta_fallback = Path.cwd() / nombre_fallback
                
                with open(ruta_fallback, "w", encoding="utf-8") as f:
                    json.dump(contenido, f, indent=2, ensure_ascii=False)
                
                logger.info(f" Respuesta guardada en fallback: {ruta_fallback}")
                
            except Exception as e2:
                logger.error(f" Error guardando fallback: {e2}")
    
 