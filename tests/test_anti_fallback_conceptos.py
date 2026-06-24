"""
TEST REGLA ANTI-COMODIN (RETEFUENTE) + ACLARACION CIIU (ICA)
============================================================

Cobertura del fix v3.19.6:

1. prompts/prompt_retefuente.py:
   - PROMPT_ANALISIS_FACTURA y PROMPT_MATCHING_CONCEPTOS contienen la REGLA
     ANTI-COMODIN: "Servicios en general" / conceptos genericos NO son un valor
     por defecto; ante ausencia de equivalencia clara -> CONCEPTO_NO_IDENTIFICADO.

2. prompts/prompt_ica.py:
   - crear_prompt_relacionar_actividades y crear_prompt_identificacion_ubicaciones
     aclaran que la ACTIVIDAD ECONOMICA / CIIU del encabezado es dato del EMISOR
     (una pista), no la actividad facturada.

Motivacion (caso real AF3522, Asociacion de Fiduciarias -> Fiducoldex): una cuota
de sostenimiento se mapeaba a "Servicios en general" (retefuente) y el CIIU 9411 del
encabezado se tomaba como actividad facturada (ICA). El refuerzo es GENERAL, no una
regla rigida atada a "cuota de sostenimiento", y no lee leyendas de la factura
(para evitar prompt injection).

Estos tests son deterministas: validan el contenido de los prompts generados, sin
llamar a Gemini ni a la base de datos.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from prompts.prompt_retefuente import (
    PROMPT_ANALISIS_FACTURA,
    PROMPT_MATCHING_CONCEPTOS,
)
from prompts.prompt_ica import (
    crear_prompt_relacionar_actividades,
    crear_prompt_identificacion_ubicaciones,
)


CONCEPTOS_DICT = {
    "Servicios en general - Beneficiario persona juridica o asimilada": 36,
    "Honorarios y comisiones - Beneficiario persona juridica": 1,
    "Compras generales - Beneficiario declarante de renta": 22,
}


class TestAntiComodinRetefuente(unittest.TestCase):
    """La rubrica de retefuente debe prohibir el uso del generico por defecto."""

    def _prompt_analisis(self) -> str:
        return PROMPT_ANALISIS_FACTURA(
            factura_texto="GRUPO II CUOTA SOSTENIMIENTO JUNIO 2026  18.607.410",
            rut_texto="",
            anexos_texto="",
            cotizaciones_texto="",
            anexo_contrato="",
            conceptos_dict=CONCEPTOS_DICT,
            nombres_archivos_directos=None,
            proveedor="ASOCIACION DE FIDUCIARIAS",
        )

    def test_analisis_factura_tiene_regla_anti_comodin(self):
        prompt = self._prompt_analisis()
        self.assertIn("ANTI-COMOD", prompt)  # ANTI-COMODIN/ANTI-COMODÍN
        self.assertIn(
            "Es PREFERIBLE dejar el concepto como CONCEPTO_NO_IDENTIFICADO",
            prompt,
        )

    def test_analisis_factura_tiene_gate_cuotas_aportes(self):
        prompt = self._prompt_analisis()
        # Gate PASO 3.0: familia cuota/aporte gremial -> CONCEPTO_NO_IDENTIFICADO
        self.assertIn("PASO 3.0", prompt)
        self.assertIn("FAMILIA CUOTA/APORTE", prompt)
        self.assertIn("ANTI-RACIONALIZACIÓN", prompt)
        self.assertIn("ACOTACIÓN DE SEGURIDAD", prompt)
        # Few-shot negativo de cuota de sostenimiento
        self.assertIn("EJEMPLO 6", prompt)
        self.assertIn("Cuota de sostenimiento junio 2026", prompt)

    def test_matching_consorcios_tiene_gate_cuotas_aportes(self):
        prompt = PROMPT_MATCHING_CONCEPTOS(
            conceptos_literales=[
                {"nombre_concepto": "Cuota de sostenimiento junio 2026", "base_gravable": 18607410.0}
            ],
            conceptos_dict=CONCEPTOS_DICT,
        )
        self.assertIn("GATE PREVIO", prompt)
        self.assertIn("FAMILIA CUOTA/APORTE", prompt)
        self.assertIn("ACOTACION DE SEGURIDAD", prompt)

    def test_analisis_factura_prohibe_generico_por_defecto(self):
        prompt = self._prompt_analisis()
        # Debe instruir que el generico no es un valor por defecto / comodin.
        self.assertIn("no son un valor por", prompt.lower())
        self.assertIn("CONCEPTO_NO_IDENTIFICADO", prompt)

    def test_matching_consorcios_tiene_regla_anti_comodin(self):
        prompt = PROMPT_MATCHING_CONCEPTOS(
            conceptos_literales=[
                {"nombre_concepto": "Cuota de sostenimiento junio 2026", "base_gravable": 18607410.0}
            ],
            conceptos_dict=CONCEPTOS_DICT,
        )
        self.assertIn("ANTI-COMODIN", prompt)
        self.assertIn(
            "Es PREFERIBLE dejar el concepto como CONCEPTO_NO_IDENTIFICADO",
            prompt,
        )


class TestCiiuPistaIca(unittest.TestCase):
    """El prompt de ICA debe distinguir el CIIU del emisor de la actividad facturada."""

    UBICACIONES_BD = [
        {"codigo_ubicacion": 1, "nombre_ubicacion": "BOGOTA D.C.", "nombre_departamento": "BOGOTA D.C."}
    ]
    TEXTOS_DOCS = {
        "factura.pdf": (
            "ACTIVIDAD ECONOMICA 9411 TARIFA ICA 9.66 X 1000\n"
            "GRUPO II CUOTA SOSTENIMIENTO JUNIO 2026  18.607.410"
        )
    }

    def test_relacionar_actividades_aclara_ciiu_es_pista(self):
        prompt = crear_prompt_relacionar_actividades(
            ubicaciones_identificadas=[{"nombre_ubicacion": "BOGOTA D.C.", "codigo_ubicacion": 1}],
            actividades_bd_por_ubicacion={
                "1": [
                    {
                        "codigo_actividad": 9411,
                        "descripcion_actividad": "ACTIVIDADES DE ASOCIACIONES EMPRESARIALES Y DE EMPLEADORES",
                        "tipo_actividad": "SERVICIOS",
                        "porcentaje_ica": 9.66,
                    }
                ]
            },
            textos_documentos=self.TEXTOS_DOCS,
            nombres_archivos_directos=None,
        )
        self.assertIn("NO CONFUNDIR EMISOR CON LO FACTURADO", prompt)
        self.assertIn("PISTA de contexto, NO la actividad facturada", prompt)

    def test_identificacion_ubicaciones_aclara_ciiu_del_emisor(self):
        prompt = crear_prompt_identificacion_ubicaciones(
            ubicaciones_bd=self.UBICACIONES_BD,
            textos_documentos=self.TEXTOS_DOCS,
            nombres_archivos_directos=None,
        )
        self.assertIn("registro del EMISOR/proveedor", prompt)


if __name__ == "__main__":
    unittest.main()
