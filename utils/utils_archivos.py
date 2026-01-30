"""
UTILIDADES PARA MANEJO DE ARCHIVOS (v3.0)
==========================================

Módulo con funciones auxiliares para manejo de archivos multimodales.
Soporta múltiples tipos de archivos:
- UploadFile de FastAPI
- File de Google Files API
- Bytes directos

Autor: Sistema Preliquidador
Versión: 3.0.0
"""

import logging
from typing import Any, List

# Configuración de logging
logger = logging.getLogger(__name__)


def obtener_nombre_archivo(archivo: Any, index: int = 0) -> str:
    """
    Función auxiliar para obtener el nombre de un archivo de forma segura.

    Maneja diferentes tipos de archivos:
    - UploadFile de FastAPI (tiene .filename)
    - File de Google Files API (tiene .display_name o .name)
    - Otros tipos (fallback a nombre genérico)

    Args:
        archivo: Objeto archivo de cualquier tipo
        index: Índice para nombre fallback

    Returns:
        str: Nombre del archivo

    Examples:
        >>> # UploadFile
        >>> upload_file = UploadFile(filename="factura.pdf")
        >>> obtener_nombre_archivo(upload_file)
        'factura.pdf'

        >>> # File de Google (Files API)
        >>> google_file = File(name="files/abc123", display_name="factura.pdf")
        >>> obtener_nombre_archivo(google_file)
        'factura.pdf'

        >>> # Sin nombre
        >>> bytes_data = b"..."
        >>> obtener_nombre_archivo(bytes_data, 0)
        'archivo_1'
    """
    if hasattr(archivo, 'filename') and archivo.filename:
        # UploadFile de FastAPI
        return archivo.filename
    elif hasattr(archivo, 'display_name') and archivo.display_name:
        # File de Google Files API (campo display_name)
        return archivo.display_name
    elif hasattr(archivo, 'name') and archivo.name:
        # File de Google Files API (campo name es "files/abc123")
        nombre_simple = archivo.name.split('/')[-1] if '/' in archivo.name else archivo.name
        return f"archivo_{nombre_simple}"
    else:
        # Fallback genérico
        return f"archivo_{index + 1}"


async def procesar_archivos_para_gemini(archivos_directos: List[Any]) -> List[Any]:
    """
    Procesa archivos para convertirlos al formato esperado por Gemini (NUEVO SDK v3.0).

    NUEVO v3.0 - FILES API:
    - Detecta objetos File de Google Files API y crea referencias types.Part
    - Convierte UploadFile a formato inline con types.Part.from_bytes
    - Determina MIME type correcto según extensión

    RESPONSABILIDAD (SRP):
    - Convierte archivos a objetos types.Part del nuevo SDK

    Args:
        archivos_directos: Lista de archivos (File de Google, UploadFile, bytes o dict)

    Returns:
        List[types.Part]: Archivos en formato Gemini SDK v3.0
    """
    from google.genai import types

    archivos_procesados = []

    for i, archivo_elemento in enumerate(archivos_directos):
        try:
            part_objeto = None

            # Caso 1: Es un objeto File de Google Files API (desde cache) - NUEVO v3.0
            if hasattr(archivo_elemento, 'uri') and hasattr(archivo_elemento, 'mime_type'):
                # Crear referencia de Files API usando types.Part
                part_objeto = types.Part(
                    file_data=types.FileData(
                        mime_type=archivo_elemento.mime_type,
                        file_uri=archivo_elemento.uri
                    )
                )
                nombre_archivo = obtener_nombre_archivo(archivo_elemento, i)
                logger.info(f" Archivo {i+1} reutilizado desde Files API: {nombre_archivo}")

            # Caso 2: Es bytes directamente
            elif isinstance(archivo_elemento, bytes):
                part_objeto = types.Part.from_bytes(
                    data=archivo_elemento,
                    mime_type="application/octet-stream"
                )
                logger.debug(f"Archivo {i+1} convertido desde bytes")

            # Caso 3: Ya es un dict con formato correcto (legacy - convertir a Part)
            elif isinstance(archivo_elemento, dict) and "mime_type" in archivo_elemento:
                if "file_uri" in archivo_elemento:
                    # Es referencia de Files API
                    part_objeto = types.Part(
                        file_data=types.FileData(
                            mime_type=archivo_elemento["mime_type"],
                            file_uri=archivo_elemento["file_uri"]
                        )
                    )
                elif "data" in archivo_elemento:
                    # Es datos inline
                    part_objeto = types.Part.from_bytes(
                        data=archivo_elemento["data"],
                        mime_type=archivo_elemento["mime_type"]
                    )
                logger.debug(f"Archivo {i+1} convertido desde dict legacy")

            # Caso 4: Es UploadFile (starlette)
            elif hasattr(archivo_elemento, 'read'):
                await archivo_elemento.seek(0)
                archivo_bytes = await archivo_elemento.read()

                # Determinar MIME type por extensión
                nombre_archivo = obtener_nombre_archivo(archivo_elemento, i)
                extension = nombre_archivo.split('.')[-1].lower() if '.' in nombre_archivo else ''

                mime_type_map = {
                    'pdf': 'application/pdf',
                    'jpg': 'image/jpeg',
                    'jpeg': 'image/jpeg',
                    'png': 'image/png',
                    'gif': 'image/gif',
                    'bmp': 'image/bmp',
                    'tiff': 'image/tiff',
                    'tif': 'image/tiff',
                    'webp': 'image/webp'
                }
                mime_type = mime_type_map.get(extension, 'application/octet-stream')

                part_objeto = types.Part.from_bytes(
                    data=archivo_bytes,
                    mime_type=mime_type
                )
                logger.debug(f"Archivo {i+1} ({nombre_archivo}): {len(archivo_bytes):,} bytes, {mime_type}")

            else:
                logger.warning(f" Tipo de archivo desconocido: {type(archivo_elemento)}")
                # No intentar convertir a bytes si no sabemos qué es
                continue

            if part_objeto:
                archivos_procesados.append(part_objeto)

        except Exception as e:
            logger.error(f" Error procesando archivo {i+1} para Gemini: {e}")
            logger.exception(e)
            continue

    logger.info(f" Archivos procesados para Gemini: {len(archivos_procesados)}/{len(archivos_directos)}")
    return archivos_procesados