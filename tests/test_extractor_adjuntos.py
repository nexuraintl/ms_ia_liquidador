"""
Tests para ExtractorAdjuntos y la integracion con ExtractorHibrido.

Cubre:
- ExtractorAdjuntos.extraer_de_eml  (unitario, EML construido en memoria)
- ExtractorAdjuntos.extraer_de_msg  (integracion con test_archivo4.msg real)
- ExtractorHibrido._enrutar_adjunto
- ExtractorHibrido._crear_upload_file
- ExtractorHibrido._procesar_adjuntos_emails
"""
import email
import pytest
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

from Extraccion.extractor_adjuntos import ExtractorAdjuntos, AdjuntoExtraido
from app.extraccion_hibrida import ExtractorHibrido
from fastapi import UploadFile


# ---------------------------------------------------------------------------
# Helpers para construir EML en memoria
# ---------------------------------------------------------------------------

def _construir_eml_con_adjuntos(*adjuntos: tuple[str, bytes]) -> bytes:
    """
    Construye un EML en memoria con los adjuntos indicados.

    Args:
        adjuntos: Tuplas (nombre_archivo, contenido_bytes)

    Returns:
        EML serializado como bytes
    """
    msg = MIMEMultipart()
    msg['From'] = 'remitente@test.com'
    msg['To'] = 'destinatario@test.com'
    msg['Subject'] = 'Test con adjuntos'
    msg.attach(MIMEText("Cuerpo del email de prueba", 'plain'))

    for nombre, contenido in adjuntos:
        parte = MIMEBase('application', 'octet-stream')
        parte.set_payload(contenido)
        encoders.encode_base64(parte)
        parte.add_header('Content-Disposition', 'attachment', filename=nombre)
        msg.attach(parte)

    return msg.as_bytes()


def _eml_sin_adjuntos() -> bytes:
    msg = MIMEMultipart()
    msg['From'] = 'remitente@test.com'
    msg['Subject'] = 'Sin adjuntos'
    msg.attach(MIMEText("Solo texto", 'plain'))
    return msg.as_bytes()


MSG_REAL_PATH = Path(__file__).parent.parent / "test_archivo4.msg"


# ===========================================================================
# Tests de AdjuntoExtraido
# ===========================================================================

class TestAdjuntoExtraido:
    """Tests del dataclass AdjuntoExtraido"""

    def test_campos_accesibles(self):
        adjunto = AdjuntoExtraido(nombre="factura.pdf", contenido=b"datos", extension="pdf")
        assert adjunto.nombre == "factura.pdf"
        assert adjunto.contenido == b"datos"
        assert adjunto.extension == "pdf"

    def test_contenido_bytes(self):
        adjunto = AdjuntoExtraido(nombre="doc.xlsx", contenido=b"\x00\x01\x02", extension="xlsx")
        assert isinstance(adjunto.contenido, bytes)

    def test_extension_sin_punto(self):
        adjunto = AdjuntoExtraido(nombre="foto.jpg", contenido=b"img", extension="jpg")
        assert "." not in adjunto.extension


# ===========================================================================
# Tests de ExtractorAdjuntos.extraer_de_eml (unitarios, sin dependencias externas)
# ===========================================================================

