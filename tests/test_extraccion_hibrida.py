"""
Tests para el módulo de extracción híbrida.
Siguiendo TDD: Tests para validar ExtractorHibrido.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from app.extraccion_hibrida import ExtractorHibrido, ResultadoExtraccion


class TestExtractorHibrido:
    """Tests para ExtractorHibrido"""

    def setup_method(self):
        """Setup ejecutado antes de cada test"""
        self.extractor = ExtractorHibrido()

    def test_inicializacion_correcta(self):
        """Debe inicializar correctamente los componentes necesarios"""
        # Assert
        assert self.extractor.extractor is not None
        assert self.extractor.validador is not None

    def test_clasificar_por_estrategia_archivos_directos(self):
        """Debe clasificar PDFs e imágenes como archivos directos"""
        # Arrange
        archivo_pdf = Mock()
        archivo_pdf.filename = "factura.pdf"

        archivo_imagen = Mock()
        archivo_imagen.filename = "foto.jpg"

        archivos = [archivo_pdf, archivo_imagen]

        # Act
        directos, preprocesamiento = self.extractor._clasificar_por_estrategia(archivos)

        # Assert
        assert len(directos) == 2
        assert len(preprocesamiento) == 0
        assert archivo_pdf in directos
        assert archivo_imagen in directos

    def test_clasificar_por_estrategia_archivos_preprocesamiento(self):
        """Debe clasificar Excel y Word como archivos de preprocesamiento"""
        # Arrange
        archivo_excel = Mock()
        archivo_excel.filename = "datos.xlsx"

        archivo_word = Mock()
        archivo_word.filename = "documento.docx"

        archivos = [archivo_excel, archivo_word]

        # Act
        directos, preprocesamiento = self.extractor._clasificar_por_estrategia(archivos)

        # Assert
        assert len(directos) == 0
        assert len(preprocesamiento) == 2
        assert archivo_excel in preprocesamiento
        assert archivo_word in preprocesamiento

    def test_clasificar_por_estrategia_mixto(self):
        """Debe clasificar correctamente archivos mixtos"""
        # Arrange
        archivo_pdf = Mock()
        archivo_pdf.filename = "factura.pdf"

        archivo_excel = Mock()
        archivo_excel.filename = "datos.xlsx"

        archivo_png = Mock()
        archivo_png.filename = "imagen.png"

        archivo_email = Mock()
        archivo_email.filename = "correo.eml"

        archivos = [archivo_pdf, archivo_excel, archivo_png, archivo_email]

        # Act
        directos, preprocesamiento = self.extractor._clasificar_por_estrategia(archivos)

        # Assert
        assert len(directos) == 2  # PDF + PNG
        assert len(preprocesamiento) == 2  # Excel + Email
        assert archivo_pdf in directos
        assert archivo_png in directos
        assert archivo_excel in preprocesamiento
        assert archivo_email in preprocesamiento

    def test_clasificar_por_estrategia_extension_mayusculas(self):
        """Debe manejar extensiones en mayúsculas correctamente"""
        # Arrange
        archivo = Mock()
        archivo.filename = "FACTURA.PDF"

        archivos = [archivo]

        # Act
        directos, preprocesamiento = self.extractor._clasificar_por_estrategia(archivos)

        # Assert
        assert len(directos) == 1
        assert len(preprocesamiento) == 0

    def test_clasificar_por_estrategia_sin_extension(self):
        """Debe manejar archivos sin extensión enviándolos a preprocesamiento"""
        # Arrange
        archivo = Mock()
        archivo.filename = "archivo_sin_extension"

        archivos = [archivo]

        # Act
        directos, preprocesamiento = self.extractor._clasificar_por_estrategia(archivos)

        # Assert
        assert len(directos) == 0
        assert len(preprocesamiento) == 1
        assert archivo in preprocesamiento

    def test_clasificar_por_estrategia_error_manejo(self):
        """Debe manejar errores enviando archivos a preprocesamiento por seguridad"""
        # Arrange
        archivo_error = Mock()
        archivo_error.filename = None  # Causa error al intentar extraer extensión

        archivos = [archivo_error]

        # Act
        directos, preprocesamiento = self.extractor._clasificar_por_estrategia(archivos)

        # Assert - Por seguridad, archivos con error van a preprocesamiento
        assert len(preprocesamiento) == 1
        assert archivo_error in preprocesamiento

    @pytest.mark.asyncio
    async def test_procesar_archivos_locales_con_archivos(self):
        """Debe procesar archivos cuando hay archivos de preprocesamiento"""
        # Arrange
        archivo = Mock()
        archivo.filename = "datos.xlsx"
        archivos = [archivo]

        # Mock del procesador
        mock_textos = {"datos.xlsx": "contenido extraído"}
        self.extractor.extractor.procesar_multiples_archivos = AsyncMock(return_value=mock_textos)

        # Act
        resultado = await self.extractor._procesar_archivos_locales(archivos)

        # Assert
        assert resultado == mock_textos
        self.extractor.extractor.procesar_multiples_archivos.assert_called_once_with(archivos)

    @pytest.mark.asyncio
    async def test_procesar_archivos_locales_sin_archivos(self):
        """Debe retornar diccionario vacío cuando no hay archivos"""
        # Arrange
        archivos = []

        # Act
        resultado = await self.extractor._procesar_archivos_locales(archivos)

        # Assert
        assert resultado == {}

    @pytest.mark.asyncio
    async def test_preprocesar_excel_archivo_excel(self):
        """Debe preprocesar archivos Excel correctamente"""
        # Arrange
        textos_originales = {"datos.xlsx": "contenido original"}

        archivo_mock = AsyncMock()
        archivo_mock.filename = "datos.xlsx"
        archivo_mock.read = AsyncMock(return_value=b"contenido binario")

        archivos = [archivo_mock]

        # Mock de preprocesar_excel_limpio
        with patch('app.extraccion_hibrida.preprocesar_excel_limpio') as mock_preprocesar:
            mock_preprocesar.return_value = "contenido preprocesado"

            # Act
            resultado = await self.extractor._preprocesar_excel(textos_originales, archivos)

            # Assert
            assert resultado["datos.xlsx"] == "contenido preprocesado"
            mock_preprocesar.assert_called_once()
            archivo_mock.seek.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_preprocesar_excel_archivo_no_excel(self):
        """Debe mantener contenido original para archivos no-Excel"""
        # Arrange
        textos_originales = {"documento.docx": "contenido word"}
        archivos = []

        # Act
        resultado = await self.extractor._preprocesar_excel(textos_originales, archivos)

        # Assert
        assert resultado["documento.docx"] == "contenido word"

    @pytest.mark.asyncio
    async def test_preprocesar_excel_error_manejo(self):
        """Debe usar contenido original si falla el preprocesamiento"""
        # Arrange
        textos_originales = {"datos.xlsx": "contenido original"}

        archivo_mock = AsyncMock()
        archivo_mock.filename = "datos.xlsx"
        archivo_mock.read = AsyncMock(side_effect=Exception("Error de lectura"))

        archivos = [archivo_mock]

        # Act
        resultado = await self.extractor._preprocesar_excel(textos_originales, archivos)

        # Assert - Debe usar contenido original cuando hay error
        assert resultado["datos.xlsx"] == "contenido original"

    @pytest.mark.asyncio
    async def test_preprocesar_excel_archivo_no_encontrado(self):
        """Debe usar contenido original si no encuentra archivo físico"""
        # Arrange
        textos_originales = {"datos.xlsx": "contenido original"}

        # Lista vacía - archivo no disponible
        archivos = []

        # Act
        resultado = await self.extractor._preprocesar_excel(textos_originales, archivos)

        # Assert
        assert resultado["datos.xlsx"] == "contenido original"

    @pytest.mark.asyncio
    async def test_extraer_flujo_completo(self):
        """Debe ejecutar el flujo completo de extracción correctamente"""
        # Arrange
        archivo_pdf = Mock()
        archivo_pdf.filename = "factura.pdf"

        archivo_excel = Mock()
        archivo_excel.filename = "datos.xlsx"

        archivos_validos = [archivo_pdf, archivo_excel]

        # Mock de métodos internos
        with patch.object(self.extractor, '_clasificar_por_estrategia') as mock_clasificar:
            with patch.object(self.extractor, '_procesar_archivos_locales') as mock_procesar:
                with patch.object(self.extractor, '_preprocesar_excel') as mock_preprocesar:
                    # Setup mocks
                    mock_clasificar.return_value = ([archivo_pdf], [archivo_excel])
                    mock_procesar.return_value = {"datos.xlsx": "texto"}
                    mock_preprocesar.return_value = {"datos.xlsx": "texto preprocesado"}

                    # Act
                    resultado = await self.extractor.extraer(archivos_validos)

                    # Assert
                    assert isinstance(resultado, ResultadoExtraccion)
                    assert len(resultado.archivos_directos) == 1
                    assert resultado.archivos_directos[0] == archivo_pdf
                    assert resultado.textos_preprocesados == {"datos.xlsx": "texto preprocesado"}

                    # Verificar llamadas
                    mock_clasificar.assert_called_once_with(archivos_validos)
                    mock_procesar.assert_called_once()
                    mock_preprocesar.assert_called_once()

    @pytest.mark.asyncio
    async def test_extraer_solo_archivos_directos(self):
        """Debe manejar caso con solo archivos directos (sin preprocesamiento)"""
        # Arrange
        archivo_pdf = Mock()
        archivo_pdf.filename = "factura.pdf"

        archivos_validos = [archivo_pdf]

        # Mock para retornar solo archivos directos
        with patch.object(self.extractor, '_clasificar_por_estrategia') as mock_clasificar:
            with patch.object(self.extractor, '_procesar_archivos_locales') as mock_procesar:
                with patch.object(self.extractor, '_preprocesar_excel') as mock_preprocesar:
                    mock_clasificar.return_value = ([archivo_pdf], [])
                    mock_procesar.return_value = {}
                    mock_preprocesar.return_value = {}

                    # Act
                    resultado = await self.extractor.extraer(archivos_validos)

                    # Assert
                    assert len(resultado.archivos_directos) == 1
                    assert len(resultado.textos_preprocesados) == 0

    @pytest.mark.asyncio
    async def test_extraer_solo_archivos_preprocesamiento(self):
        """Debe manejar caso con solo archivos de preprocesamiento"""
        # Arrange
        archivo_excel = Mock()
        archivo_excel.filename = "datos.xlsx"

        archivos_validos = [archivo_excel]

        # Mock para retornar solo archivos de preprocesamiento
        with patch.object(self.extractor, '_clasificar_por_estrategia') as mock_clasificar:
            with patch.object(self.extractor, '_procesar_archivos_locales') as mock_procesar:
                with patch.object(self.extractor, '_preprocesar_excel') as mock_preprocesar:
                    mock_clasificar.return_value = ([], [archivo_excel])
                    mock_procesar.return_value = {"datos.xlsx": "texto"}
                    mock_preprocesar.return_value = {"datos.xlsx": "texto procesado"}

                    # Act
                    resultado = await self.extractor.extraer(archivos_validos)

                    # Assert
                    assert len(resultado.archivos_directos) == 0
                    assert len(resultado.textos_preprocesados) == 1


class TestResultadoExtraccion:
    """Tests para ResultadoExtraccion"""

    def test_puede_desempaquetar_como_tupla(self):
        """ResultadoExtraccion debe ser desempaquetable como tupla"""
        # Arrange
        archivo_mock = Mock()
        archivo_mock.filename = "test.pdf"
        textos_mock = {"archivo.txt": "contenido"}

        resultado = ResultadoExtraccion(
            archivos_directos=[archivo_mock],
            textos_preprocesados=textos_mock
        )

        # Act
        directos, preprocesados = resultado

        # Assert
        assert isinstance(directos, list)
        assert isinstance(preprocesados, dict)
        assert len(directos) == 1
        assert preprocesados == textos_mock

    def test_acceso_por_atributos(self):
        """Debe permitir acceso por atributos"""
        # Arrange
        archivo_mock = Mock()
        textos_mock = {"archivo.txt": "contenido"}

        resultado = ResultadoExtraccion(
            archivos_directos=[archivo_mock],
            textos_preprocesados=textos_mock
        )

        # Act & Assert
        assert resultado.archivos_directos == [archivo_mock]
        assert resultado.textos_preprocesados == textos_mock

    def test_dataclass_inmutabilidad(self):
        """Debe comportarse como dataclass con campos tipados"""
        # Arrange & Act
        resultado = ResultadoExtraccion(
            archivos_directos=[],
            textos_preprocesados={}
        )

        # Assert
        assert hasattr(resultado, 'archivos_directos')
        assert hasattr(resultado, 'textos_preprocesados')
        assert isinstance(resultado.archivos_directos, list)
        assert isinstance(resultado.textos_preprocesados, dict)