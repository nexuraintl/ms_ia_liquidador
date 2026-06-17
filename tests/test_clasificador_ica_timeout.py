"""
Tests para el manejo de timeout / fallo tecnico en ClasificadorICA.analizar_ica.

Verifica que un fallo TECNICO (timeout de Gemini) NO se reporte como si Gemini
no hubiera identificado ubicaciones/actividades, y que el caso genuino conserve
su mensaje original.

Autor: Sistema Preliquidador
"""

import asyncio
import json
import unittest
from unittest.mock import Mock, AsyncMock, patch

from Clasificador.clasificador_ica import ClasificadorICA


def _respuesta(texto: str) -> Mock:
    r = Mock()
    r.text = texto
    return r


UBICACION_OK_JSON = json.dumps({
    "aplica_ica": True,
    "ubicaciones": [{
        "nombre_ubicacion": "BOGOTA",
        "codigo_ubicacion": 1,
        "texto_identificador": "Bogota D.C.",
        "porcentaje_ejecucion": 100.0,
    }],
    "observaciones": "",
})

UBICACION_VACIA_JSON = json.dumps({
    "aplica_ica": True,
    "ubicaciones": [{
        "nombre_ubicacion": "",
        "codigo_ubicacion": 0,
        "texto_identificador": "",
        "porcentaje_ejecucion": 0.0,
    }],
    "observaciones": "No se encontró ubicación en los documentos proporcionados",
})


class TestClasificadorICATimeout(unittest.IsolatedAsyncioTestCase):
    """Tests de diferenciacion timeout vs. no identificado."""

    def _build(self, ejecutar_side_effect):
        procesador = Mock()
        procesador.generation_config = {}
        procesador._ejecutar_con_retry = AsyncMock(side_effect=ejecutar_side_effect)

        db = Mock()
        db.obtener_ubicaciones_ica.return_value = {
            "success": True,
            "data": [{
                "codigo_ubicacion": 1,
                "nombre_ubicacion": "BOGOTA",
                "nombre_departamento": "BOGOTA D.C.",
            }],
            "message": "",
        }
        db.obtener_actividades_ica.return_value = {
            "success": True,
            "data": [{
                "nombre_ubicacion": "BOGOTA",
                "codigo_actividad": 10,
                "descripcion_actividad": "Servicios profesionales",
                "tipo_actividad": "SERVICIOS",
                "porcentaje_ica": 0.966,
            }],
            "message": "",
        }

        clasificador = ClasificadorICA(database_manager=db, procesador_gemini=procesador)
        return clasificador

    async def _analizar(self, clasificador):
        with patch("config.nit_aplica_ICA", return_value=True), \
             patch.object(ClasificadorICA, "_guardar_respuesta_gemini", return_value=None):
            return await clasificador.analizar_ica(
                nit_administrativo="900123456",
                textos_documentos={"doc.pdf": "Servicio prestado en Bogota"},
                estructura_contable=1,
                cache_archivos=None,
            )

    async def test_timeout_ubicaciones_reporta_error_tecnico(self):
        """Timeout en la 1a llamada -> 'Error analizando ubicaciones', no 'no se pudo identificar el municipio'."""
        clasificador = self._build(asyncio.TimeoutError())
        resultado = await self._analizar(clasificador)

        self.assertEqual(resultado["estado"], "preliquidacion_sin_finalizar")
        obs = " ".join(resultado["observaciones"])
        self.assertIn("Error analizando ubicaciones ICA", obs)
        self.assertNotIn("No se pudo identificar el municipio", obs)

    async def test_timeout_actividades_reporta_error_tecnico(self):
        """Ubicaciones OK pero timeout en la 2a llamada -> 'Error mapeando actividades ICA'."""
        clasificador = self._build([
            _respuesta(UBICACION_OK_JSON),
            asyncio.TimeoutError(),
        ])
        resultado = await self._analizar(clasificador)

        self.assertEqual(resultado["estado"], "preliquidacion_sin_finalizar")
        obs = " ".join(resultado["observaciones"])
        self.assertIn("Error mapeando actividades ICA", obs)
        self.assertNotIn("No se pudo identificar la actividad económica facturada", obs)

    async def test_caso_genuino_conserva_mensaje_original(self):
        """Gemini responde sin ubicacion (caso genuino) -> mensaje original intacto."""
        clasificador = self._build([_respuesta(UBICACION_VACIA_JSON)])
        resultado = await self._analizar(clasificador)

        self.assertEqual(resultado["estado"], "preliquidacion_sin_finalizar")
        obs = " ".join(resultado["observaciones"])
        self.assertIn("No se pudo identificar el municipio de la actividad gravada.", obs)
        self.assertNotIn("Error analizando ubicaciones ICA", obs)


if __name__ == "__main__":
    unittest.main()