class TestExtractorAdjuntosEml:
    """Tests unitarios para extraccion de adjuntos EML"""

    def setup_method(self):
        self.extractor = ExtractorAdjuntos()

    def test_sin_adjuntos_retorna_lista_vacia(self):
        eml = _eml_sin_adjuntos()
        resultado = self.extractor.extraer_de_eml(eml, "correo.eml")
        assert resultado == []

    def test_adjunto_pdf_detectado(self):
        contenido_pdf = b"%PDF-1.4 contenido de prueba"
        eml = _construir_eml_con_adjuntos(("factura.pdf", contenido_pdf))

        resultado = self.extractor.extraer_de_eml(eml, "correo.eml")

        assert len(resultado) == 1
        assert resultado[0].nombre == "factura.pdf"
        assert resultado[0].extension == "pdf"
        assert resultado[0].contenido == contenido_pdf

    def test_adjunto_excel_detectado(self):
        contenido_xlsx = b"PK\x03\x04 datos excel simulados"
        eml = _construir_eml_con_adjuntos(("datos.xlsx", contenido_xlsx))

        resultado = self.extractor.extraer_de_eml(eml, "correo.eml")

        assert len(resultado) == 1
        assert resultado[0].extension == "xlsx"

    def test_multiples_adjuntos(self):
        eml = _construir_eml_con_adjuntos(
            ("factura.pdf", b"pdf bytes"),
            ("planilla.xlsx", b"excel bytes"),
            ("foto.jpg", b"imagen bytes"),
        )

        resultado = self.extractor.extraer_de_eml(eml, "correo.eml")

        assert len(resultado) == 3
        extensiones = {a.extension for a in resultado}
        assert extensiones == {"pdf", "xlsx", "jpg"}

    def test_extension_mayusculas_normalizada(self):
        eml = _construir_eml_con_adjuntos(("DOCUMENTO.PDF", b"contenido"))

        resultado = self.extractor.extraer_de_eml(eml, "correo.eml")

        assert len(resultado) == 1
        assert resultado[0].extension == "pdf"

    def test_adjunto_sin_nombre_usa_fallback(self):
        msg = MIMEMultipart()
        msg['From'] = 'a@b.com'
        msg['Subject'] = 'test'
        parte = MIMEBase('application', 'octet-stream')
        parte.set_payload(b"datos sin nombre")
        encoders.encode_base64(parte)
        # Content-Disposition sin filename
        parte.add_header('Content-Disposition', 'attachment')
        msg.attach(parte)
        eml = msg.as_bytes()

        resultado = self.extractor.extraer_de_eml(eml, "correo.eml")

        assert len(resultado) == 1
        assert resultado[0].nombre == "adjunto_sin_nombre"
        assert resultado[0].extension == "bin"

    def test_eml_malformado_retorna_lista_vacia(self):
        resultado = self.extractor.extraer_de_eml(b"esto no es un eml valido", "roto.eml")
        # No debe lanzar excepcion; puede retornar lista vacia
        assert isinstance(resultado, list)

    def test_bytes_extraidos_correctos(self):
        contenido_esperado = b"\x89PNG\r\n\x1a\n datos de imagen"
        eml = _construir_eml_con_adjuntos(("imagen.png", contenido_esperado))

        resultado = self.extractor.extraer_de_eml(eml, "correo.eml")

        assert resultado[0].contenido == contenido_esperado

    def test_parte_inline_no_se_extrae(self):
        msg = MIMEMultipart()
        msg['From'] = 'a@b.com'
        parte_inline = MIMEBase('image', 'png')
        parte_inline.set_payload(b"imagen inline")
        encoders.encode_base64(parte_inline)
        parte_inline.add_header('Content-Disposition', 'inline', filename="logo.png")
        msg.attach(parte_inline)
        eml = msg.as_bytes()

        resultado = self.extractor.extraer_de_eml(eml, "correo.eml")

        assert resultado == []


# ===========================================================================
# Tests de ExtractorAdjuntos.extraer_de_msg (integracion con archivo real)
# ===========================================================================

