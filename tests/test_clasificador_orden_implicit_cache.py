"""
TESTS - ORDEN DE CONTENIDO PARA IMPLICIT CACHING DE GEMINI 2.5
==============================================================

Verifica que el contenido enviado a Gemini se arme con los documentos
PRIMERO y el prompt al FINAL, para que el prefijo estable (documentos
identicos entre los ~8 clasificadores) habilite el implicit caching de
Gemini 2.5 y se evite re-procesar el documento N veces.

Cubre las dos rutas reordenadas:
- _llamar_gemini_hibrido        (via clasificar_documentos)
- _llamar_gemini_hibrido_factura (via _llamar_gemini_hibrido_factura)
"""

import unittest
import asyncio
import os
from unittest.mock import MagicMock, patch, AsyncMock

from Clasificador.clasificador import ProcesadorGemini


def _capturar_contents(mock_generate_content):
    """Devuelve la lista 'contents' del ultimo generate_content."""
    assert mock_generate_content.called, "generate_content no fue llamado"
    return mock_generate_content.call_args.kwargs["contents"]


class TestOrdenImplicitCache(unittest.TestCase):

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = "test_api_key_12345"

        self.mock_archivo_pdf = MagicMock()
        self.mock_archivo_pdf.filename = "factura_test.pdf"
        self.mock_archivo_pdf.read = AsyncMock(return_value=b"%PDF-1.4 contenido test")
        self.mock_archivo_pdf.seek = AsyncMock(return_value=None)

    def tearDown(self):
        os.environ.pop("GEMINI_API_KEY", None)

    def _mock_file(self):
        f = MagicMock()
        f.name = "files/abc123"
        f.display_name = "factura_test.pdf"
        f.mime_type = "application/pdf"
        f.size_bytes = 1024
        f.state = "ACTIVE"
        f.uri = "https://generativelanguage.googleapis.com/v1/files/abc123"
        return f

    @patch("Clasificador.clasificador.genai.Client")
    @patch("Clasificador.gemini_files_manager.genai.Client")
    @patch("Clasificador.clasificador.ProcesadorGemini._validar_pdf_tiene_paginas")
    def test_clasificacion_prompt_va_al_final(
        self, mock_validar_pdf, mock_files_client_class, mock_client_class
    ):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_files_client = MagicMock()
        mock_files_client_class.return_value = mock_files_client
        mock_validar_pdf.return_value = AsyncMock(return_value=True)()

        mf = self._mock_file()
        mock_files_client.aio.files.upload = AsyncMock(return_value=mf)
        mock_files_client.aio.files.get = AsyncMock(return_value=mf)
        mock_client.aio.files.upload = AsyncMock(return_value=mf)
        mock_client.aio.files.get = AsyncMock(return_value=mf)

        mock_response = MagicMock()
        mock_response.text = '{"clasificacion": {"factura_test.pdf": "FACTURA"}}'
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=1000,
            cached_content_token_count=900,
            candidates_token_count=50,
        )
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        clasificador = ProcesadorGemini()
        asyncio.run(
            clasificador.clasificar_documentos(archivos_directos=[self.mock_archivo_pdf])
        )

        contents = _capturar_contents(mock_client.aio.models.generate_content)

        self.assertGreaterEqual(len(contents), 2)
        # El ultimo elemento es el prompt (str)
        self.assertIsInstance(contents[-1], str)
        # Antes del prompt debe haber al menos un documento (Part no-str).
        prefijo = contents[:-1]
        docs_no_str = [e for e in prefijo if not isinstance(e, str)]
        self.assertGreaterEqual(len(docs_no_str), 1)
        # Los str intermedios solo pueden ser etiquetas deterministas de documento
        # (===== DOCUMENTO ADJUNTO: <nombre> =====): vinculan nombre<->contenido y
        # mantienen estable el prefijo para el implicit caching de Gemini 2.5.
        for elem in prefijo:
            if isinstance(elem, str):
                self.assertIn("DOCUMENTO ADJUNTO:", elem)

    @patch("Clasificador.clasificador.genai.Client")
    @patch("Clasificador.gemini_files_manager.genai.Client")
    def test_analisis_factura_prompt_va_al_final(
        self, mock_files_client_class, mock_client_class
    ):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_files_client = MagicMock()
        mock_files_client_class.return_value = mock_files_client

        mf = self._mock_file()
        mock_client.aio.files.get = AsyncMock(return_value=mf)

        mock_response = MagicMock()
        mock_response.text = '{"conceptos_aplicables": []}'
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=2000,
            cached_content_token_count=1800,
            candidates_token_count=80,
        )
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        clasificador = ProcesadorGemini()

        # Archivo ya en Files API (objeto con uri/mime_type) -> ruta cache directa
        archivo_files_api = self._mock_file()

        asyncio.run(
            clasificador._llamar_gemini_hibrido_factura(
                prompt="PROMPT DE ANALISIS DE FACTURA",
                archivos_directos=[archivo_files_api],
            )
        )

        contents = _capturar_contents(mock_client.aio.models.generate_content)

        self.assertGreaterEqual(len(contents), 2)
        self.assertIsInstance(contents[-1], str)
        self.assertEqual(contents[-1], "PROMPT DE ANALISIS DE FACTURA")
        for elem in contents[:-1]:
            self.assertNotIsInstance(elem, str)

    @patch("Clasificador.clasificador.genai.Client")
    @patch("Clasificador.gemini_files_manager.genai.Client")
    def test_log_uso_tokens_no_rompe_sin_usage_metadata(
        self, mock_files_client_class, mock_client_class
    ):
        mock_client_class.return_value = MagicMock()
        mock_files_client_class.return_value = MagicMock()
        clasificador = ProcesadorGemini()

        # Respuesta sin usage_metadata: no debe lanzar
        resp = MagicMock(spec=[])
        clasificador._log_uso_tokens(resp, "test")

        # usage_metadata = None: no debe lanzar
        resp2 = MagicMock()
        resp2.usage_metadata = None
        clasificador._log_uso_tokens(resp2, "test")


