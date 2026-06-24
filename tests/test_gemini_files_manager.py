"""
TESTS PARA GEMINI FILES MANAGER - TDD CICLO 1
==============================================

Tests unitarios para GeminiFilesManager siguiendo metodología TDD.

Autor: Claude + Usuario
Versión: 3.0.0
Ciclo TDD: 1 - GeminiFilesManager Básico
"""

import unittest
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
from datetime import datetime
from io import BytesIO

from Clasificador.gemini_files_manager import GeminiFilesManager, FileUploadResult


class TestGeminiFilesManager(unittest.TestCase):
    """Tests unitarios para GeminiFilesManager"""

    def setUp(self):
        """Configuración inicial para cada test"""
        self.api_key = "test_api_key_12345"
        self.mock_client = MagicMock()

        # Mock de archivo UploadFile de FastAPI
        self.mock_upload_file = MagicMock()
        self.mock_upload_file.filename = "factura_test.pdf"
        self.mock_upload_file.read = AsyncMock(return_value=b'%PDF-1.4 contenido test')
        self.mock_upload_file.seek = AsyncMock(return_value=None)

    def tearDown(self):
        """Limpieza después de cada test"""
        pass

    # ========== TEST 1: Upload Exitoso ==========

    @patch('Clasificador.gemini_files_manager.genai.Client')
    def test_upload_file_success(self, mock_client_class):
        """
        Test: Upload exitoso de archivo PDF a Files API

        Escenario:
        - Archivo PDF válido
        - Upload exitoso con estado ACTIVE inmediato

        Resultado esperado:
        - FileUploadResult con datos correctos
        - Archivo guardado en cache interno
        """
        # ARRANGE: Configurar mocks
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock de Files API upload response
        mock_uploaded_file = MagicMock()
        mock_uploaded_file.name = "files/abc123xyz"
        mock_uploaded_file.display_name = "factura_test.pdf"
        mock_uploaded_file.mime_type = "application/pdf"
        mock_uploaded_file.size_bytes = 1024
        mock_uploaded_file.state = "ACTIVE"
        mock_uploaded_file.uri = "https://generativelanguage.googleapis.com/v1/files/abc123xyz"

        # SDK 1.x: client.aio.files.upload es async
        mock_client.aio.files.upload = AsyncMock(return_value=mock_uploaded_file)

        # ACT: Ejecutar upload
        manager = GeminiFilesManager(api_key=self.api_key)
        result = asyncio.run(manager.upload_file(self.mock_upload_file, wait_for_active=False))

        # ASSERT: Verificar resultado
        self.assertIsInstance(result, FileUploadResult)
        self.assertEqual(result.name, "files/abc123xyz")
        self.assertEqual(result.display_name, "factura_test.pdf")
        self.assertEqual(result.state, "ACTIVE")
        self.assertIn("factura_test.pdf", manager.uploaded_files)

        # Verificar que upload fue llamado
        mock_client.aio.files.upload.assert_called_once()

    # ========== TEST 2: Espera a Estado ACTIVE ==========

    @patch('Clasificador.gemini_files_manager.genai.Client')
    def test_upload_file_wait_for_active_state(self, mock_client_class):
        """
        Test: Espera a que archivo pase de PROCESSING a ACTIVE

        Escenario:
        - Archivo se sube pero está en estado PROCESSING
        - Después de polling, pasa a ACTIVE

        Resultado esperado:
        - Función espera hasta ACTIVE
        - Retorna FileUploadResult con estado ACTIVE
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Primera llamada upload: PROCESSING; polling get: ACTIVE
        mock_file_processing = MagicMock()
        mock_file_processing.name = "files/xyz789"
        mock_file_processing.state = "PROCESSING"
        mock_file_processing.display_name = "factura_test.pdf"
        mock_file_processing.mime_type = "application/pdf"
        mock_file_processing.size_bytes = 2048
        mock_file_processing.uri = "https://generativelanguage.googleapis.com/v1/files/xyz789"

        mock_file_active = MagicMock()
        mock_file_active.name = "files/xyz789"
        mock_file_active.state = "ACTIVE"
        mock_file_active.display_name = "factura_test.pdf"
        mock_file_active.mime_type = "application/pdf"
        mock_file_active.size_bytes = 2048
        mock_file_active.uri = "https://generativelanguage.googleapis.com/v1/files/xyz789"

        mock_client.aio.files.upload = AsyncMock(return_value=mock_file_processing)
        mock_client.aio.files.get = AsyncMock(return_value=mock_file_active)

        # ACT
        manager = GeminiFilesManager(api_key=self.api_key)
        result = asyncio.run(manager.upload_file(self.mock_upload_file, wait_for_active=True))

        # ASSERT
        self.assertEqual(result.state, "ACTIVE")
        # Verificar que get fue llamado (polling)
        mock_client.aio.files.get.assert_called()

    # ========== TEST 3: Timeout en PROCESSING ==========

    @patch('Clasificador.gemini_files_manager.genai.Client')
    def test_upload_file_timeout_processing(self, mock_client_class):
        """
        Test: Timeout si archivo nunca llega a ACTIVE

        Escenario:
        - Archivo permanece en PROCESSING indefinidamente
        - Timeout configurado de 5 segundos

        Resultado esperado:
        - Lanza ValueError con mensaje de timeout
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Siempre retorna PROCESSING
        mock_file = MagicMock()
        mock_file.state = "PROCESSING"
        mock_file.name = "files/stuck123"

        mock_client.aio.files.upload = AsyncMock(return_value=mock_file)
        mock_client.aio.files.get = AsyncMock(return_value=mock_file)

        # ACT & ASSERT
        manager = GeminiFilesManager(api_key=self.api_key)

        with self.assertRaises(ValueError) as context:
            # Timeout corto para test rápido
            asyncio.run(manager.upload_file(
                self.mock_upload_file,
                wait_for_active=True,
                timeout_seconds=5
            ))

        # Verificar mensaje de error
        self.assertIn("timeout", str(context.exception).lower())

    # ========== TEST 4: Obtener Metadata ==========

    @patch('Clasificador.gemini_files_manager.genai.Client')
    def test_get_file_metadata_success(self, mock_client_class):
        """
        Test: Obtener metadata de archivo subido

        Escenario:
        - Archivo ya subido en Files API
        - Solicitar metadata

        Resultado esperado:
        - Retorna metadata completa del archivo
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_file_metadata = MagicMock()
        mock_file_metadata.name = "files/meta123"
        mock_file_metadata.display_name = "factura_meta.pdf"
        mock_file_metadata.size_bytes = 4096
        mock_file_metadata.mime_type = "application/pdf"
        mock_file_metadata.state = "ACTIVE"

        mock_client.aio.files.get = AsyncMock(return_value=mock_file_metadata)

        # ACT
        manager = GeminiFilesManager(api_key=self.api_key)
        metadata = asyncio.run(manager.get_file_metadata("files/meta123"))

        # ASSERT
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.name, "files/meta123")
        mock_client.aio.files.get.assert_called_once_with(name="files/meta123")

    # ========== TEST 5: Eliminar Archivo Exitoso ==========

    @patch('Clasificador.gemini_files_manager.genai.Client')
    def test_delete_file_success(self, mock_client_class):
        """
        Test: Eliminación exitosa de archivo

        Escenario:
        - Archivo existe en Files API
        - Llamada a delete exitosa

        Resultado esperado:
        - Retorna True
        - Archivo removido del cache interno
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_client.aio.files.delete = AsyncMock(return_value=None)

        # ACT
        manager = GeminiFilesManager(api_key=self.api_key)
        # Simular archivo en cache
        manager.uploaded_files["test.pdf"] = FileUploadResult(
            name="files/delete123",
            display_name="test.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            state="ACTIVE",
            uri="https://test.com",
            upload_timestamp=datetime.now().isoformat()
        )

        result = asyncio.run(manager.delete_file("files/delete123"))

        # ASSERT
        self.assertTrue(result)
        mock_client.aio.files.delete.assert_called_once_with(name="files/delete123")

    # ========== TEST 6: Manejo de NotFound ==========

    @patch('Clasificador.gemini_files_manager.genai.Client')
    def test_delete_file_handles_not_found(self, mock_client_class):
        """
        Test: Manejo de archivo no encontrado al eliminar

        Escenario:
        - Intentar eliminar archivo que no existe
        - Files API lanza excepción

        Resultado esperado:
        - No lanza excepción (manejo graceful)
        - Log de warning
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Simular NotFoundError
        mock_client.aio.files.delete = AsyncMock(side_effect=Exception("File not found"))

        # ACT
        manager = GeminiFilesManager(api_key=self.api_key)
        result = asyncio.run(manager.delete_file("files/noexiste"))

        # ASSERT
        # No debe lanzar excepción, retorna False
        self.assertFalse(result)

    # ========== TEST 7: Upload Múltiples Archivos Paralelo ==========

    @patch('Clasificador.gemini_files_manager.genai.Client')
    def test_upload_multiple_files_in_parallel(self, mock_client_class):
        """
        Test: Upload de múltiples archivos en paralelo

        Escenario:
        - 3 archivos a subir simultáneamente
        - Todos exitosos

        Resultado esperado:
        - 3 FileUploadResult
        - Cache con 3 archivos
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock de 3 archivos
        archivos = []
        for i in range(3):
            archivo_mock = MagicMock()
            archivo_mock.filename = f"archivo_{i}.pdf"
            archivo_mock.read = AsyncMock(return_value=b'%PDF contenido')
            archivo_mock.seek = AsyncMock(return_value=None)
            archivos.append(archivo_mock)

        # Mock de respuestas de upload (async side_effect)
        async def mock_upload_side_effect(file, config=None):
            mock_file = MagicMock()
            mock_file.name = f"files/file{config['display_name']}"
            mock_file.state = "ACTIVE"
            mock_file.display_name = config['display_name']
            mock_file.mime_type = "application/pdf"
            mock_file.size_bytes = 1024
            mock_file.uri = f"https://test.com/{config['display_name']}"
            return mock_file

        mock_client.aio.files.upload = AsyncMock(side_effect=mock_upload_side_effect)

        # ACT
        manager = GeminiFilesManager(api_key=self.api_key)

        async def upload_all():
            tasks = [manager.upload_file(archivo, wait_for_active=False) for archivo in archivos]
            return await asyncio.gather(*tasks)

        results = asyncio.run(upload_all())

        # ASSERT
        self.assertEqual(len(results), 3)
        self.assertEqual(len(manager.uploaded_files), 3)
        self.assertEqual(mock_client.aio.files.upload.call_count, 3)

    # ========== TEST 8: Tipo de Archivo Inválido ==========

    @patch('Clasificador.gemini_files_manager.genai.Client')
    def test_upload_handles_invalid_file_type(self, mock_client_class):
        """
        Test: Manejo de tipo de archivo no soportado

        Escenario:
        - Archivo .exe (no soportado por Files API)
        - Files API rechaza upload

        Resultado esperado:
        - Lanza ValueError con mensaje descriptivo
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        archivo_invalido = MagicMock()
        archivo_invalido.filename = "virus.exe"
        archivo_invalido.read = AsyncMock(return_value=b'MZ executable')
        archivo_invalido.seek = AsyncMock(return_value=None)

        # Files API rechaza
        mock_client.aio.files.upload = AsyncMock(side_effect=Exception("Unsupported file type"))

        # ACT & ASSERT
        manager = GeminiFilesManager(api_key=self.api_key)

        with self.assertRaises(Exception):
            asyncio.run(manager.upload_file(archivo_invalido, wait_for_active=False))

    # ========== TEST 9: Archivo Demasiado Grande ==========

    @patch('Clasificador.gemini_files_manager.genai.Client')
    def test_upload_handles_file_too_large(self, mock_client_class):
        """
        Test: Manejo de archivo que excede límite de 2GB

        Escenario:
        - Archivo de 3GB
        - Files API rechaza (límite 2GB)

        Resultado esperado:
        - Lanza ValueError con mensaje de límite excedido
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        archivo_grande = MagicMock()
        archivo_grande.filename = "archivo_3gb.mp4"
        archivo_grande.read = AsyncMock(return_value=b'huge file content')
        archivo_grande.seek = AsyncMock(return_value=None)

        # Files API rechaza por tamaño
        mock_client.aio.files.upload = AsyncMock(side_effect=Exception("File too large: max 2GB"))

        # ACT & ASSERT
        manager = GeminiFilesManager(api_key=self.api_key)

        with self.assertRaises(Exception) as context:
            asyncio.run(manager.upload_file(archivo_grande, wait_for_active=False))

        self.assertIn("too large", str(context.exception).lower())


# ========== TEST RUNNER ==========

if __name__ == '__main__':
    unittest.main(verbosity=2)
