"""
TEST LIQUIDADOR CONSORCIOS
==========================

Tests unitarios para Liquidador.liquidador_consorcios.LiquidadorConsorcios.

Cobertura del fix v3.14.5:
1. Validacion explicita cuando Gemini devuelve porcentaje_participacion: null
   (antes lanzaba TypeError: float() argument... y reseteaba todo el resultado).
2. Hardening del antipatron dict.get(key, 0) que dejaba pasar None hacia
   float()/Decimal(str(...)).

CASOS:
1. porcentaje_participacion null en consorciado unico -> preliquidacion sin finalizar
2. porcentaje_participacion null en uno de varios -> preserva los validos
3. porcentaje_participacion = 0 -> caso valido (no es incompleto)
4. valor_total null -> no crashea, queda Decimal('0')
5. tarifa_retencion null en concepto -> no crashea
6. base_gravable null en concepto -> no crashea, base individual = 0
"""

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from Liquidador.liquidador_consorcios import (
    LiquidadorConsorcios,
    ValidadorNaturalezaTributaria,
    CalculadorRetencionConsorcio,
)


def _mk_naturaleza_valida():
    """Naturaleza tributaria que pasa la validacion (no autorretenedor, no SIMPLE)."""
    return {
        "es_persona_natural": False,
        "regimen_tributario": "ORDINARIO",
        "es_autorretenedor": False,
        "es_responsable_iva": True,
    }


def _mk_concepto(tarifa_retencion=4.0, base_gravable=419927450.00):
    """Concepto identificado tipico (formato porcentaje, no decimal)."""
    return {
        "concepto": "ADMINISTRACION EN OPERACION DEL PROYECTO VIAL",
        "concepto_index": 3285,
        "tarifa_retencion": tarifa_retencion,
        "base_gravable": base_gravable,
    }


def _mk_validador_conceptos_mock(datos_extra=None):
    """
    Mock de IValidadorConceptos que aprueba cualquier concepto y retorna
    metadatos de BD opcionales. Por defecto retorna codigo + base 0
    (igual que en logs reales: 'tarifa=4.0%, base=$0.00').
    """
    mock = Mock()
    datos = {"codigo_concepto": "3285", "base_pesos": 0}
    if datos_extra:
        datos.update(datos_extra)
    mock.validar_concepto = Mock(return_value=(True, datos))
    return mock


def _mk_validador_conceptos_selectivo(datos_extra=None):
    """
    Mock que RECHAZA conceptos no mapeados (CONCEPTO_NO_IDENTIFICADO / concepto_index 0)
    y aprueba el resto, igual que el ValidadorConceptos real. Permite probar la regla
    flexible: un concepto no mapeado no debe abortar si al menos otro si mapea.
    """
    mock = Mock()
    datos = {"codigo_concepto": "3285", "base_pesos": 0}
    if datos_extra:
        datos.update(datos_extra)

    def _validar(concepto, diccionario_conceptos, concepto_index=None):
        if concepto == "CONCEPTO_NO_IDENTIFICADO" or not concepto or concepto_index == 0:
            return False, {}
        return True, dict(datos)

    mock.validar_concepto = Mock(side_effect=_validar)
    return mock


def _mk_concepto_no_mapeado(nombre="IVA"):
    """Concepto que Gemini no logro mapear: CONCEPTO_NO_IDENTIFICADO con index 0."""
    return {
        "nombre_concepto": nombre,
        "concepto": "CONCEPTO_NO_IDENTIFICADO",
        "concepto_index": 0,
        "base_gravable": 10950357.0,
        "razonamiento": "IVA es un impuesto, no un concepto sujeto a retencion en la fuente.",
    }


def _mk_liquidador():
    """Construye un LiquidadorConsorcios con dependencias reales salvo BD."""
    return LiquidadorConsorcios(
        estructura_contable=13,
        db_manager=Mock(),
        validador_naturaleza=ValidadorNaturalezaTributaria(),
        validador_conceptos=_mk_validador_conceptos_mock(),
        calculador_retencion=CalculadorRetencionConsorcio(),
    )