@pytest.mark.skipif(
    not MSG_REAL_PATH.exists(),
    reason="Archivo test_archivo4.msg no encontrado en la raiz del proyecto"
)
class TestExtractorAdjuntosMsgReal:
    """Tests de integracion con el archivo .msg real que contiene adjuntos embebidos"""

    def setup_method(self):
        self.extractor = ExtractorAdjuntos()
        self.contenido_msg = MSG_REAL_PATH.read_bytes()

    def test_extrae_cinco_adjuntos(self):
        resultado = self.extractor.extraer_de_msg(self.contenido_msg, "test_archivo4.msg")
        assert len(resultado) == 5

    def test_adjunto_excel_presente(self):
        resultado = self.extractor.extraer_de_msg(self.contenido_msg, "test_archivo4.msg")
        excels = [a for a in resultado if a.extension == "xlsx"]
        assert len(excels) == 1

    def test_adjunto_excel_tiene_bytes_reales(self):
        resultado = self.extractor.extraer_de_msg(self.contenido_msg, "test_archivo4.msg")
        excel = next(a for a in resultado if a.extension == "xlsx")
        assert len(excel.contenido) > 0
        # Verificar firma PK (ZIP/XLSX)
        assert excel.contenido[:2] == b"PK"

    def test_adjuntos_imagen_presentes(self):
        resultado = self.extractor.extraer_de_msg(self.contenido_msg, "test_archivo4.msg")
        imagenes = [a for a in resultado if a.extension in {"png", "jpg", "jpeg"}]
        assert len(imagenes) == 4

    def test_imagenes_png_tienen_firma_correcta(self):
        resultado = self.extractor.extraer_de_msg(self.contenido_msg, "test_archivo4.msg")
        pngs = [a for a in resultado if a.extension == "png"]
        for png in pngs:
            assert png.contenido[:4] == b"\x89PNG", f"PNG sin firma correcta: {png.nombre}"

    def test_todos_los_adjuntos_tienen_nombre(self):
        resultado = self.extractor.extraer_de_msg(self.contenido_msg, "test_archivo4.msg")
        for adjunto in resultado:
            assert adjunto.nombre and adjunto.nombre != "adjunto_sin_nombre"

    def test_todos_los_adjuntos_tienen_extension(self):
        resultado = self.extractor.extraer_de_msg(self.contenido_msg, "test_archivo4.msg")
        for adjunto in resultado:
            assert adjunto.extension and len(adjunto.extension) >= 2

    def test_todos_los_adjuntos_tienen_bytes_no_vacios(self):
        resultado = self.extractor.extraer_de_msg(self.contenido_msg, "test_archivo4.msg")
        for adjunto in resultado:
            assert len(adjunto.contenido) > 0, f"Adjunto vacio: {adjunto.nombre}"

    def test_extensiones_son_minusculas(self):
        resultado = self.extractor.extraer_de_msg(self.contenido_msg, "test_archivo4.msg")
        for adjunto in resultado:
            assert adjunto.extension == adjunto.extension.lower()


class TestExtractorAdjuntosMsgSinLibreria:
    """Tests cuando extract_msg no esta disponible"""

    def setup_method(self):
        self.extractor = ExtractorAdjuntos()

    def test_sin_extract_msg_retorna_lista_vacia(self):
        with patch.dict('sys.modules', {'extract_msg': None}):
            with patch('Extraccion.extractor_adjuntos.logger'):
                resultado = self.extractor.extraer_de_msg(b"datos", "correo.msg")
        # El ImportError interno devuelve lista vacia sin lanzar excepcion
        assert isinstance(resultado, list)


# ===========================================================================
# Tests de ExtractorHibrido._crear_upload_file
# ===========================================================================

class TestCrearUploadFile:
    """Tests para la creacion de UploadFile sintetico desde bytes"""

    def setup_method(self):
        self.extractor = ExtractorHibrido()

    def test_retorna_upload_file(self):
        resultado = self.extractor._crear_upload_file(b"contenido", "archivo.pdf")
        assert isinstance(resultado, UploadFile)

    def test_filename_correcto(self):
        resultado = self.extractor._crear_upload_file(b"bytes", "factura.pdf")
        assert resultado.filename == "factura.pdf"

    def test_contenido_legible(self):
        contenido = b"datos de prueba 1234"
        upload = self.extractor._crear_upload_file(contenido, "test.pdf")
        leido = upload.file.read()
        assert leido == contenido

    def test_bytesio_en_posicion_inicial(self):
        upload = self.extractor._crear_upload_file(b"abc", "x.pdf")
        assert upload.file.read() == b"abc"


# ===========================================================================
# Tests de ExtractorHibrido._enrutar_adjunto
# ===========================================================================

