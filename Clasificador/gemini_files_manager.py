"""GEMINI FILES MANAGER - Gestor de Google Files API
==================================================

SRP: Responsabilidad única - gestionar archivos en Google Files API
OCP: Extensible para nuevas estrategias de upload
DIP: Depende de abstracción de cliente Gemini

Autor: Claude + Usuario
Versión: 3.0.0
Ciclo TDD: 1 - Implementación Básica
"""

import os
import asyncio
import io
import logging
import mimetypes
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from google import genai
from fastapi import UploadFile

logger = logging.getLogger(__name__)


@dataclass
class FileUploadResult:
    """Resultado de upload de archivo a Files API."""
    name: str               # Nombre en Files API (files/abc123)
    display_name: str       # Nombre original del archivo
    mime_type: str          # Tipo MIME
    size_bytes: int         # Tamaño en bytes
    state: str              # PROCESSING, ACTIVE, FAILED
    uri: str                # URI del archivo en Files API
    upload_timestamp: str   # Timestamp de subida


class GeminiFilesManager:
    """Gestor de archivos para Google Files API.

    Responsabilidades (SRP):
    - Upload de archivos a Files API
    - Espera a estado ACTIVE
    - Obtención de metadata
    - Eliminación de archivos

    NO responsable de:
    - Generar contenido con Gemini (eso es de ProcesadorGemini)
    - Validar archivos PDF (eso es de clasificador.py)
    - Cache de archivos (eso es de preparar_archivos_para_workers_paralelos)
    """

    def __init__(self, api_key: str):
        """Inicializa gestor con nuevo SDK google-genai.

        Args:
            api_key: API key de Google Gemini
        """
        self.client = genai.Client(api_key=api_key)
        self.uploaded_files: Dict[str, FileUploadResult] = {}

        logger.info("GeminiFilesManager inicializado con nuevo SDK google-genai")

    async def upload_file(
        self,
        archivo: UploadFile,
        wait_for_active: bool = True,
        timeout_seconds: int = 300
    ) -> FileUploadResult:
        """Sube archivo a Google Files API.

        Args:
            archivo: UploadFile de FastAPI
            wait_for_active: Si esperar a estado ACTIVE
            timeout_seconds: Timeout máximo de espera

        Returns:
            FileUploadResult con información del archivo subido

        Raises:
            ValueError: Si falla upload o timeout
        """
        # Verificar cache antes de subir
        if archivo.filename in self.uploaded_files:
            logger.info(f"Archivo ya en Files API (cache hit): {archivo.filename}")
            return self.uploaded_files[archivo.filename]

        try:
            # PASO 1: Subir directamente desde el buffer en memoria. El SDK acepta
            # cualquier stream seekable; escribir un temporal (que en Cloud Run es RAM)
            # y releerlo duplicaba el trabajo por cada archivo.
            logger.info(f"Subiendo archivo a Files API: {archivo.filename}")
            uploaded_file = await self.client.aio.files.upload(
                file=await self._stream_subida(archivo),
                config={
                    "display_name": archivo.filename,
                    "mime_type": self._mime_type(archivo)
                }
            )

            # PASO 2: Esperar a estado ACTIVE si se solicita
            if wait_for_active:
                uploaded_file = await self._wait_for_active_state(
                    uploaded_file,
                    timeout_seconds
                )

            # PASO 3: Crear resultado
            result = FileUploadResult(
                name=uploaded_file.name,
                display_name=archivo.filename,
                mime_type=uploaded_file.mime_type,
                size_bytes=uploaded_file.size_bytes,
                state=uploaded_file.state,
                uri=uploaded_file.uri,
                upload_timestamp=datetime.now().isoformat()
            )

            # PASO 4: Guardar en cache interno
            self.uploaded_files[archivo.filename] = result

            logger.info(f"Upload exitoso: {archivo.filename} → {uploaded_file.name}")
            return result

        except Exception as e:
            logger.error(f"Error subiendo archivo {archivo.filename}: {e}")
            raise

    async def _stream_subida(self, archivo: UploadFile) -> io.IOBase:
        """Devuelve el stream seekable que se entrega al SDK, rebobinado al inicio.

        Args:
            archivo: UploadFile de FastAPI

        Returns:
            El buffer subyacente si es un stream estandar; si no, una copia en memoria.
        """
        await archivo.seek(0)
        if isinstance(getattr(archivo, "file", None), io.IOBase):
            return archivo.file
        return io.BytesIO(await archivo.read())

    @staticmethod
    def _mime_type(archivo: UploadFile) -> str:
        """Resuelve el MIME type, obligatorio al subir desde un stream.

        Args:
            archivo: UploadFile de FastAPI

        Returns:
            MIME por extension del nombre; si no se reconoce, application/octet-stream.
        """
        adivinado, _ = mimetypes.guess_type(archivo.filename or "")
        return adivinado or "application/octet-stream"

    async def _wait_for_active_state(
        self,
        file_obj,
        timeout_seconds: int = 300
    ):
        """Espera a que archivo llegue a estado ACTIVE.

        Args:
            file_obj: Objeto File de Files API
            timeout_seconds: Timeout máximo en segundos

        Returns:
            File object con estado ACTIVE

        Raises:
            ValueError: Si timeout o error en procesamiento
        """
        start_time = datetime.now()

        while file_obj.state == "PROCESSING":
            # Verificar timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout_seconds:
                raise ValueError(f"Timeout esperando estado ACTIVE: {timeout_seconds}s excedidos")

            # Esperar antes de siguiente polling
            await asyncio.sleep(2)

            # Obtener estado actualizado
            try:
                file_obj = await self.client.aio.files.get(name=file_obj.name)
            except Exception as e:
                raise ValueError(f"Error consultando estado del archivo: {str(e)}")

        if file_obj.state == "FAILED":
            raise ValueError(f"Procesamiento de archivo falló: {file_obj.name}")

        logger.info(f"Archivo ACTIVE: {file_obj.name}")
        return file_obj

    async def get_file_metadata(self, file_name: str):
        """Obtiene metadata de archivo en Files API.

        Args:
            file_name: Nombre del archivo en Files API (files/abc123)

        Returns:
            File object con metadata
        """
        try:
            file_obj = await self.client.aio.files.get(name=file_name)
            logger.debug(f"Metadata obtenida: {file_name}")
            return file_obj
        except Exception as e:
            logger.error(f"Error obteniendo metadata de {file_name}: {e}")
            raise

    async def delete_file(self, file_name: str) -> bool:
        """Elimina archivo de Files API.

        Args:
            file_name: Nombre del archivo en Files API (files/abc123)

        Returns:
            True si eliminado exitosamente, False si error
        """
        try:
            await self.client.aio.files.delete(name=file_name)

            # Remover del cache interno
            for filename, file_result in list(self.uploaded_files.items()):
                if file_result.name == file_name:
                    del self.uploaded_files[filename]
                    break

            logger.info(f"Archivo eliminado: {file_name}")
            return True

        except Exception as e:
            logger.warning(f"Error eliminando archivo {file_name}: {e}")
            return False

    async def cleanup_all(self, ignore_errors: bool = True):
        """Elimina todos los archivos subidos a Files API en paralelo.

        CRÍTICO: Usar en finally del endpoint para evitar acumulación.

        Args:
            ignore_errors: Si ignorar errores de archivos ya eliminados
        """
        logger.info(f"Iniciando cleanup de {len(self.uploaded_files)} archivos")

        archivos_a_eliminar = list(self.uploaded_files.items())

        if archivos_a_eliminar:
            # Lanzar todos los deletes en paralelo en lugar de secuencial.
            # return_exceptions=True evita que un fallo cancele los demas.
            resultados = await asyncio.gather(
                *[self.delete_file(file_result.name) for _, file_result in archivos_a_eliminar],
                return_exceptions=True
            )

            exitosos = sum(1 for r in resultados if r is True)
            errores = []
            for (nombre, _), resultado in zip(archivos_a_eliminar, resultados):
                if isinstance(resultado, Exception):
                    errores.append(f"{nombre}: {str(resultado)}")
                    if not ignore_errors:
                        raise resultado
                elif resultado is False:
                    errores.append(f"{nombre}: fallo al eliminar")

            logger.info(f"Cleanup completado: {exitosos} exitosos, {len(errores)} errores")

            if errores and ignore_errors:
                logger.warning(f"Errores durante cleanup (ignorados): {errores}")

        # Limpiar cache interno
        self.uploaded_files.clear()

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - auto cleanup."""
        await self.cleanup_all(ignore_errors=True)
        return False
