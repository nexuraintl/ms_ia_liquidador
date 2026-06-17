"""
Tests para ExtractorZip y la integracion con ExtractorHibrido.

Cubre:
- ExtractorZip.extraer_de_zip  (unitario, ZIPs construidos en memoria)
- ExtractorZip limites de seguridad (max archivos, max tamano, ZIPs anidados)
- ExtractorHibrido._deduplicar_adjuntos_zip
- ExtractorHibrido._construir_indice_archivos
- ExtractorHibrido._es_duplicado
"""
import zipfile
import pytest
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

from Extraccion.extractor_zip import ExtractorZip
from Extraccion.extractor_adjuntos import AdjuntoExtraido
from app.extraccion_hibrida import ExtractorHibrido
from fastapi import UploadFile


# ---------------------------------------------------------------------------
# Helpers para construir ZIPs en memoria
# ---------------------------------------------------------------------------

def _construir_zip(*archivos: tuple[str, bytes]) -> bytes:
    """
    Construye un ZIP en memoria con los archivos indicados.

    Args:
        archivos: Tuplas (nombre_archivo, contenido_bytes)

    Returns:
        ZIP serializado como bytes
    """
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for nombre, contenido in archivos:
            zf.writestr(nombre, contenido)
    return buffer.getvalue()


def _crear_upload_file(nombre: str, contenido: bytes) -> UploadFile:
    """Crea un UploadFile sintetico para tests."""
    return UploadFile(file=BytesIO(contenido), filename=nombre)


# ===========================================================================
# Tests unitarios: ExtractorZip
# ===========================================================================