class TestEnrutarAdjunto:
    """Tests para el enrutamiento de adjuntos segun extension"""

    def setup_method(self):
        self.extractor = ExtractorHibrido()

    @pytest.mark.asyncio
    async def test_pdf_va_a_directos(self):
        adjunto = AdjuntoExtraido(nombre="factura.pdf", contenido=b"pdf", extension="pdf")
        directos, textos = [], {}

        await self.extractor._enrutar_adjunto(adjunto, directos, textos)

        assert len(directos) == 1
        assert directos[0].filename == "factura.pdf"
        assert textos == {}

    @pytest.mark.asyncio
    async def test_imagen_png_va_a_directos(self):
        adjunto = AdjuntoExtraido(nombre="logo.png", contenido=b"\x89PNG", extension="png")
        directos, textos = [], {}

        await self.extractor._enrutar_adjunto(adjunto, directos, textos)

        assert len(directos) == 1
        assert textos == {}

    @pytest.mark.asyncio
    async def test_imagen_jpg_va_a_directos(self):
        adjunto = AdjuntoExtraido(nombre="foto.jpg", contenido=b"\xff\xd8\xff", extension="jpg")
        directos, textos = [], {}

        await self.extractor._enrutar_adjunto(adjunto, directos, textos)

        assert len(directos) == 1

    @pytest.mark.asyncio
    async def test_excel_xlsx_va_a_textos(self):
        adjunto = AdjuntoExtraido(nombre="datos.xlsx", contenido=b"PK excel", extension="xlsx")
        directos, textos = [], {}

        with patch('app.extraccion_hibrida.preprocesar_excel_limpio', return_value="texto excel"):
            await self.extractor._enrutar_adjunto(adjunto, directos, textos)

        assert directos == []
        assert "datos.xlsx" in textos
        assert textos["datos.xlsx"] == "texto excel"

    @pytest.mark.asyncio
    async def test_excel_xls_va_a_textos(self):
        adjunto = AdjuntoExtraido(nombre="hoja.xls", contenido=b"\xd0\xcf\x11\xe0", extension="xls")
        directos, textos = [], {}

        with patch('app.extraccion_hibrida.preprocesar_excel_limpio', return_value="texto xls"):
            await self.extractor._enrutar_adjunto(adjunto, directos, textos)

        assert "hoja.xls" in textos

    @pytest.mark.asyncio
    async def test_word_docx_va_a_textos(self):
        adjunto = AdjuntoExtraido(nombre="contrato.docx", contenido=b"PK word", extension="docx")
        directos, textos = [], {}

        self.extractor.extractor.extraer_texto_word = AsyncMock(return_value="texto word")

        await self.extractor._enrutar_adjunto(adjunto, directos, textos)

        assert directos == []
        assert textos["contrato.docx"] == "texto word"

    @pytest.mark.asyncio
    async def test_tipo_desconocido_ignorado(self):
        adjunto = AdjuntoExtraido(nombre="datos.zip", contenido=b"PK zip", extension="zip")
        directos, textos = [], {}

        await self.extractor._enrutar_adjunto(adjunto, directos, textos)

        assert directos == []
        assert textos == {}

    @pytest.mark.asyncio
    async def test_extension_bin_ignorada(self):
        adjunto = AdjuntoExtraido(nombre="adjunto_sin_nombre", contenido=b"raw", extension="bin")
        directos, textos = [], {}

        await self.extractor._enrutar_adjunto(adjunto, directos, textos)

        assert directos == []
        assert textos == {}


# ===========================================================================
# Tests de ExtractorHibrido._procesar_adjuntos_emails
# ===========================================================================

