"""
GEMINI FILES MANAGER - Gestor de Google Files API
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
import logging
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from google import genai
from fastapi import UploadFile

logger = logging.getLogger(__name__)


@dataclass
class FileUploadResult:
    """Resultado de upload de archivo a Files API"""
    name: str               # Nombre en Files API (files/abc123)
    display_name: str       # Nombre original del archivo
    mime_type: str          # Tipo MIME
    size_bytes: int         # Tamaño en bytes
    state: str              # PROCESSING, ACTIVE, FAILED
    uri: str                # URI del archivo en Files API
    upload_timestamp: str   # Timestamp de subida


class GeminiFilesManager:
    """
    Gestor de archivos para Google Files API.

    Responsabilidades (SRP):
    - Upload de archivos a Files API
    - Espera a estado ACTIVE
    - Obtención de metadata
    - Eliminación de archivos
    - Gestión de archivos temporales

    NO responsable de:
    - Generar contenido con Gemini (eso es de ProcesadorGemini)
    - Validar archivos PDF (eso es de clasificador.py)
    - Cache de archivos (eso es de preparar_archivos_para_workers_paralelos)
    """

    def __init__(self, api_key: str):
        """
        Inicializa gestor con nuevo SDK google-genai.

        Args:
            api_key: API key de Google Gemini
        """
        self.client = genai.Client(api_key=api_key)
        self.uploaded_files: Dict[str, FileUploadResult] = {}
        self.temp_files: List[Path] = []  # Para cleanup

        logger.info("GeminiFilesManager inicializado con nuevo SDK google-genai")

    async def upload_file(
        self,
        archivo: UploadFile,
        wait_for_active: bool = True,
        timeout_seconds: int = 300
    ) -> FileUploadResult:
        """
        Sube archivo a Google Files API.

        Args:
            archivo: UploadFile de FastAPI
            wait_for_active: Si esperar a estado ACTIVE
            timeout_seconds: Timeout máximo de espera

        Returns:
            FileUploadResult con información del archivo subido

        Raises:
            ValueError: Si falla upload o timeout
        """
        try:
            # PASO 1: Guardar archivo temporalmente (Files API requiere path)
            temp_path = await self._save_temp_file(archivo)

            try:
                # PASO 2: Upload usando nuevo SDK
                logger.info(f"Subiendo archivo a Files API: {archivo.filename}")

                uploaded_file = self.client.files.upload(
                    path=str(temp_path),
                    config={
                        "display_name": archivo.filename
                    }
                )

                # PASO 3: Esperar a estado ACTIVE si se solicita
                if wait_for_active:
                    uploaded_file = await self._wait_for_active_state(
                        uploaded_file,
                        timeout_seconds
                    )

                # PASO 4: Crear resultado
                result = FileUploadResult(
                    name=uploaded_file.name,
                    display_name=archivo.filename,
                    mime_type=uploaded_file.mime_type,
                    size_bytes=uploaded_file.size_bytes,
                    state=uploaded_file.state,
                    uri=uploaded_file.uri,
                    upload_timestamp=datetime.now().isoformat()
                )

                # PASO 5: Guardar en cache interno
                self.uploaded_files[archivo.filename] = result

                logger.info(f"Upload exitoso: {archivo.filename} → {uploaded_file.name}")
                return result

            finally:
                # PASO 6: Limpiar archivo temporal
                await self._cleanup_temp_file(temp_path)

        except Exception as e:
            logger.error(f"Error subiendo archivo {archivo.filename}: {e}")
            raise

    async def _save_temp_file(self, archivo: UploadFile) -> Path:
        """
        Guarda UploadFile temporalmente para upload a Files API.

        Args:
            archivo: UploadFile de FastAPI

        Returns:
            Path del archivo temporal
        """
        try:
            # Resetear puntero del archivo
            await archivo.seek(0)

            # Leer contenido
            contenido = await archivo.read()

            # Crear archivo temporal
            suffix = Path(archivo.filename).suffix
            with tempfile.NamedTemporaryFile(mode='wb', suffix=suffix, delete=False) as temp_file:
                temp_file.write(contenido)
                temp_path = Path(temp_file.name)

            # Guardar para cleanup posterior
            self.temp_files.append(temp_path)

            logger.debug(f"Archivo temporal creado: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"Error guardando archivo temporal: {e}")
            raise ValueError(f"Error guardando archivo temporal: {str(e)}")

    async def _wait_for_active_state(
        self,
        file_obj,
        timeout_seconds: int = 300
    ):
        """
        Espera a que archivo llegue a estado ACTIVE.

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
                file_obj = self.client.files.get(name=file_obj.name)
            except Exception as e:
                raise ValueError(f"Error consultando estado del archivo: {str(e)}")

        if file_obj.state == "FAILED":
            raise ValueError(f"Procesamiento de archivo falló: {file_obj.name}")

        logger.info(f"Archivo ACTIVE: {file_obj.name}")
        return file_obj

    async def _cleanup_temp_file(self, temp_path: Path):
        """
        Elimina archivo temporal.

        Args:
            temp_path: Ruta del archivo temporal
        """
        try:
            if temp_path.exists():
                temp_path.unlink()
                if temp_path in self.temp_files:
                    self.temp_files.remove(temp_path)
                logger.debug(f"Archivo temporal eliminado: {temp_path}")
        except Exception as e:
            logger.warning(f"Error eliminando archivo temporal {temp_path}: {e}")

    async def get_file_metadata(self, file_name: str):
        """
        Obtiene metadata de archivo en Files API.

        Args:
            file_name: Nombre del archivo en Files API (files/abc123)

        Returns:
            File object con metadata
        """
        try:
            file_obj = self.client.files.get(name=file_name)
            logger.debug(f"Metadata obtenida: {file_name}")
            return file_obj
        except Exception as e:
            logger.error(f"Error obteniendo metadata de {file_name}: {e}")
            raise

    async def delete_file(self, file_name: str) -> bool:
        """
        Elimina archivo de Files API.

        Args:
            file_name: Nombre del archivo en Files API (files/abc123)

        Returns:
            True si eliminado exitosamente, False si error
        """
        try:
            self.client.files.delete(name=file_name)

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
        """
        Elimina todos los archivos subidos a Files API.

        CRÍTICO: Usar en finally del endpoint para evitar acumulación.

        Args:
            ignore_errors: Si ignorar errores de archivos ya eliminados
        """
        logger.info(f"Iniciando cleanup de {len(self.uploaded_files)} archivos")

        errores = []
        exitosos = 0

        for filename, file_result in list(self.uploaded_files.items()):
            try:
                await self.delete_file(file_result.name)
                exitosos += 1
                logger.info(f"Archivo eliminado: {filename}")
            except Exception as e:
                errores.append(f"{filename}: {str(e)}")
                if not ignore_errors:
                    raise

        # Limpiar cache interno
        self.uploaded_files.clear()

        # Limpiar archivos temporales restantes
        for temp_file in list(self.temp_files):
            await self._cleanup_temp_file(temp_file)

        logger.info(f"Cleanup completado: {exitosos} exitosos, {len(errores)} errores")

        if errores and ignore_errors:
            logger.warning(f"Errores durante cleanup (ignorados): {errores}")

    async def __aenter__(self):
        """Context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - auto cleanup"""
        await self.cleanup_all(ignore_errors=True)
        return False