class TestLiquidadorConsorciosFixPorcentajeNull(unittest.IsolatedAsyncioTestCase):
    """Task 2: validacion explicita cuando porcentaje_participacion es None."""

    async def test_porcentaje_participacion_null_no_crashea(self):
        """Caso real del incidente 2026-05-15: un null en porcentaje no debe tumbar todo."""
        analisis = {
            "es_consorcio": True,
            "nombre_consorcio": "CONSORCIO TEST",
            "valor_total": 419927450.00,
            "consorciados": [
                {
                    "nombre": "CONSORCIADO ALFA",
                    "nit": "900123456",
                    "porcentaje_participacion": None,  # <- el bug
                    "naturaleza_tributaria": _mk_naturaleza_valida(),
                }
            ],
            "conceptos_identificados": [_mk_concepto()],
        }

        liq = _mk_liquidador()
        resultado = await liq.liquidar_consorcio(analisis, diccionario_conceptos={})

        # Antes del fix: lanzaba TypeError -> caia al except y devolvia
        # es_consorcio=False, consorciados=[], valor=0. Tras el fix:
        self.assertFalse(resultado.procesamiento_exitoso)
        self.assertEqual(resultado.estado, "preliquidación_sin_finalizar")
        self.assertEqual(resultado.es_consorcio, True)  # se preserva
        self.assertEqual(len(resultado.consorciados), 1)
        self.assertEqual(resultado.valor_factura_sin_iva, Decimal("419927450.00"))

        # La observacion debe ser amigable y mencionar el campo + consorciado
        observaciones_juntas = " ".join(resultado.observaciones)
        self.assertIn("porcentaje de participación", observaciones_juntas)
        self.assertIn("CONSORCIADO ALFA", observaciones_juntas)

    async def test_porcentaje_null_preserva_otros_consorciados(self):
        """Un consorciado incompleto no debe borrar a los demas."""
        analisis = {
            "es_consorcio": True,
            "nombre_consorcio": "CONSORCIO TEST",
            "valor_total": 1000000.00,
            "consorciados": [
                {
                    "nombre": "ALFA",
                    "nit": "900111111",
                    "porcentaje_participacion": 50.0,
                    "naturaleza_tributaria": _mk_naturaleza_valida(),
                },
                {
                    "nombre": "BETA",
                    "nit": "900222222",
                    "porcentaje_participacion": None,
                    "naturaleza_tributaria": _mk_naturaleza_valida(),
                },
            ],
            "conceptos_identificados": [_mk_concepto()],
        }

        liq = _mk_liquidador()
        resultado = await liq.liquidar_consorcio(analisis, diccionario_conceptos={})

        # Ambos consorciados deben aparecer en la lista (uno liquidado, uno no)
        self.assertEqual(len(resultado.consorciados), 2)
        nombres = {c.nombre for c in resultado.consorciados}
        self.assertEqual(nombres, {"ALFA", "BETA"})

        # Pero el resultado global queda como sin finalizar (un dato faltante)
        self.assertFalse(resultado.procesamiento_exitoso)
        self.assertEqual(resultado.estado, "preliquidación_sin_finalizar")

        # La observacion menciona solo a BETA (el que falta), no a ALFA
        observaciones_juntas = " ".join(resultado.observaciones)
        self.assertIn("BETA", observaciones_juntas)
        self.assertNotIn("ALFA", observaciones_juntas)

    async def test_porcentaje_cero_es_valido(self):
        """porcentaje 0 es un valor numerico real, NO debe activar la rama 'incompleto'."""
        analisis = {
            "es_consorcio": True,
            "nombre_consorcio": "CONSORCIO TEST",
            "valor_total": 1000000.00,
            "consorciados": [
                {
                    "nombre": "ALFA",
                    "nit": "900111111",
                    "porcentaje_participacion": 0,  # valor real, no faltante
                    "naturaleza_tributaria": _mk_naturaleza_valida(),
                }
            ],
            "conceptos_identificados": [_mk_concepto()],
        }

        liq = _mk_liquidador()
        resultado = await liq.liquidar_consorcio(analisis, diccionario_conceptos={})

        # Sin observaciones de "informacion incompleta" - se procesa limpio
        self.assertTrue(resultado.procesamiento_exitoso)
        self.assertEqual(resultado.estado, "preliquidado")
        observaciones_juntas = " ".join(resultado.observaciones).lower()
        self.assertNotIn("incompleta", observaciones_juntas)
        # Y como porcentaje=0, valor_retencion individual = 0
        self.assertEqual(resultado.consorciados[0].valor_retencion, Decimal("0"))