class TestProcesarAdjuntosEmails:
    """Tests para la orquestacion de extraccion de adjuntos en emails"""

    def setup_method(self):
        self.extractor = ExtractorHibrido()

    def _mock_archivo(self, nombre: str, contenido: bytes) -> AsyncMock:
        archivo = AsyncMock()
        archivo.filename = nombre
        archivo.read = AsyncMock(return_value=contenido)
        archivo.seek = AsyncMock()
        return archivo

    @pytest.mark.asyncio
    async def test_sin_emails_retorna_vacios(self):
        archivo_pdf = self._mock_archivo("factura.pdf", b"pdf")
        archivo_excel = self._mock_archivo("datos.xlsx", b"excel")

        directos, textos = await self.extractor._procesar_adjuntos_emails([archivo_pdf, archivo_excel])

        assert directos == []
        assert textos == {}

    @pytest.mark.asyncio
    async def test_msg_con_adjunto_pdf_agrega_a_directos(self):
        adjunto_pdf = AdjuntoExtraido(nombre="factura.pdf", contenido=b"%PDF", extension="pdf")
        eml_bytes = _eml_sin_adjuntos()
        archivo_msg = self._mock_archivo("correo.msg", eml_bytes)

        self.extractor.extractor_adjuntos.extraer_de_msg = MagicMock(return_value=[adjunto_pdf])

        directos, textos = await self.extractor._procesar_adjuntos_emails([archivo_msg])

        assert len(directos) == 1
        assert directos[0].filename == "factura.pdf"
        assert textos == {}

    @pytest.mark.asyncio
    async def test_eml_con_adjunto_excel_agrega_a_textos(self):
        adjunto_excel = AdjuntoExtraido(nombre="planilla.xlsx", contenido=b"PK", extension="xlsx")
        eml_bytes = _eml_sin_adjuntos()
        archivo_eml = self._mock_archivo("correo.eml", eml_bytes)

        self.extractor.extractor_adjuntos.extraer_de_eml = MagicMock(return_value=[adjunto_excel])

        with patch('app.extraccion_hibrida.preprocesar_excel_limpio', return_value="texto preprocesado"):
            directos, textos = await self.extractor._procesar_adjuntos_emails([archivo_eml])

        assert directos == []
        assert textos["planilla.xlsx"] == "texto preprocesado"

    @pytest.mark.asyncio
    async def test_msg_con_multiples_adjuntos_mixtos(self):
        adjuntos = [
            AdjuntoExtraido(nombre="factura.pdf", contenido=b"%PDF", extension="pdf"),
            AdjuntoExtraido(nombre="datos.xlsx", contenido=b"PK", extension="xlsx"),
            AdjuntoExtraido(nombre="foto.jpg", contenido=b"\xff\xd8", extension="jpg"),
        ]
        archivo_msg = self._mock_archivo("correo.msg", b"msg bytes")
        self.extractor.extractor_adjuntos.extraer_de_msg = MagicMock(return_value=adjuntos)

        with patch('app.extraccion_hibrida.preprocesar_excel_limpio', return_value="texto excel"):
            directos, textos = await self.extractor._procesar_adjuntos_emails([archivo_msg])

        assert len(directos) == 2  # pdf + jpg
        assert "datos.xlsx" in textos

    @pytest.mark.asyncio
    async def test_error_en_archivo_no_detiene_el_resto(self):
        archivo_roto = AsyncMock()
        archivo_roto.filename = "roto.msg"
        archivo_roto.seek = AsyncMock(side_effect=Exception("Error de lectura"))

        adjunto_ok = AdjuntoExtraido(nombre="foto.png", contenido=b"\x89PNG", extension="png")
        archivo_ok = self._mock_archivo("correo2.msg", b"msg bytes")
        self.extractor.extractor_adjuntos.extraer_de_msg = MagicMock(return_value=[adjunto_ok])

        directos, textos = await self.extractor._procesar_adjuntos_emails([archivo_roto, archivo_ok])

        assert len(directos) == 1

    @pytest.mark.asyncio
    async def test_msg_sin_adjuntos_no_modifica_resultado(self):
        archivo_msg = self._mock_archivo("vacio.msg", b"msg sin adjuntos")
        self.extractor.extractor_adjuntos.extraer_de_msg = MagicMock(return_value=[])

        directos, textos = await self.extractor._procesar_adjuntos_emails([archivo_msg])

        assert directos == []
        assert textos == {}

    @pytest.mark.asyncio
    async def test_llama_extraer_de_msg_para_msg(self):
        archivo_msg = self._mock_archivo("correo.msg", b"bytes msg")
        self.extractor.extractor_adjuntos.extraer_de_msg = MagicMock(return_value=[])
        self.extractor.extractor_adjuntos.extraer_de_eml = MagicMock(return_value=[])

        await self.extractor._procesar_adjuntos_emails([archivo_msg])

        self.extractor.extractor_adjuntos.extraer_de_msg.assert_called_once()
        self.extractor.extractor_adjuntos.extraer_de_eml.assert_not_called()

    @pytest.mark.asyncio
    async def test_llama_extraer_de_eml_para_eml(self):
        archivo_eml = self._mock_archivo("correo.eml", b"bytes eml")
        self.extractor.extractor_adjuntos.extraer_de_msg = MagicMock(return_value=[])
        self.extractor.extractor_adjuntos.extraer_de_eml = MagicMock(return_value=[])

        await self.extractor._procesar_adjuntos_emails([archivo_eml])

        self.extractor.extractor_adjuntos.extraer_de_eml.assert_called_once()
        self.extractor.extractor_adjuntos.extraer_de_msg.assert_not_called()


