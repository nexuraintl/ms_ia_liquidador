"""
Tests para el preprocesamiento de Excel (Extraccion/extractor.py).

Cubre las optimizaciones de consumo de ventana de contexto:
- _normalizar_enteros: float-entero -> Int64 (quita '.0' y notacion cientifica).
- preprocesar_excel_limpio: limpieza, topes por hoja y presupuesto global de
  caracteres, lectura multi-hoja y eliminacion de vacios.

Autor: Miguel Angel Jaramillo Durango
"""

import io
import re

import pandas as pd
import pytest

import config
from Extraccion.extractor import (
    _normalizar_enteros,
    preprocesar_excel_limpio,
)


def _construir_xlsx(hojas: dict) -> bytes:
    """Serializa un dict {nombre_hoja: DataFrame} a bytes .xlsx en memoria."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for nombre, df in hojas.items():
            df.to_excel(writer, sheet_name=nombre, index=False)
    return buffer.getvalue()


_RE_DOT0 = re.compile(r"[0-9]\.0(?:[^0-9]|$)")
_RE_SCI = re.compile(r"[0-9]\.[0-9]+e[+-][0-9]+", re.IGNORECASE)


class TestNormalizarEnteros:
    """Tests unitarios de _normalizar_enteros."""

    def test_columna_float_entera_se_convierte_a_int64(self):
        df = pd.DataFrame({"valor": [9345000.0, 1775550.0, None]})
        resultado = _normalizar_enteros(df)
        assert str(resultado["valor"].dtype) == "Int64"

    def test_columna_con_decimales_reales_no_se_toca(self):
        df = pd.DataFrame({"tarifa": [0.025, 0.035, 0.01]})
        resultado = _normalizar_enteros(df)
        assert pd.api.types.is_float_dtype(resultado["tarifa"])

    def test_columna_todo_nan_no_falla(self):
        df = pd.DataFrame({"vacia": [None, None, None]}, dtype="float64")
        resultado = _normalizar_enteros(df)  # no debe lanzar
        assert "vacia" in resultado.columns

    def test_no_muta_el_dataframe_de_entrada(self):
        df = pd.DataFrame({"valor": [1.0, 2.0, 3.0]})
        _ = _normalizar_enteros(df)
        assert pd.api.types.is_float_dtype(df["valor"])


class TestPreprocesarExcelLimpio:
    """Tests de integracion de preprocesar_excel_limpio."""

    def test_enteros_sin_sufijo_punto_cero(self):
        df = pd.DataFrame({"valor": [9345000, 1775550, None, 12]})
        texto = preprocesar_excel_limpio(_construir_xlsx({"Base": df}), "t.xlsx")
        assert not _RE_DOT0.search(texto)

    def test_entero_grande_sin_notacion_cientifica(self):
        # NIT de 10 digitos (exacto en float64) con NaN que fuerza float.
        df = pd.DataFrame({"nit": [1061719238, None, 27104473]})
        texto = preprocesar_excel_limpio(_construir_xlsx({"Base": df}), "t.xlsx")
        assert not _RE_SCI.search(texto)
        assert "1061719238" in texto

    def test_decimales_reales_se_conservan(self):
        df = pd.DataFrame({"tarifa": [0.025, 0.035, 0.01]})
        texto = preprocesar_excel_limpio(_construir_xlsx({"Base": df}), "t.xlsx")
        assert "0.025" in texto

    def test_truncado_por_hoja(self, monkeypatch):
        monkeypatch.setattr(config, "EXCEL_MAX_FILAS_POR_HOJA", 50, raising=True)
        # Reimportar la constante usada dentro del modulo extractor.
        import Extraccion.extractor as extractor
        monkeypatch.setattr(extractor, "EXCEL_MAX_FILAS_POR_HOJA", 50, raising=True)

        df = pd.DataFrame({"a": range(200), "b": range(200)})
        texto = preprocesar_excel_limpio(_construir_xlsx({"Grande": df}), "t.xlsx")

        filas_datos = sum(1 for ln in texto.splitlines() if ln[:1].isdigit())
        assert filas_datos == 50
        assert "truncado" in texto

    def test_presupuesto_global_de_caracteres(self, monkeypatch):
        import Extraccion.extractor as extractor
        monkeypatch.setattr(extractor, "EXCEL_MAX_CHARS_POR_ARCHIVO", 5000, raising=True)

        ancho = pd.DataFrame(
            {f"col{i}": [f"valor_largo_{j}_{i}" for j in range(300)] for i in range(15)}
        )
        texto = preprocesar_excel_limpio(
            _construir_xlsx({f"H{k}": ancho for k in range(5)}), "t.xlsx"
        )
        # El total respeta el presupuesto (+ holgura por notas/encabezados).
        assert len(texto) <= 5000 + 500
        assert "presupuesto" in texto

    def test_reparto_no_omite_hojas(self, monkeypatch):
        # Varias hojas densas que juntas exceden el presupuesto: todas deben
        # aparecer (con su encabezado), ninguna se omite por completo.
        import Extraccion.extractor as extractor
        monkeypatch.setattr(extractor, "EXCEL_MAX_CHARS_POR_ARCHIVO", 6000, raising=True)

        ancho = pd.DataFrame(
            {f"col{i}": [f"valor_largo_{j}_{i}" for j in range(300)] for i in range(15)}
        )
        n_hojas = 5
        texto = preprocesar_excel_limpio(
            _construir_xlsx({f"H{k}": ancho for k in range(n_hojas)}), "t.xlsx"
        )
        assert texto.count("--- HOJA:") == n_hojas
        for k in range(n_hojas):
            assert f"--- HOJA: H{k} ---" in texto
        assert len(texto) <= 6000 + 500

    def test_arrastre_de_cuota(self, monkeypatch):
        # Hoja pequeña seguida de una grande: la grande debe recibir más que
        # presupuesto/N gracias al sobrante arrastrado de la pequeña.
        import Extraccion.extractor as extractor
        monkeypatch.setattr(extractor, "EXCEL_MAX_CHARS_POR_ARCHIVO", 4000, raising=True)

        pequena = pd.DataFrame({"x": [1, 2, 3]})
        grande = pd.DataFrame(
            {f"col{i}": [f"dato_{j}_{i}" for j in range(300)] for i in range(10)}
        )
        texto = preprocesar_excel_limpio(
            _construir_xlsx({"Pequena": pequena, "Grande": grande}), "t.xlsx"
        )
        # Aislar el bloque de la hoja grande.
        bloque_grande = texto.split("--- HOJA: Grande ---", 1)[1]
        # Con cuota fija sería ~2000 (4000/2); con arrastre la grande supera eso.
        assert len(bloque_grande) > 2000
        assert texto.count("--- HOJA:") == 2

    def test_multi_hoja_y_eliminacion_de_columna_vacia(self):
        a = pd.DataFrame({"x": [1, None, 3], "vacia": [None, None, None]})
        b = pd.DataFrame({"y": [10, 20]})
        texto = preprocesar_excel_limpio(_construir_xlsx({"A": a, "B": b}), "t.xlsx")
        assert texto.count("--- HOJA:") == 2
        assert "vacia" not in texto

    def test_hoja_vacia_tras_limpieza(self):
        vacia = pd.DataFrame({"c": [None, None]}, dtype="float64")
        texto = preprocesar_excel_limpio(_construir_xlsx({"V": vacia}), "t.xlsx")
        assert "HOJA VACÍA DESPUÉS DE LIMPIEZA" in texto
