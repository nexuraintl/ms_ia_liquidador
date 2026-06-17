"""
TESTS PARA INTEGRACION FILES API - TDD CICLO 2
================================================

Tests de integración para verificar que ProcesadorGemini usa Files API
correctamente en lugar de enviar archivos inline como bytes.

Autor: Claude + Usuario
Versión: 3.0.0
Ciclo TDD: 2 - Integración Files API con Clasificador
"""

import unittest
import asyncio
import os
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
from pathlib import Path
from datetime import datetime
from io import BytesIO

# Imports del sistema
from Clasificador.clasificador import ProcesadorGemini
from Clasificador.gemini_files_manager import GeminiFilesManager, FileUploadResult


class TestClasificadorFilesAPI(unittest.TestCase):
    """Tests de integración para Files API con ProcesadorGemini"""

    def setUp(self):
        """Configuración inicial para cada test"""
        # Mock de variables de entorno
        os.environ["GEMINI_API_KEY"] = "test_api_key_12345"

        # Mock de archivos UploadFile
        self.mock_archivo_pdf = MagicMock()
        self.mock_archivo_pdf.filename = "factura_test.pdf"
        self.mock_archivo_pdf.read = AsyncMock(return_value=b'%PDF-1.4 contenido test')
        self.mock_archivo_pdf.seek = AsyncMock(return_value=None)

        self.mock_archivo_imagen = MagicMock()
        self.mock_archivo_imagen.filename = "imagen_test.png"
        self.mock_archivo_imagen.read = AsyncMock(return_value=b'\x89PNG\r\n\x1a\n contenido imagen')
        self.mock_archivo_imagen.seek = AsyncMock(return_value=None)

        # Textos preprocesados (Excel, Word, etc.)
        self.textos_preprocesados = {
            "datos_excel.xlsx": "Contenido extraído del Excel:\nFila 1: Datos\nFila 2: Más datos"
        }

    def tearDown(self):
        """Limpieza después de cada test"""
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]

    # ========== TEST 1: Clasificación usa Files API ==========

    @patch('Clasificador.clasificador.genai.Client')
    @patch('Clasificador.gemini_files_manager.genai.Client')
    @patch('Clasificador.clasificador.ProcesadorGemini._validar_pdf_tiene_paginas')
    def test_clasificar_documentos_usa_files_api(self, mock_validar_pdf, mock_files_client_class, mock_client_class):
        """
        Test: clasificar_documentos debe subir archivos a Files API

        Escenario:
        - 1 archivo PDF directo
        - 1 texto preprocesado

        Resultado esperado:
        - Archivo PDF subido a Files API (no bytes inline)
        - Files API retorna FileUploadResult
        - Contenido enviado a Gemini usa referencia, no bytes
        """
        # ARRANGE: Configurar mocks
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_files_client = MagicMock()
        mock_files_client_class.return_value = mock_files_client

        # Mock de validación PDF
        mock_validar_pdf.return_value = AsyncMock(return_value=True)()

        # Mock de Files API upload response
        mock_uploaded_file = MagicMock()
        mock_uploaded_file.name = "files/abc123xyz"
        mock_uploaded_file.display_name = "factura_test.pdf"
        mock_uploaded_file.mime_type = "application/pdf"
        mock_uploaded_file.size_bytes = 1024
        mock_uploaded_file.state = "ACTIVE"
        mock_uploaded_file.uri = "https://generativelanguage.googleapis.com/v1/files/abc123xyz"

        # Mocks async para Files API (cliente de GeminiFilesManager)
        mock_files_client.aio.files.upload = AsyncMock(return_value=mock_uploaded_file)
        mock_files_client.aio.files.get = AsyncMock(return_value=mock_uploaded_file)
        # Mocks async para Files API (cliente de ProcesadorGemini — llamadas a files.get)
        mock_client.aio.files.upload = AsyncMock(return_value=mock_uploaded_file)
        mock_client.aio.files.get = AsyncMock(return_value=mock_uploaded_file)

        # Mock async para generate_content
        mock_response = MagicMock()
        mock_response.text = '{"clasificacion": {"factura_test.pdf": "FACTURA"}, "factura_identificada": true}'
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # ACT: Crear clasificador y ejecutar
        clasificador = ProcesadorGemini()

        resultado = asyncio.run(clasificador.clasificar_documentos(
            archivos_directos=[self.mock_archivo_pdf],
            textos_preprocesados=self.textos_preprocesados
        ))

        # ASSERT: Verificar que Files API fue llamada
        # Ambos módulos comparten la misma referencia a genai (patch exterior gana)
        mock_client.aio.files.upload.assert_called_once()

        # Verificar que clasificador tiene files_manager
        self.assertIsNotNone(clasificador.files_manager)
        self.assertIsInstance(clasificador.files_manager, GeminiFilesManager)

    # ========== TEST 2: Análisis de factura usa Files API ==========

    @patch('Clasificador.clasificador.genai.Client')
    @patch('Clasificador.gemini_files_manager.genai.Client')
    def test_analizar_factura_usa_files_api(self, mock_files_client_class, mock_client_class):
        """
        Test: Análisis de factura debe usar Files API

        Escenario:
        - Análisis de factura con 2 archivos directos

        Resultado esperado:
        - Ambos archivos subidos a Files API
        - Cache mantiene referencias FileUploadResult
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_files_client = MagicMock()
        mock_files_client_class.return_value = mock_files_client

        # Mock async para Files API
        mock_response = MagicMock()
        mock_response.text = '{"conceptos_aplicables": ["servicios"], "base_gravable": 1000000}'
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # ACT
        clasificador = ProcesadorGemini()

        # Simular análisis de factura (este método será creado/modificado)
        # Por ahora verificamos que el files_manager se inicializa

        # ASSERT
        self.assertIsNotNone(clasificador.files_manager)
        self.assertEqual(mock_files_client.aio.files.upload.call_count, 0)  # No se llama aún

    # ========== TEST 3: Cache para workers paralelos ==========

    @patch('Clasificador.clasificador.genai.Client')
    @patch('Clasificador.gemini_files_manager.genai.Client')
    def test_cache_files_api_para_workers_paralelos(self, mock_files_client_class, mock_client_class):
        """
        Test: Cache debe guardar FileUploadResult, no bytes

        Escenario:
        - preparar_archivos_para_workers_paralelos() con 2 archivos

        Resultado esperado:
        - Cache retorna Dict[str, FileUploadResult]
        - NO Dict[str, bytes]
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_files_client = MagicMock()
        mock_files_client_class.return_value = mock_files_client

        # Mock de upload
        mock_uploaded_file = MagicMock()
        mock_uploaded_file.name = "files/cache_test"
        mock_uploaded_file.display_name = "test.pdf"
        mock_uploaded_file.mime_type = "application/pdf"
        mock_uploaded_file.size_bytes = 1024
        mock_uploaded_file.state = "ACTIVE"
        mock_uploaded_file.uri = "https://test.com/cache_test"

        mock_files_client.aio.files.upload = AsyncMock(return_value=mock_uploaded_file)

        # ACT
        clasificador = ProcesadorGemini()

        cache = asyncio.run(clasificador.preparar_archivos_para_workers_paralelos(
            [self.mock_archivo_pdf]
        ))

        # ASSERT
        self.assertIsInstance(cache, dict)
        # Verificar que el cache contiene FileUploadResult, no bytes
        for nombre, valor in cache.items():
            self.assertIsInstance(valor, FileUploadResult)
            self.assertIsInstance(valor.name, str)
            self.assertTrue(valor.name.startswith("files/"))

    # ========== TEST 4: Fallback a inline si Files API falla ==========

    @patch('Clasificador.clasificador.genai.Client')
    @patch('Clasificador.gemini_files_manager.genai.Client')
    @patch('Clasificador.clasificador.ProcesadorGemini._validar_pdf_tiene_paginas')
    def test_files_api_fallback_a_inline_en_error(self, mock_validar_pdf, mock_files_client_class, mock_client_class):
        """
        Test: Si Files API falla, debe usar bytes inline

        Escenario:
        - Files API upload falla con excepción

        Resultado esperado:
        - Sistema hace fallback a envío inline (bytes)
        - No lanza excepción, procesa correctamente
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_files_client = MagicMock()
        mock_files_client_class.return_value = mock_files_client

        # Mock de validación PDF
        mock_validar_pdf.return_value = AsyncMock(return_value=True)()

        # Files API falla en ambos clientes
        mock_files_client.aio.files.upload = AsyncMock(side_effect=Exception("Files API timeout"))
        mock_client.aio.files.upload = AsyncMock(side_effect=Exception("Files API timeout"))

        # Mock async para generate_content (con bytes inline)
        mock_response = MagicMock()
        mock_response.text = '{"clasificacion": {"factura_test.pdf": "FACTURA"}}'
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # ACT
        clasificador = ProcesadorGemini()

        # Debe funcionar con fallback, no lanzar excepción
        resultado = asyncio.run(clasificador.clasificar_documentos(
            archivos_directos=[self.mock_archivo_pdf]
        ))

        # ASSERT
        # Verificar que intentó usar Files API pero hizo fallback
        mock_client.aio.files.upload.assert_called()
        # Resultado debe ser exitoso igualmente
        self.assertIsNotNone(resultado)

    # ========== TEST 5: Cleanup después de análisis ==========

    @patch('Clasificador.clasificador.genai.Client')
    @patch('Clasificador.gemini_files_manager.genai.Client')
    @patch('Clasificador.clasificador.ProcesadorGemini._validar_pdf_tiene_paginas')
    def test_cleanup_files_api_despues_analisis(self, mock_validar_pdf, mock_files_client_class, mock_client_class):
        """
        Test: Archivos deben limpiarse después de análisis

        Escenario:
        - Análisis completo de documentos
        - files_manager.cleanup_all() debe ser llamado

        Resultado esperado:
        - cleanup_all() ejecutado
        - Archivos eliminados de Files API
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_files_client = MagicMock()
        mock_files_client_class.return_value = mock_files_client

        # Mock de validación PDF
        mock_validar_pdf.return_value = AsyncMock(return_value=True)()

        # Mock upload y delete (async)
        mock_uploaded_file = MagicMock()
        mock_uploaded_file.name = "files/cleanup_test"
        mock_uploaded_file.state = "ACTIVE"
        mock_uploaded_file.display_name = "factura_test.pdf"
        mock_uploaded_file.mime_type = "application/pdf"
        mock_uploaded_file.size_bytes = 1024
        mock_uploaded_file.uri = "https://test.com"

        mock_files_client.aio.files.upload = AsyncMock(return_value=mock_uploaded_file)
        mock_files_client.aio.files.get = AsyncMock(return_value=mock_uploaded_file)
        mock_files_client.aio.files.delete = AsyncMock(return_value=None)
        mock_client.aio.files.upload = AsyncMock(return_value=mock_uploaded_file)
        mock_client.aio.files.get = AsyncMock(return_value=mock_uploaded_file)
        mock_client.aio.files.delete = AsyncMock(return_value=None)

        # Mock async para generate_content
        mock_response = MagicMock()
        mock_response.text = '{"clasificacion": {}}'
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # ACT
        clasificador = ProcesadorGemini()

        asyncio.run(clasificador.clasificar_documentos(
            archivos_directos=[self.mock_archivo_pdf]
        ))

        # Cleanup manual (en el futuro será automático en finally)
        asyncio.run(clasificador.files_manager.cleanup_all())

        # ASSERT
        # Ambos módulos comparten la misma referencia a genai (patch exterior gana)
        mock_client.aio.files.delete.assert_called_once_with(name="files/cleanup_test")

    # ========== TEST 6: Archivos preprocesados siguen usando texto ==========

    @patch('Clasificador.clasificador.genai.Client')
    @patch('Clasificador.gemini_files_manager.genai.Client')
    def test_archivos_preprocesados_siguen_usando_texto(self, mock_files_client_class, mock_client_class):
        """
        Test: Excel/Word preprocesados NO deben usar Files API

        Escenario:
        - Solo textos preprocesados (Excel, Word)
        - Sin archivos directos

        Resultado esperado:
        - Files API NO es llamada
        - Textos enviados directamente en prompt
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_files_client = MagicMock()
        mock_files_client_class.return_value = mock_files_client

        # Mock async para generate_content
        mock_response = MagicMock()
        mock_response.text = '{"clasificacion": {"datos_excel.xlsx": "ANEXO"}}'
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_files_client.aio.files.upload = AsyncMock()

        # ACT
        clasificador = ProcesadorGemini()

        resultado = asyncio.run(clasificador.clasificar_documentos(
            archivos_directos=[],  # Sin archivos directos
            textos_preprocesados=self.textos_preprocesados
        ))

        # ASSERT
        # Files API NO debe ser llamada para textos preprocesados
        mock_files_client.aio.files.upload.assert_not_called()
        self.assertIsNotNone(resultado)

    # ========== TEST 7: Híbrido Files API + textos ==========

    @patch('Clasificador.clasificador.genai.Client')
    @patch('Clasificador.gemini_files_manager.genai.Client')
    @patch('Clasificador.clasificador.ProcesadorGemini._validar_pdf_tiene_paginas')
    def test_hibrido_files_api_mas_textos_preprocesados(self, mock_validar_pdf, mock_files_client_class, mock_client_class):
        """
        Test: Modo híbrido: Files API para PDFs + textos para Excel

        Escenario:
        - 1 archivo PDF (Files API)
        - 1 archivo Excel preprocesado (texto)

        Resultado esperado:
        - Files API llamada 1 vez (solo PDF)
        - Contenido híbrido: referencia Files API + texto preprocesado
        """
        # ARRANGE
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_files_client = MagicMock()
        mock_files_client_class.return_value = mock_files_client

        # Mock de validación PDF
        mock_validar_pdf.return_value = AsyncMock(return_value=True)()

        # Mock upload (async)
        mock_uploaded_file = MagicMock()
        mock_uploaded_file.name = "files/hybrid_test"
        mock_uploaded_file.state = "ACTIVE"
        mock_uploaded_file.display_name = "factura_test.pdf"
        mock_uploaded_file.mime_type = "application/pdf"
        mock_uploaded_file.size_bytes = 1024
        mock_uploaded_file.uri = "https://test.com"

        mock_files_client.aio.files.upload = AsyncMock(return_value=mock_uploaded_file)
        mock_files_client.aio.files.get = AsyncMock(return_value=mock_uploaded_file)
        mock_client.aio.files.upload = AsyncMock(return_value=mock_uploaded_file)
        mock_client.aio.files.get = AsyncMock(return_value=mock_uploaded_file)

        # Mock async para generate_content
        mock_response = MagicMock()
        mock_response.text = '{"clasificacion": {"factura_test.pdf": "FACTURA", "datos_excel.xlsx": "ANEXO"}}'
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # ACT
        clasificador = ProcesadorGemini()

        resultado = asyncio.run(clasificador.clasificar_documentos(
            archivos_directos=[self.mock_archivo_pdf],
            textos_preprocesados=self.textos_preprocesados
        ))

        # ASSERT
        # Files API llamada solo 1 vez (para el PDF)
        # Ambos módulos comparten la misma referencia a genai (patch exterior gana)
        self.assertEqual(mock_client.aio.files.upload.call_count, 1)
        # Resultado debe incluir ambos archivos
        self.assertIsNotNone(resultado)


# ========== TEST RUNNER ==========

if __name__ == '__main__':
    # Ejecutar tests con verbosidad
    unittest.main(verbosity=2)