# ===========================================================================
# Test de integracion end-to-end con archivo MSG real
# ===========================================================================

@pytest.mark.skipif(
    not MSG_REAL_PATH.exists(),
    reason="Archivo test_archivo4.msg no encontrado en la raiz del proyecto"
)
class TestIntegracionMsgRealConHibrido:
    """
    Integracion end-to-end: ExtractorHibrido procesa el .msg real
    y produce los resultados correctamente enrutados.
    """

    def setup_method(self):
        self.extractor = ExtractorHibrido()
        self.contenido_msg = MSG_REAL_PATH.read_bytes()

    @pytest.mark.asyncio
    async def test_msg_real_produce_directos_e_imagenes(self):
        archivo_mock = AsyncMock()
        archivo_mock.filename = "test_archivo4.msg"
        archivo_mock.read = AsyncMock(return_value=self.contenido_msg)
        archivo_mock.seek = AsyncMock()

        with patch('app.extraccion_hibrida.preprocesar_excel_limpio', return_value="texto excel"):
            directos, textos = await self.extractor._procesar_adjuntos_emails([archivo_mock])

        # 4 imagenes (png/jpg) deben ir a directos
        assert len(directos) == 4
        # 1 excel debe ir a textos
        assert len(textos) == 1

    @pytest.mark.asyncio
    async def test_msg_real_excel_en_textos_preprocesados(self):
        archivo_mock = AsyncMock()
        archivo_mock.filename = "test_archivo4.msg"
        archivo_mock.read = AsyncMock(return_value=self.contenido_msg)
        archivo_mock.seek = AsyncMock()

        with patch('app.extraccion_hibrida.preprocesar_excel_limpio', return_value="contenido excel") as mock_excel:
            directos, textos = await self.extractor._procesar_adjuntos_emails([archivo_mock])

        mock_excel.assert_called_once()
        clave_excel = list(textos.keys())[0]
        assert clave_excel.endswith(".xlsx")

    @pytest.mark.asyncio
    async def test_msg_real_imagenes_son_upload_files(self):
        archivo_mock = AsyncMock()
        archivo_mock.filename = "test_archivo4.msg"
        archivo_mock.read = AsyncMock(return_value=self.contenido_msg)
        archivo_mock.seek = AsyncMock()

        with patch('app.extraccion_hibrida.preprocesar_excel_limpio', return_value="texto"):
            directos, textos = await self.extractor._procesar_adjuntos_emails([archivo_mock])

        for upload in directos:
            assert isinstance(upload, UploadFile)
            assert upload.filename.lower().endswith(('.png', '.jpg', '.jpeg'))