class TestLiquidadorConsorciosHardeningNone(unittest.IsolatedAsyncioTestCase):
    """Task 3: el antipatron dict.get(key, 0) ya no deja pasar None hacia float/Decimal."""

    async def test_valor_total_null_no_crashea(self):
        """analisis_gemini['valor_total'] = None no debe lanzar TypeError ni InvalidOperation."""
        analisis = {
            "es_consorcio": True,
            "nombre_consorcio": "CONSORCIO TEST",
            "valor_total": None,  # <- antes: Decimal('None') -> InvalidOperation
            "consorciados": [
                {
                    "nombre": "ALFA",
                    "nit": "900111111",
                    "porcentaje_participacion": 100.0,
                    "naturaleza_tributaria": _mk_naturaleza_valida(),
                }
            ],
            "conceptos_identificados": [_mk_concepto()],
        }

        liq = _mk_liquidador()
        resultado = await liq.liquidar_consorcio(analisis, diccionario_conceptos={})

        # No debe haber caido al except generico (que devolveria es_consorcio=False)
        self.assertEqual(resultado.es_consorcio, True)
        self.assertEqual(resultado.valor_factura_sin_iva, Decimal("0"))

    async def test_tarifa_retencion_null_en_concepto_no_crashea(self):
        """concepto con tarifa_retencion: None no debe crashear el calculo."""
        analisis = {
            "es_consorcio": True,
            "nombre_consorcio": "CONSORCIO TEST",
            "valor_total": 1000000.00,
            "consorciados": [
                {
                    "nombre": "ALFA",
                    "nit": "900111111",
                    "porcentaje_participacion": 100.0,
                    "naturaleza_tributaria": _mk_naturaleza_valida(),
                }
            ],
            "conceptos_identificados": [_mk_concepto(tarifa_retencion=None)],
        }

        # Mock que NO sobreescribe tarifa_retencion - asi el None del concepto sobrevive
        liq = LiquidadorConsorcios(
            estructura_contable=13,
            db_manager=Mock(),
            validador_naturaleza=ValidadorNaturalezaTributaria(),
            validador_conceptos=_mk_validador_conceptos_mock(),  # solo aporta codigo + base_pesos
            calculador_retencion=CalculadorRetencionConsorcio(),
        )
        resultado = await liq.liquidar_consorcio(analisis, diccionario_conceptos={})

        # No crashea - la liquidacion continua, simplemente con tarifa = 0
        self.assertEqual(resultado.es_consorcio, True)
        # valor_retencion individual debe ser 0 (tarifa 0 -> retencion 0)
        self.assertEqual(resultado.consorciados[0].valor_retencion, Decimal("0"))

    async def test_base_gravable_null_en_concepto_no_crashea(self):
        """concepto con base_gravable: None no debe crashear; base individual = 0."""
        analisis = {
            "es_consorcio": True,
            "nombre_consorcio": "CONSORCIO TEST",
            "valor_total": 1000000.00,
            "consorciados": [
                {
                    "nombre": "ALFA",
                    "nit": "900111111",
                    "porcentaje_participacion": 100.0,
                    "naturaleza_tributaria": _mk_naturaleza_valida(),
                }
            ],
            "conceptos_identificados": [_mk_concepto(base_gravable=None)],
        }

        liq = _mk_liquidador()
        resultado = await liq.liquidar_consorcio(analisis, diccionario_conceptos={})

        # No crashea
        self.assertEqual(resultado.es_consorcio, True)
        # base_gravable=0 + base_pesos=0 -> 0 < 0 es False, asi que aplica concepto
        # con base individual = 0 -> retencion = 0
        self.assertEqual(resultado.consorciados[0].valor_retencion, Decimal("0"))


