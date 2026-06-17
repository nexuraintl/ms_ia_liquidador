"""
TEST PRELIQUIDACION SIN FINALIZAR + REINTENTOS CONNECTERROR
===========================================================

Cobertura del fix v3.14.6:

1. utils.mockups.crear_respuesta_preliquidacion_sin_finalizar:
   - respeta el contrato normal (mismas claves raiz que resultado_final)
   - estado_procesamiento == "preliquidacion_sin_finalizar"
   - todos los impuestos presentes con estado / aplica=False
   - bloque diagnostico_error presente y SIN error_traceback crudo

2. Clasificador.clasificador.ProcesadorGemini:
   - _es_error_transitorio detecta httpx.ConnectError (str vacio) por tipo
   - _files_get_con_retry reintenta ante ConnectError y luego tiene exito
   - _files_get_con_retry propaga errores NO transitorios sin reintentar
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import crear_respuesta_preliquidacion_sin_finalizar
from Clasificador.clasificador import ProcesadorGemini


CLAVES_CONTRATO_RAIZ = {
    "impuestos_procesados",
    "nit_administrativo",
    "nombre_entidad",
    "timestamp",
    "version",
    "impuestos",
    "es_consorcio",
    "es_facturacion_extranjera",
    "documentos_procesados",
    "documentos_clasificados",
}

IMPUESTOS_ESPERADOS = {
    "retefuente",
    "estampilla_universidad",
    "contribucion_obra_publica",
    "iva_reteiva",
    "estampillas_generales",
    "ica",
    "sobretasa_bomberil",
    "timbre",
    "tasa_prodeporte",
}


class TestRespuestaPreliquidacionSinFinalizar(unittest.TestCase):

    def setUp(self):
        self.mensaje = (
            "No se pudo conectar con el servicio de IA (Google Gemini). "
            "Preliquidación sin finalizar, intente nuevamente."
        )
        self.resp = crear_respuesta_preliquidacion_sin_finalizar(
            mensaje=self.mensaje,
            codigo_del_negocio=99664,
            diagnostico={
                "tipo_error": "ConnectError",
                "timestamp_error": "2026-05-18T00:00:00",
            },
        )

    def test_tiene_claves_de_contrato_normal(self):
        self.assertTrue(CLAVES_CONTRATO_RAIZ.issubset(set(self.resp.keys())))

    def test_estado_procesamiento_canonico(self):
        self.assertEqual(
            self.resp["estado_procesamiento"], "preliquidacion_sin_finalizar"
        )

    def test_no_es_blob_de_error(self):
        # El contrato roto usaba {"status": "error"}; aqui NO debe existir.
        self.assertNotIn("status", self.resp)
        self.assertNotEqual(self.resp.get("estado_procesamiento"), "error")

    def test_todos_los_impuestos_presentes(self):
        self.assertEqual(set(self.resp["impuestos"].keys()), IMPUESTOS_ESPERADOS)

    def test_impuestos_marcados_no_aplica(self):
        for nombre, impuesto in self.resp["impuestos"].items():
            if nombre == "estampillas_generales":
                # estructura anidada distinta
                continue
            self.assertIn(
                "aplica", impuesto, f"{nombre} sin campo 'aplica'"
            )
            self.assertFalse(impuesto["aplica"], f"{nombre} deberia ser aplica=False")
            tiene_estado = "estado" in impuesto or "estado_liquidacion" in impuesto
            self.assertTrue(tiene_estado, f"{nombre} sin campo de estado")

    def test_diagnostico_error_presente_sin_traceback(self):
        self.assertIn("diagnostico_error", self.resp)
        diag = self.resp["diagnostico_error"]
        self.assertEqual(diag["tipo_error"], "ConnectError")
        self.assertEqual(diag["servicio_externo"], "Google Gemini API")
        self.assertEqual(diag["causa_resumida"], self.mensaje)
        self.assertEqual(diag["codigo_del_negocio"], 99664)
        self.assertTrue(diag["retry_sugerido"])
        # NO debe filtrarse traceback crudo al frontend
        self.assertNotIn("error_traceback", diag)
        self.assertNotIn("error_traceback", self.resp)

    def test_mensaje_propagado_a_observaciones(self):
        obs_retefuente = self.resp["impuestos"]["retefuente"]["observaciones"]
        self.assertIn(self.mensaje, obs_retefuente)

    def test_diagnostico_opcional_usa_defaults(self):
        resp = crear_respuesta_preliquidacion_sin_finalizar(
            mensaje="fallo generico", codigo_del_negocio=1
        )
        diag = resp["diagnostico_error"]
        self.assertEqual(diag["servicio_externo"], "Google Gemini API")
        self.assertTrue(diag["retry_sugerido"])


class TestEsErrorTransitorio(unittest.TestCase):

    def setUp(self):
        # Instancia sin __init__ para probar metodos puros
        self.proc = object.__new__(ProcesadorGemini)

    def test_connecterror_detectado_por_tipo(self):
        # httpx.ConnectError tiene str() vacio -> debe detectarse por tipo
        e = httpx.ConnectError("")
        self.assertEqual(str(e), "")
        self.assertTrue(self.proc._es_error_transitorio(e))

    def test_ssl_error_sigue_siendo_transitorio(self):
        import ssl

        self.assertTrue(self.proc._es_error_transitorio(ssl.SSLError("ssl boom")))

    def test_patron_substring_unexpected_eof(self):
        self.assertTrue(
            self.proc._es_error_transitorio(Exception("UNEXPECTED_EOF on stream"))
        )

    def test_error_no_transitorio(self):
        self.assertFalse(
            self.proc._es_error_transitorio(ValueError("JSON invalido de Gemini"))
        )


class TestFilesGetConRetry(unittest.IsolatedAsyncioTestCase):

    def _nueva_instancia(self):
        proc = object.__new__(ProcesadorGemini)
        proc.api_key = "fake-key"
        return proc

    async def test_reintenta_y_tiene_exito(self):
        proc = self._nueva_instancia()
        proc.client = unittest_mock_client(
            side_effects=[httpx.ConnectError(""), "FILE_OBJ_OK"]
        )

        with patch("Clasificador.clasificador.genai.Client", return_value=proc.client), \
             patch("Clasificador.clasificador.asyncio.sleep", new=AsyncMock()):
            resultado = await proc._files_get_con_retry(name="files/abc", max_reintentos=3)

        self.assertEqual(resultado, "FILE_OBJ_OK")
        self.assertEqual(proc.client.aio.files.get.await_count, 2)

    async def test_propaga_error_no_transitorio_sin_reintentar(self):
        proc = self._nueva_instancia()
        proc.client = unittest_mock_client(side_effects=[ValueError("no transitorio")])

        with self.assertRaises(ValueError):
            await proc._files_get_con_retry(name="files/abc", max_reintentos=3)

        self.assertEqual(proc.client.aio.files.get.await_count, 1)


def unittest_mock_client(side_effects):
    """Crea un cliente genai mock con client.aio.files.get(...) async."""
    from unittest.mock import MagicMock

    client = MagicMock()
    client.aio.files.get = AsyncMock(side_effect=side_effects)
    return client


class TestBackgroundEnviaContratoAWebhook(unittest.IsolatedAsyncioTestCase):
    """
    Integracion del except de BackgroundProcessor.procesar_factura_background:
    ante un fallo del flujo, el webhook debe recibir el payload de CONTRATO
    (estado_procesamiento="preliquidacion_sin_finalizar"), NO el blob
    {"status": "error", "error_traceback": ...} que rompia el frontend.
    """

    def _construir_processor(self, fallo: Exception):
        from unittest.mock import MagicMock
        from Background.background_processor import BackgroundProcessor

        webhook_publisher = MagicMock()
        webhook_publisher.enviar_resultado = AsyncMock(
            return_value={"success": True, "intentos": 1, "message": "ok"}
        )

        proc = BackgroundProcessor(
            webhook_publisher=webhook_publisher,
            business_service=MagicMock(),
            db_manager=MagicMock(),
        )
        proc._autenticar_con_retry = AsyncMock(return_value=True)
        proc._reconstruir_archivos = MagicMock(return_value=[])
        proc._ejecutar_flujo_completo = AsyncMock(side_effect=fallo)
        return proc, webhook_publisher

    def _payload_enviado(self, webhook_publisher):
        self.assertTrue(
            webhook_publisher.enviar_resultado.await_count >= 1,
            "No se invoco enviar_resultado",
        )
        _, kwargs = webhook_publisher.enviar_resultado.call_args
        return kwargs["resultado"]

    async def test_fallo_conexion_ia_envia_contrato(self):
        fallo = ValueError(
            "Error en clasificación híbrida: 502: {'error': 'Error en "
            "clasificación híbrida de documentos', 'tipo': 'bad_gateway'}"
        )
        proc, webhook_publisher = self._construir_processor(fallo)

        with patch("config.guardar_archivo_json"):
            await proc.procesar_factura_background(
                factura_id=99664,
                archivos_data=[],
                parametros={"codigo_del_negocio": 99664},
            )

        payload = self._payload_enviado(webhook_publisher)
        # Respeta el contrato, NO es el blob de error
        self.assertNotIn("status", payload)
        self.assertEqual(
            payload["estado_procesamiento"], "preliquidacion_sin_finalizar"
        )
        self.assertEqual(set(payload["impuestos"].keys()), IMPUESTOS_ESPERADOS)
        # Mensaje de fallo de IA y diagnostico sin traceback
        diag = payload["diagnostico_error"]
        self.assertEqual(diag["tipo_error"], "ValueError")
        self.assertEqual(diag["codigo_del_negocio"], 99664)
        self.assertIn("servicio de procesamiento", diag["causa_resumida"])
        # El nombre del proveedor de IA NO debe filtrarse a campos visibles
        for impuesto in payload["impuestos"].values():
            self.assertNotIn("Gemini", str(impuesto))
        self.assertNotIn("Gemini", diag["causa_resumida"])
        # ...pero si se conserva en el bloque de diagnostico (servicio_externo)
        self.assertEqual(diag["servicio_externo"], "Google Gemini API")
        self.assertNotIn("error_traceback", payload)
        self.assertNotIn("error_traceback", diag)

    async def test_fallo_generico_envia_contrato_con_mensaje_generico(self):
        proc, webhook_publisher = self._construir_processor(
            RuntimeError("algo inesperado en liquidacion")
        )

        with patch("config.guardar_archivo_json"):
            await proc.procesar_factura_background(
                factura_id=30,
                archivos_data=[],
                parametros={"codigo_del_negocio": 30},
            )

        payload = self._payload_enviado(webhook_publisher)
        self.assertEqual(
            payload["estado_procesamiento"], "preliquidacion_sin_finalizar"
        )
        self.assertEqual(payload["diagnostico_error"]["tipo_error"], "RuntimeError")
        self.assertIn(
            "no pudo completarse",
            payload["diagnostico_error"]["causa_resumida"],
        )

    async def test_fallo_codigos_negocio_envia_contrato_con_diagnostico_nexura(self):
        # Mensaje real que lanza config.refrescar_codigos_negocio cuando la API
        # de codigoNegociosFiduciaria falla sin cache valido.
        fallo = RuntimeError(
            "No se pudieron obtener los códigos de negocio desde la API y no hay "
            "caché válido; se aborta la preliquidación. Detalle: API caida"
        )
        proc, webhook_publisher = self._construir_processor(fallo)

        with patch("config.guardar_archivo_json"):
            await proc.procesar_factura_background(
                factura_id=69164,
                archivos_data=[],
                parametros={"codigo_del_negocio": 69164},
            )

        payload = self._payload_enviado(webhook_publisher)
        self.assertNotIn("status", payload)
        self.assertEqual(
            payload["estado_procesamiento"], "preliquidacion_sin_finalizar"
        )
        diag = payload["diagnostico_error"]
        self.assertEqual(diag["tipo_error"], "RuntimeError")
        # Etiquetado correctamente como fallo de Nexura / BD, NO de Gemini
        self.assertEqual(diag["servicio_externo"], "API Nexura / Base de datos")
        self.assertTrue(diag["retry_sugerido"])
        self.assertIn("configuración de negocios", diag["causa_resumida"])
        self.assertNotIn("error_traceback", payload)

    async def test_limite_archivos_envia_contrato_con_mensaje_especifico(self):
        from fastapi import HTTPException

        fallo = HTTPException(
            status_code=400,
            detail={
                "error": "Demasiados archivos directos",
                "detalle": "Límite excedido: 38 archivos directos (máximo 20)",
                "limite_maximo": 20,
                "archivos_recibidos": 38,
                "sugerencia": "Reduzca el número de archivos directos",
            },
        )
        proc, webhook_publisher = self._construir_processor(fallo)

        with patch("config.guardar_archivo_json"):
            await proc.procesar_factura_background(
                factura_id=125798,
                archivos_data=[],
                parametros={"codigo_del_negocio": 125798},
            )

        payload = self._payload_enviado(webhook_publisher)
        # Respeta el contrato, NO es el blob de error
        self.assertNotIn("status", payload)
        self.assertEqual(
            payload["estado_procesamiento"], "preliquidacion_sin_finalizar"
        )
        self.assertEqual(set(payload["impuestos"].keys()), IMPUESTOS_ESPERADOS)
        diag = payload["diagnostico_error"]
        # Mensaje especifico del limite de archivos
        self.assertIn(
            "Límite de archivos adjuntos superado", diag["causa_resumida"]
        )
        # No es un fallo de Gemini ni se debe reintentar con los mismos archivos
        self.assertFalse(diag["retry_sugerido"])
        self.assertNotEqual(diag["servicio_externo"], "Google Gemini API")
        self.assertNotIn("error_traceback", payload)
        self.assertNotIn("error_traceback", diag)


if __name__ == "__main__":
    unittest.main()