class TestExtractorZipBasico:
    """Tests basicos de extraccion ZIP."""

    def setup_method(self):
        self.extractor = ExtractorZip()

    def test_extraer_zip_con_un_archivo(self):
        contenido_pdf = b"%PDF-1.4 contenido de prueba"
        zip_bytes = _construir_zip(("factura.pdf", contenido_pdf))

        resultado = self.extractor.extraer_de_zip(zip_bytes, "test.zip")

        assert len(resultado) == 1
        assert resultado[0].nombre == "factura.pdf"
        assert resultado[0].contenido == contenido_pdf
        assert resultado[0].extension == "pdf"

    def test_extraer_zip_con_multiples_archivos(self):
        zip_bytes = _construir_zip(
            ("factura.pdf", b"pdf content"),
            ("datos.xlsx", b"excel content"),
            ("imagen.jpg", b"jpg content"),
        )

        resultado = self.extractor.extraer_de_zip(zip_bytes, "multi.zip")

        assert len(resultado) == 3
        nombres = {a.nombre for a in resultado}
        assert nombres == {"factura.pdf", "datos.xlsx", "imagen.jpg"}

    def test_extraer_zip_vacio(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
            pass
        zip_bytes = buffer.getvalue()

        resultado = self.extractor.extraer_de_zip(zip_bytes, "vacio.zip")

        assert resultado == []

    def test_extraer_zip_ignora_directorios(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
            zf.writestr("carpeta/", "")
            zf.writestr("carpeta/archivo.pdf", b"contenido")
        zip_bytes = buffer.getvalue()

        resultado = self.extractor.extraer_de_zip(zip_bytes, "con_carpeta.zip")

        assert len(resultado) == 1
        assert resultado[0].nombre == "archivo.pdf"

    def test_extraer_zip_ignora_macosx(self):
        zip_bytes = _construir_zip(
            ("__MACOSX/._factura.pdf", b"metadata mac"),
            ("factura.pdf", b"contenido real"),
        )

        resultado = self.extractor.extraer_de_zip(zip_bytes, "mac.zip")

        assert len(resultado) == 1
        assert resultado[0].nombre == "factura.pdf"

    def test_extraer_zip_sanitiza_path(self):
        zip_bytes = _construir_zip(
            ("carpeta/subcarpeta/factura.pdf", b"contenido"),
        )

        resultado = self.extractor.extraer_de_zip(zip_bytes, "nested_path.zip")

        assert len(resultado) == 1
        assert resultado[0].nombre == "factura.pdf"

    def test_zip_corrupto_retorna_lista_vacia(self):
        resultado = self.extractor.extraer_de_zip(b"no soy un zip", "corrupto.zip")

        assert resultado == []

    def test_bytes_vacios_retorna_lista_vacia(self):
        resultado = self.extractor.extraer_de_zip(b"", "vacio.zip")

        assert resultado == []


class TestExtractorZipSeguridad:
    """Tests de limites de seguridad."""

    def setup_method(self):
        self.extractor = ExtractorZip()

    def test_zip_anidado_es_ignorado(self):
        zip_interno = _construir_zip(("interno.pdf", b"pdf"))
        zip_bytes = _construir_zip(
            ("factura.pdf", b"contenido pdf"),
            ("otro.zip", zip_interno),
        )

        resultado = self.extractor.extraer_de_zip(zip_bytes, "anidado.zip")

        assert len(resultado) == 1
        assert resultado[0].nombre == "factura.pdf"

    def test_rar_anidado_es_ignorado(self):
        zip_bytes = _construir_zip(
            ("factura.pdf", b"contenido"),
            ("archivo.rar", b"fake rar"),
        )

        resultado = self.extractor.extraer_de_zip(zip_bytes, "con_rar.zip")

        assert len(resultado) == 1
        assert resultado[0].nombre == "factura.pdf"

    def test_excede_max_archivos(self):
        archivos = [(f"archivo_{i}.pdf", b"contenido") for i in range(25)]
        zip_bytes = _construir_zip(*archivos)

        resultado = self.extractor.extraer_de_zip(zip_bytes, "muchos.zip")

        assert resultado == []

    def test_excede_max_tamano_total(self):
        self.extractor.MAX_TAMANO_TOTAL_BYTES = 1024  # 1 KB para test
        zip_bytes = _construir_zip(("grande.pdf", b"x" * 2048))

        resultado = self.extractor.extraer_de_zip(zip_bytes, "grande.zip")

        assert resultado == []

    def test_dentro_de_limites_funciona(self):
        archivos = [(f"archivo_{i}.pdf", b"ok") for i in range(20)]
        zip_bytes = _construir_zip(*archivos)

        resultado = self.extractor.extraer_de_zip(zip_bytes, "limite.zip")

        assert len(resultado) == 20


# ===========================================================================
# Tests unitarios: Deduplicacion en ExtractorHibrido
# ===========================================================================

class TestDeduplicacionZip:
    """Tests de deduplicacion de adjuntos ZIP contra archivos existentes."""

    def setup_method(self):
        self.hibrido = ExtractorHibrido()

    def test_sin_duplicados_retorna_todos(self):
        adjuntos = [
            AdjuntoExtraido("nuevo.pdf", b"contenido nuevo", "pdf"),
        ]
        existentes = [
            _crear_upload_file("otro.pdf", b"contenido otro"),
        ]

        resultado = self.hibrido._deduplicar_adjuntos_zip(adjuntos, existentes, "test.zip")

        assert len(resultado) == 1
        assert resultado[0].nombre == "nuevo.pdf"

    def test_duplicado_exacto_es_omitido(self):
        contenido = b"mismo contenido exacto para ambos"
        adjuntos = [
            AdjuntoExtraido("factura.pdf", contenido, "pdf"),
        ]
        existentes = [
            _crear_upload_file("factura.pdf", contenido),
        ]

        resultado = self.hibrido._deduplicar_adjuntos_zip(adjuntos, existentes, "test.zip")

        assert len(resultado) == 0

    def test_duplicado_case_insensitive(self):
        contenido = b"contenido de prueba"
        adjuntos = [
            AdjuntoExtraido("Factura.PDF", contenido, "pdf"),
        ]
        existentes = [
            _crear_upload_file("factura.pdf", contenido),
        ]

        resultado = self.hibrido._deduplicar_adjuntos_zip(adjuntos, existentes, "test.zip")

        assert len(resultado) == 0

    def test_mismo_nombre_tamano_diferente_no_es_duplicado(self):
        adjuntos = [
            AdjuntoExtraido("factura.pdf", b"x" * 1000, "pdf"),
        ]
        existentes = [
            _crear_upload_file("factura.pdf", b"y" * 100),
        ]

        resultado = self.hibrido._deduplicar_adjuntos_zip(adjuntos, existentes, "test.zip")

        assert len(resultado) == 1

    def test_tamano_dentro_tolerancia_es_duplicado(self):
        adjuntos = [
            AdjuntoExtraido("factura.pdf", b"x" * 1000, "pdf"),
        ]
        existentes = [
            _crear_upload_file("factura.pdf", b"y" * 1050),
        ]

        resultado = self.hibrido._deduplicar_adjuntos_zip(adjuntos, existentes, "test.zip")

        assert len(resultado) == 0

    def test_mezcla_duplicados_y_nuevos(self):
        adjuntos = [
            AdjuntoExtraido("duplicado.pdf", b"contenido", "pdf"),
            AdjuntoExtraido("nuevo.xlsx", b"excel data", "xlsx"),
        ]
        existentes = [
            _crear_upload_file("duplicado.pdf", b"contenido"),
        ]

        resultado = self.hibrido._deduplicar_adjuntos_zip(adjuntos, existentes, "test.zip")

        assert len(resultado) == 1
        assert resultado[0].nombre == "nuevo.xlsx"

    def test_sin_archivos_existentes_retorna_todos(self):
        adjuntos = [
            AdjuntoExtraido("archivo.pdf", b"pdf", "pdf"),
            AdjuntoExtraido("datos.xlsx", b"excel", "xlsx"),
        ]

        resultado = self.hibrido._deduplicar_adjuntos_zip(adjuntos, [], "test.zip")

        assert len(resultado) == 2


class TestConstruirIndiceArchivos:
    """Tests para _construir_indice_archivos."""

    def setup_method(self):
        self.hibrido = ExtractorHibrido()

    def test_indice_con_archivos(self):
        archivos = [
            _crear_upload_file("Factura.pdf", b"contenido"),
            _crear_upload_file("datos.xlsx", b"excel"),
        ]

        indice = self.hibrido._construir_indice_archivos(archivos)

        assert "factura.pdf" in indice
        assert "datos.xlsx" in indice
        assert indice["factura.pdf"] == len(b"contenido")

    def test_indice_vacio(self):
        indice = self.hibrido._construir_indice_archivos([])

        assert indice == {}


class TestEsDuplicado:
    """Tests para _es_duplicado."""

    def setup_method(self):
        self.hibrido = ExtractorHibrido()

    def test_no_duplicado_nombre_diferente(self):
        adjunto = AdjuntoExtraido("nuevo.pdf", b"contenido", "pdf")
        existentes = {"otro.pdf": 9}

        assert not self.hibrido._es_duplicado(adjunto, existentes, "test.zip")

    def test_duplicado_nombre_y_tamano_igual(self):
        adjunto = AdjuntoExtraido("factura.pdf", b"123456789", "pdf")
        existentes = {"factura.pdf": 9}

        assert self.hibrido._es_duplicado(adjunto, existentes, "test.zip")

    def test_no_duplicado_tamano_muy_diferente(self):
        adjunto = AdjuntoExtraido("factura.pdf", b"x" * 1000, "pdf")
        existentes = {"factura.pdf": 100}

        assert not self.hibrido._es_duplicado(adjunto, existentes, "test.zip")