class TestLiquidadorConsorciosConceptosNoMapeados(unittest.IsolatedAsyncioTestCase):
    """Regla flexible: un concepto no mapeado no aborta la liquidacion si al menos uno mapea."""

    def _mk_liquidador_selectivo(self):
        return LiquidadorConsorcios(
            estructura_contable=13,
            db_manager=Mock(),
            validador_naturaleza=ValidadorNaturalezaTributaria(),
            validador_conceptos=_mk_validador_conceptos_selectivo(),
            calculador_retencion=CalculadorRetencionConsorcio(),
        )

    async def test_al_menos_un_concepto_mapea_se_muestra(self):
        """Con 1 concepto valido + 1 no mapeado, se liquida y se muestra con alerta."""
        analisis = {
            "es_consorcio": True,
            "nombre_consorcio": "CONSORCIO PAS",
            "valor_total": 1000000.00,
            "consorciados": [
                {
                    "nombre": "ALFA",
                    "nit": "900111111",
                    "porcentaje_participacion": 100.0,
                    "naturaleza_tributaria": _mk_naturaleza_valida(),
                }
            ],
            "conceptos_identificados": [_mk_concepto(), _mk_concepto_no_mapeado("IVA")],
        }

        liq = self._mk_liquidador_selectivo()
        resultado = await liq.liquidar_consorcio(analisis, diccionario_conceptos={})

        # Se muestra el resultado: exitoso y preliquidado
        self.assertTrue(resultado.procesamiento_exitoso)
        self.assertEqual(resultado.estado, "preliquidado")

        # Solo el concepto mapeado entra a conceptos_aplicados
        self.assertEqual(len(resultado.conceptos_aplicados), 1)
        self.assertNotIn(
            "CONCEPTO_NO_IDENTIFICADO",
            [c.get("concepto") for c in resultado.conceptos_aplicados],
        )

        # La alerta del concepto no mapeado aparece en observaciones
        observaciones_juntas = " ".join(resultado.observaciones)
        self.assertIn("IVA", observaciones_juntas)
        self.assertIn("no se pudo relacionar", observaciones_juntas)

    async def test_ningun_concepto_mapea_alerta_bloqueante(self):
        """Si NINGUN concepto mapea, recien ahi la preliquidacion queda sin finalizar."""
        analisis = {
            "es_consorcio": True,
            "nombre_consorcio": "CONSORCIO PAS",
            "valor_total": 1000000.00,
            "consorciados": [
                {
                    "nombre": "ALFA",
                    "nit": "900111111",
                    "porcentaje_participacion": 100.0,
                    "naturaleza_tributaria": _mk_naturaleza_valida(),
                }
            ],
            "conceptos_identificados": [
                _mk_concepto_no_mapeado("IVA"),
                _mk_concepto_no_mapeado("OTRO IMPUESTO"),
            ],
        }

        liq = self._mk_liquidador_selectivo()
        resultado = await liq.liquidar_consorcio(analisis, diccionario_conceptos={})

        self.assertFalse(resultado.procesamiento_exitoso)
        self.assertEqual(resultado.estado, "preliquidacion_sin_finalizar")
        self.assertEqual(len(resultado.conceptos_aplicados), 0)


if __name__ == "__main__":
    unittest.main()