class TestMedicionAgregadaYPrimado(unittest.TestCase):

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = "test_api_key_12345"

    def tearDown(self):
        os.environ.pop("GEMINI_API_KEY", None)

    def _resp(self, prompt, cacheados, salida):
        r = MagicMock()
        r.usage_metadata = MagicMock(
            prompt_token_count=prompt,
            cached_content_token_count=cacheados,
            candidates_token_count=salida,
        )
        return r

    @patch("Clasificador.clasificador.genai.Client")
    @patch("Clasificador.gemini_files_manager.genai.Client")
    def test_acumula_y_resumen(self, mock_files, mock_client):
        mock_client.return_value = MagicMock()
        mock_files.return_value = MagicMock()
        c = ProcesadorGemini()

        c._log_uso_tokens(self._resp(1000, 800, 50), "clasificacion")
        c._log_uso_tokens(self._resp(2000, 1500, 60), "analisis_factura")
        c._log_uso_tokens(self._resp(500, 0, 10), "ica_ubicaciones")

        self.assertEqual(len(c._uso_acumulado), 3)
        self.assertEqual(sum(r["prompt"] for r in c._uso_acumulado), 3500)
        self.assertEqual(sum(r["cacheados"] for r in c._uso_acumulado), 2300)
        # No debe romper
        c._log_resumen_uso_tokens()

    @patch("Clasificador.clasificador.genai.Client")
    @patch("Clasificador.gemini_files_manager.genai.Client")
    def test_resumen_vacio_no_rompe(self, mock_files, mock_client):
        mock_client.return_value = MagicMock()
        mock_files.return_value = MagicMock()
        c = ProcesadorGemini()
        c._log_resumen_uso_tokens()  # _uso_acumulado vacio

    @patch("Clasificador.clasificador.genai.Client")
    @patch("Clasificador.gemini_files_manager.genai.Client")
    def test_ejecutar_con_retry_invoca_hook_con_contexto(self, mock_files, mock_client):
        mc = MagicMock()
        mock_client.return_value = mc
        mock_files.return_value = MagicMock()
        mc.aio.models.generate_content = AsyncMock(
            return_value=self._resp(100, 90, 5)
        )
        c = ProcesadorGemini()

        asyncio.run(
            c._ejecutar_con_retry(
                contenido=["x"], config={}, timeout_segundos=5, contexto="probe"
            )
        )
        self.assertEqual(len(c._uso_acumulado), 1)
        self.assertEqual(c._uso_acumulado[0]["contexto"], "probe")


class TestICAReorden(unittest.TestCase):

    def setUp(self):
        os.environ["GEMINI_API_KEY"] = "test_api_key_12345"

    def tearDown(self):
        os.environ.pop("GEMINI_API_KEY", None)

    @patch("Clasificador.clasificador_ica.crear_prompt_identificacion_ubicaciones")
    def test_ubicaciones_documentos_primero_prompt_al_final(self, mock_prompt):
        from Clasificador.clasificador_ica import ClasificadorICA

        mock_prompt.return_value = "PROMPT_ICA_UBICACIONES"

        procesador = MagicMock()
        procesador.generation_config = {"temperature": 0.4}
        procesador._ejecutar_con_retry = AsyncMock(side_effect=RuntimeError("stop"))

        ica = ClasificadorICA(database_manager=MagicMock(), procesador_gemini=procesador)
        ica._procesar_archivos_para_gemini = AsyncMock(return_value=["DOC1", "DOC2"])

        # El metodo captura la excepcion internamente; solo importan call_args
        asyncio.run(
            ica._identificar_ubicaciones_gemini(
                ubicaciones_bd=[{"x": 1}],
                textos_documentos={},
                archivos_directos=[MagicMock(), MagicMock()],
            )
        )

        procesador._ejecutar_con_retry.assert_awaited()
        kwargs = procesador._ejecutar_con_retry.await_args.kwargs
        self.assertEqual(kwargs["contexto"], "ica_ubicaciones")
        contenido = kwargs["contenido"]
        self.assertEqual(contenido, ["DOC1", "DOC2", "PROMPT_ICA_UBICACIONES"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
