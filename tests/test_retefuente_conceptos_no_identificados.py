"""
Tests para el caso en que TODOS los conceptos facturados quedan como
CONCEPTO_NO_IDENTIFICADO en retencion en la fuente.

Cuando Gemini no encuentra ninguna relacion entre lo facturado y el
diccionario de conceptos de retefuente, el liquidador debe:
  - devolver un unico mensaje ("No se identificaron conceptos validos
    para calcular retencion"), sin el mensaje redundante de validar soportes
  - dejar el estado como "no_aplica_impuesto"
  - no liquidar retencion (valor_retencion == 0, puede_liquidar == False)

Ver CHANGELOG [3.19.7].
"""

import unittest

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modelos import AnalisisFactura, ConceptoIdentificado, NaturalezaTercero
from Liquidador.liquidador import LiquidadorRetencion


MENSAJE_VALIDAR_SOPORTES = (
    "El concepto facturado no se identifica en los soportes adjuntos. "
    "Validar soportes."
)
MENSAJE_SIN_CONCEPTOS = "No se identificaron conceptos válidos para calcular retención"


def _naturaleza_completa():
    """Tercero valido que NO bloquea ni agrega advertencias en la validacion."""
    return NaturalezaTercero(
        es_persona_natural=False,
        regimen_tributario="ORDINARIO",
        es_autorretenedor=False,
    )


class TestRetefuenteTodosConceptosNoIdentificados(unittest.TestCase):
    """Caso: ningun concepto facturado mapea al diccionario."""

    def setUp(self):
        self.liquidador = LiquidadorRetencion()

    def _analisis_todos_no_identificados(self):
        return AnalisisFactura(
            conceptos_identificados=[
                ConceptoIdentificado(
                    concepto="CONCEPTO_NO_IDENTIFICADO",
                    concepto_facturado="Cuota de sostenimiento gremial",
                    base_gravable=1000000.0,
                    concepto_index=0,
                ),
                ConceptoIdentificado(
                    concepto="CONCEPTO_NO_IDENTIFICADO",
                    concepto_facturado="Aporte ordinario asociacion",
                    base_gravable=500000.0,
                    concepto_index=0,
                ),
            ],
            naturaleza_tercero=_naturaleza_completa(),
            valor_total=1500000.0,
            observaciones=[],
        )

    def test_estado_es_no_aplica_impuesto(self):
        resultado = self.liquidador.calcular_retencion(
            self._analisis_todos_no_identificados()
        )
        self.assertEqual(resultado.estado, "no_aplica_impuesto")
        self.assertFalse(resultado.puede_liquidar)
        self.assertEqual(resultado.valor_retencion, 0)

    def test_solo_mensaje_sin_conceptos_validos(self):
        resultado = self.liquidador.calcular_retencion(
            self._analisis_todos_no_identificados()
        )
        self.assertIn(MENSAJE_SIN_CONCEPTOS, resultado.mensajes_error)
        # El mensaje redundante de "validar soportes" NO debe aparecer
        # cuando todos los conceptos son no identificados.
        self.assertNotIn(MENSAJE_VALIDAR_SOPORTES, resultado.mensajes_error)


if __name__ == "__main__":
    unittest.main()
