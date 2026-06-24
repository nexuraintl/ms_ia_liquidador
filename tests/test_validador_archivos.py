"""
Tests para el módulo de validación de archivos.
Siguiendo TDD: Tests escritos antes de la implementación.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from app.validacion_archivos import ValidadorArchivos, ResultadoValidacionArchivos


class TestValidadorArchivos:
    """Tests para ValidadorArchivos"""

    def setup_method(self):
        """Setup ejecutado antes de cada test"""
        self.validador = ValidadorArchivos()

    def test_inicializacion_correcta(self):
        """Debe inicializar con extensiones soportadas"""
        # Assert
        assert self.validador.extensiones_soportadas is not None
        assert 'pdf' in self.validador.extensiones_soportadas
        assert 'xlsx' in self.validador.extensiones_soportadas

    def test_extraer_extension_minusculas(self):
        """Debe extraer extensión sin punto en minúsculas"""
        # Arrange
        nombre_archivo = "nombrearchivopdf.pdf"

        # Act
        resultado = self.validador._extraer_extension(nombre_archivo)

        # Assert
        assert "pdf" == resultado

    def test_extraer_extension_mayusculas(self):
        """Debe convertir extensiones en mayúsculas a minúsculas"""
        # Arrange
        nombre_archivo = "DOCUMENTO.PDF"

        # Act
        resultado = self.validador._extraer_extension(nombre_archivo)

        # Assert
        assert "pdf" == resultado

    def test_extraer_extension_sin_extension(self):
        """Debe retornar string vacío para archivos sin extensión"""
        # Arrange
        nombre_archivo = "archivo_sin_extension"

        # Act
        resultado = self.validador._extraer_extension(nombre_archivo)

        # Assert
        assert "" == resultado

    def test_extraer_extension_multiples_puntos(self):
        """Debe extraer solo la última extensión en nombres con múltiples puntos"""
        # Arrange
        nombre_archivo = "archivo.backup.2024.xlsx"

        # Act
        resultado = self.validador._extraer_extension(nombre_archivo)

        # Assert
        assert "xlsx" == resultado

    def test_filtrar_por_extension_archivos_validos(self):
        """Debe filtrar correctamente archivos con extensión válida"""
        # Arrange
        archivo_pdf = Mock()
        archivo_pdf.filename = "factura.pdf"

        archivo_excel = Mock()
        archivo_excel.filename = "datos.xlsx"

        archivos = [archivo_pdf, archivo_excel]

        # Act
        validos, ignorados = self.validador._filtrar_por_extension(archivos)

        # Assert
        assert len(validos) == 2
        assert len(ignorados) == 0
        assert archivo_pdf in validos
        assert archivo_excel in validos

    def test_filtrar_por_extension_archivos_invalidos(self):
        """Debe filtrar archivos con extensión no soportada"""
        # Arrange
        archivo_exe = Mock()
        archivo_exe.filename = "virus.exe"

        archivo_bat = Mock()
        archivo_bat.filename = "script.bat"

        archivos = [archivo_exe, archivo_bat]

        # Act
        validos, ignorados = self.validador._filtrar_por_extension(archivos)

        # Assert
        assert len(validos) == 0
        assert len(ignorados) == 2
        assert "virus.exe" in ignorados
        assert "script.bat" in ignorados

    def test_filtrar_por_extension_mixto(self):
        """Debe separar correctamente archivos válidos e inválidos"""
        # Arrange
        archivo_valido = Mock()
        archivo_valido.filename = "documento.pdf"

        archivo_invalido = Mock()
        archivo_invalido.filename = "malware.exe"

        archivos = [archivo_valido, archivo_invalido]

        # Act
        validos, ignorados = self.validador._filtrar_por_extension(archivos)

        # Assert
        assert len(validos) == 1
        assert len(ignorados) == 1
        assert archivo_valido in validos
        assert "malware.exe" in ignorados

    def test_filtrar_por_extension_error_manejo(self):
        """Debe manejar errores agregando archivo a ignorados"""
        # Arrange
        archivo_error = Mock()
        archivo_error.filename = None  # Causa error

        archivos = [archivo_error]

        # Act
        validos, ignorados = self.validador._filtrar_por_extension(archivos)

        # Assert
        assert len(validos) == 0
        assert len(ignorados) == 1

    def test_validar_minimo_un_archivo_con_archivos(self):
        """No debe lanzar excepción si hay archivos válidos"""
        # Arrange
        archivo = Mock()
        archivo.filename = "test.pdf"
        archivos_validos = [archivo]
        archivos_originales = [archivo]

        # Act & Assert - No debe lanzar excepción
        try:
            self.validador._validar_minimo_un_archivo(archivos_validos, archivos_originales)
        except HTTPException:
            pytest.fail("No debería lanzar HTTPException con archivos válidos")

    def test_validar_minimo_un_archivo_sin_archivos(self):
        """Debe lanzar HTTPException si no hay archivos válidos"""
        # Arrange
        archivo_invalido = Mock()
        archivo_invalido.filename = "test.exe"

        archivos_validos = []
        archivos_originales = [archivo_invalido]

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            self.validador._validar_minimo_un_archivo(archivos_validos, archivos_originales)

        assert exc_info.value.status_code == 400
        assert "NO_VALID_FILES" in str(exc_info.value.detail)

    def test_validar_retorna_resultado_exitoso(self):
        """Debe retornar ResultadoValidacionArchivos con archivos válidos"""
        # Arrange
        archivo_pdf = Mock()
        archivo_pdf.filename = "factura.pdf"

        archivo_exe = Mock()
        archivo_exe.filename = "programa.exe"

        archivos = [archivo_pdf, archivo_exe]

        # Act
        resultado = self.validador.validar(archivos)

        # Assert
        assert isinstance(resultado, ResultadoValidacionArchivos)
        assert len(resultado.archivos_validos) == 1
        assert len(resultado.archivos_ignorados) == 1
        assert archivo_pdf in resultado.archivos_validos
        assert "programa.exe" in resultado.archivos_ignorados

    def test_validar_lanza_excepcion_sin_validos(self):
        """Debe lanzar HTTPException si todos los archivos son inválidos"""
        # Arrange
        archivo_exe = Mock()
        archivo_exe.filename = "programa.exe"

        archivos = [archivo_exe]

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            self.validador.validar(archivos)

        assert exc_info.value.status_code == 400

    def test_validar_flujo_completo(self):
        """Debe ejecutar flujo completo de validación correctamente"""
        # Arrange
        archivo_pdf = Mock()
        archivo_pdf.filename = "factura.pdf"

        archivo_jpg = Mock()
        archivo_jpg.filename = "imagen.jpg"

        archivo_xlsx = Mock()
        archivo_xlsx.filename = "datos.xlsx"

        archivo_exe = Mock()
        archivo_exe.filename = "malware.exe"

        archivos = [archivo_pdf, archivo_jpg, archivo_xlsx, archivo_exe]

        # Act
        resultado = self.validador.validar(archivos)

        # Assert
        assert len(resultado.archivos_validos) == 3
        assert len(resultado.archivos_ignorados) == 1
        assert archivo_pdf in resultado.archivos_validos
        assert archivo_jpg in resultado.archivos_validos
        assert archivo_xlsx in resultado.archivos_validos
        assert "malware.exe" in resultado.archivos_ignorados


class TestResultadoValidacionArchivos:
    """Tests para ResultadoValidacionArchivos"""

    def test_puede_desempaquetar_como_tupla(self):
        """Debe ser desempaquetable como tupla"""
        # Arrange
        archivo_mock = Mock()
        resultado = ResultadoValidacionArchivos(
            archivos_validos=[archivo_mock],
            archivos_ignorados=["archivo.exe"]
        )

        # Act
        validos, ignorados = resultado

        # Assert
        assert len(validos) == 1
        assert len(ignorados) == 1
        assert ignorados == ["archivo.exe"]
        assert validos[0].filename == archivo_mock.filename

    def test_acceso_por_atributos(self):
        """Debe permitir acceso por atributos"""
        # Arrange
        archivo_mock = Mock()
        resultado = ResultadoValidacionArchivos(
            archivos_validos=[archivo_mock],
            archivos_ignorados=["archivo.exe"]
        )

        # Act & Assert
        assert resultado.archivos_validos == [archivo_mock]
        assert resultado.archivos_ignorados == ["archivo.exe"]

    def test_resultado_vacio(self):
        """Debe manejar resultado vacío correctamente"""
        # Arrange & Act
        resultado = ResultadoValidacionArchivos(
            archivos_validos=[],
            archivos_ignorados=[]
        )

        # Assert
        assert len(resultado.archivos_validos) == 0
        assert len(resultado.archivos_ignorados) == 0
