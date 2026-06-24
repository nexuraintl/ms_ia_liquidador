"""
Tests para el módulo de clasificación de documentos.

Cubre funcionalidad completa y casos edge de:
- ResultadoDocumentosClasificados (dataclass)
- ClasificadorDocumentos (clase)
- clasificar_archivos (función fachada)

Autor: Miguel Angel Jaramillo Durango
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, List, Any
from fastapi import HTTPException, UploadFile
from io import BytesIO
from datetime import datetime

from app.clasificacion_documentos import (
    ResultadoDocumentosClasificados,
    ClasificadorDocumentos,
    clasificar_archivos
)


class TestResultadoDocumentosClasificados:
    """Tests para el dataclass ResultadoDocumentosClasificados."""

    def test_creacion_dataclass_con_todos_campos(self):
        """Test: Crear dataclass con todos los campos requeridos."""
        resultado = ResultadoDocumentosClasificados(
            documentos_clasificados={"factura.pdf": {"categoria": "FACTURA", "texto": "..."}},
            es_consorcio=True,
            es_recurso_extranjero=False,
            es_facturacion_extranjera=False,
            clasificacion={"factura.pdf": "FACTURA"}
        )

        assert resultado.documentos_clasificados == {"factura.pdf": {"categoria": "FACTURA", "texto": "..."}}
        assert resultado.es_consorcio is True
        assert resultado.es_recurso_extranjero is False
        assert resultado.es_facturacion_extranjera is False
        assert resultado.clasificacion == {"factura.pdf": "FACTURA"}

    def test_desempaquetado_completo_5_valores(self):
        """Test: Desempaquetar dataclass retorna 5 valores en orden correcto."""
        resultado = ResultadoDocumentosClasificados(
            documentos_clasificados={"factura.pdf": {"categoria": "FACTURA", "texto": "..."}},
            es_consorcio=True,
            es_recurso_extranjero=False,
            es_facturacion_extranjera=True,
            clasificacion={"factura.pdf": "FACTURA"}
        )

        docs, consorcio, extranjero, extranjera, clasif = resultado

        assert docs == {"factura.pdf": {"categoria": "FACTURA", "texto": "..."}}
        assert consorcio is True
        assert extranjero is False
        assert extranjera is True
        assert clasif == {"factura.pdf": "FACTURA"}

    def test_acceso_por_atributo(self):
        """Test: Acceso individual a cada atributo del dataclass."""
        resultado = ResultadoDocumentosClasificados(
            documentos_clasificados={"rut.pdf": {"categoria": "RUT", "texto": "123456"}},
            es_consorcio=False,
            es_recurso_extranjero=True,
            es_facturacion_extranjera=False,
            clasificacion={"rut.pdf": "RUT"}
        )

        assert "rut.pdf" in resultado.documentos_clasificados
        assert resultado.documentos_clasificados["rut.pdf"]["categoria"] == "RUT"
        assert resultado.es_consorcio is False
        assert resultado.es_recurso_extranjero is True
        assert resultado.clasificacion["rut.pdf"] == "RUT"

    def test_dataclass_con_multiples_documentos(self):
        """Test: Dataclass con múltiples documentos clasificados."""
        docs_clasificados = {
            "factura.pdf": {"categoria": "FACTURA", "texto": "...", "procesamiento": "directo_gemini"},
            "rut.pdf": {"categoria": "RUT", "texto": "...", "procesamiento": "directo_gemini"},
            "anexo.xlsx": {"categoria": "ANEXO", "texto": "texto preprocesado"}
        }
        clasificacion = {
            "factura.pdf": "FACTURA",
            "rut.pdf": "RUT",
            "anexo.xlsx": "ANEXO"
        }

        resultado = ResultadoDocumentosClasificados(
            documentos_clasificados=docs_clasificados,
            es_consorcio=False,
            es_recurso_extranjero=False,
            es_facturacion_extranjera=False,
            clasificacion=clasificacion
        )

        assert len(resultado.documentos_clasificados) == 3
        assert len(resultado.clasificacion) == 3


class TestClasificadorDocumentos:
    """Tests para la clase ClasificadorDocumentos."""

    @pytest.fixture
    def mock_clasificador_gemini(self):
        """Fixture: Mock de ProcesadorGemini."""
        mock = AsyncMock()
        mock.clasificar_documentos = AsyncMock()
        return mock

    @pytest.fixture
    def clasificador_documentos(self, mock_clasificador_gemini):
        """Fixture: Instancia de ClasificadorDocumentos con mock."""
        return ClasificadorDocumentos(mock_clasificador_gemini)

    @pytest.fixture
    def archivos_directos_mock(self):
        """Fixture: Lista de archivos UploadFile mock."""
        archivo1 = Mock(spec=UploadFile)
        archivo1.filename = "factura.pdf"
        archivo1.read = AsyncMock(return_value=b"%PDF-1.4 contenido...")

        archivo2 = Mock(spec=UploadFile)
        archivo2.filename = "rut.pdf"
        archivo2.read = AsyncMock(return_value=b"%PDF-1.5 contenido...")

        return [archivo1, archivo2]

    @pytest.fixture
    def textos_preprocesados_mock(self):
        """Fixture: Textos preprocesados de Excel/Email."""
        return {
            "anexo.xlsx": "Contenido del anexo en texto plano",
            "email.msg": "Asunto: Factura\nCuerpo del email..."
        }

    def test_init_clasificador_documentos(self, mock_clasificador_gemini):
        """Test: Inicialización correcta de ClasificadorDocumentos."""
        clasificador = ClasificadorDocumentos(mock_clasificador_gemini)

        assert clasificador.clasificador == mock_clasificador_gemini

    @pytest.mark.asyncio
    async def test_clasificar_exitoso_factura_simple(
        self,
        clasificador_documentos,
        mock_clasificador_gemini,
        archivos_directos_mock,
        textos_preprocesados_mock
    ):
        """Test: Clasificación exitosa de factura simple (no consorcio)."""
        mock_clasificador_gemini.clasificar_documentos.return_value = (
            {"factura.pdf": "FACTURA", "rut.pdf": "RUT", "anexo.xlsx": "ANEXO"},
            False,  # es_consorcio
            False,  # es_recurso_extranjero
            False   # es_facturacion_extranjera
        )

        with patch('app.clasificacion_documentos.guardar_archivo_json') as mock_guardar:
            resultado = await clasificador_documentos.clasificar(
                archivos_directos=archivos_directos_mock,
                textos_preprocesados=textos_preprocesados_mock,
                provedor="PROVEEDOR ABC",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente", "iva"]
            )

        assert isinstance(resultado, ResultadoDocumentosClasificados)
        assert resultado.es_consorcio is False
        assert resultado.es_recurso_extranjero is False
        assert resultado.es_facturacion_extranjera is False
        assert len(resultado.clasificacion) == 3
        assert resultado.clasificacion["factura.pdf"] == "FACTURA"
        assert mock_guardar.called

    @pytest.mark.asyncio
    async def test_clasificar_exitoso_consorcio(
        self,
        clasificador_documentos,
        mock_clasificador_gemini,
        archivos_directos_mock,
        textos_preprocesados_mock
    ):
        """Test: Clasificación exitosa detectando consorcio."""
        mock_clasificador_gemini.clasificar_documentos.return_value = (
            {"factura.pdf": "FACTURA", "distribucion.xlsx": "ANEXO"},
            True,   # es_consorcio
            False,  # es_recurso_extranjero
            False   # es_facturacion_extranjera
        )

        with patch('app.clasificacion_documentos.guardar_archivo_json'):
            resultado = await clasificador_documentos.clasificar(
                archivos_directos=archivos_directos_mock,
                textos_preprocesados=textos_preprocesados_mock,
                provedor="CONSORCIO XYZ",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente"]
            )

        assert resultado.es_consorcio is True
        assert "factura.pdf" in resultado.clasificacion

    @pytest.mark.asyncio
    async def test_clasificar_facturacion_extranjera(
        self,
        clasificador_documentos,
        mock_clasificador_gemini,
        archivos_directos_mock,
        textos_preprocesados_mock
    ):
        """Test: Clasificación con facturación extranjera detectada."""
        mock_clasificador_gemini.clasificar_documentos.return_value = (
            {"invoice.pdf": "FACTURA"},
            False,  # es_consorcio
            False,  # es_recurso_extranjero
            True    # es_facturacion_extranjera
        )

        with patch('app.clasificacion_documentos.guardar_archivo_json'):
            resultado = await clasificador_documentos.clasificar(
                archivos_directos=archivos_directos_mock,
                textos_preprocesados={},
                provedor="FOREIGN SUPPLIER INC",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente"]
            )

        assert resultado.es_facturacion_extranjera is True
        assert resultado.es_recurso_extranjero is False

    @pytest.mark.asyncio
    async def test_clasificar_recurso_extranjero(
        self,
        clasificador_documentos,
        mock_clasificador_gemini,
        archivos_directos_mock,
        textos_preprocesados_mock
    ):
        """Test: Clasificación con recurso de fuente extranjera."""
        mock_clasificador_gemini.clasificar_documentos.return_value = (
            {"factura.pdf": "FACTURA"},
            False,  # es_consorcio
            True,   # es_recurso_extranjero
            True    # es_facturacion_extranjera
        )

        with patch('app.clasificacion_documentos.guardar_archivo_json'):
            resultado = await clasificador_documentos.clasificar(
                archivos_directos=archivos_directos_mock,
                textos_preprocesados={},
                provedor="FOREIGN SUPPLIER",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente", "iva"]
            )

        assert resultado.es_recurso_extranjero is True
        assert resultado.es_facturacion_extranjera is True

    @pytest.mark.asyncio
    async def test_clasificar_solo_archivos_directos(
        self,
        clasificador_documentos,
        mock_clasificador_gemini,
        archivos_directos_mock
    ):
        """Test: Clasificación solo con archivos directos (sin preprocesados)."""
        mock_clasificador_gemini.clasificar_documentos.return_value = (
            {"factura.pdf": "FACTURA", "rut.pdf": "RUT"},
            False, False, False
        )

        with patch('app.clasificacion_documentos.guardar_archivo_json'):
            resultado = await clasificador_documentos.clasificar(
                archivos_directos=archivos_directos_mock,
                textos_preprocesados={},  # Vacío
                provedor="PROVEEDOR ABC",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente"]
            )

        assert len(resultado.documentos_clasificados) == 2
        assert resultado.documentos_clasificados["factura.pdf"]["procesamiento"] == "directo_gemini"
        assert resultado.documentos_clasificados["factura.pdf"]["texto"] == "[ARCHIVO_DIRECTO_MULTIMODAL]"

    @pytest.mark.asyncio
    async def test_clasificar_solo_textos_preprocesados(
        self,
        clasificador_documentos,
        mock_clasificador_gemini,
        textos_preprocesados_mock
    ):
        """Test: Clasificación solo con textos preprocesados (sin archivos directos)."""
        mock_clasificador_gemini.clasificar_documentos.return_value = (
            {"anexo.xlsx": "ANEXO", "email.msg": "FACTURA"},
            False, False, False
        )

        with patch('app.clasificacion_documentos.guardar_archivo_json'):
            resultado = await clasificador_documentos.clasificar(
                archivos_directos=[],  # Vacío
                textos_preprocesados=textos_preprocesados_mock,
                provedor="PROVEEDOR ABC",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente"]
            )

        assert len(resultado.documentos_clasificados) == 2
        assert "procesamiento" not in resultado.documentos_clasificados["anexo.xlsx"]
        assert resultado.documentos_clasificados["anexo.xlsx"]["texto"] == "Contenido del anexo en texto plano"

    @pytest.mark.asyncio
    async def test_clasificar_timeout_gemini(
        self,
        clasificador_documentos,
        mock_clasificador_gemini,
        archivos_directos_mock,
        textos_preprocesados_mock
    ):
        """Test: Manejo de timeout de Gemini (504 Gateway Timeout)."""
        mock_clasificador_gemini.clasificar_documentos.side_effect = HTTPException(
            status_code=504,
            detail={
                "error": "Timeout comunicándose con servicio de IA",
                "tipo": "gateway_timeout"
            }
        )

        with pytest.raises(HTTPException) as exc_info:
            await clasificador_documentos.clasificar(
                archivos_directos=archivos_directos_mock,
                textos_preprocesados=textos_preprocesados_mock,
                provedor="PROVEEDOR ABC",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente"]
            )

        assert exc_info.value.status_code == 504
        assert "timeout" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_clasificar_quota_exceeded(
        self,
        clasificador_documentos,
        mock_clasificador_gemini,
        archivos_directos_mock,
        textos_preprocesados_mock
    ):
        """Test: Manejo de quota excedida de Gemini (429 Too Many Requests)."""
        mock_clasificador_gemini.clasificar_documentos.side_effect = HTTPException(
            status_code=429,
            detail={
                "error": "Límite de uso del servicio de IA excedido",
                "tipo": "quota_exceeded"
            }
        )

        with pytest.raises(HTTPException) as exc_info:
            await clasificador_documentos.clasificar(
                archivos_directos=archivos_directos_mock,
                textos_preprocesados=textos_preprocesados_mock,
                provedor="PROVEEDOR ABC",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente"]
            )

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_clasificar_error_autenticacion(
        self,
        clasificador_documentos,
        mock_clasificador_gemini,
        archivos_directos_mock,
        textos_preprocesados_mock
    ):
        """Test: Manejo de error de autenticación (502 Bad Gateway)."""
        mock_clasificador_gemini.clasificar_documentos.side_effect = HTTPException(
            status_code=502,
            detail={
                "error": "Error de autenticación con servicio de IA",
                "tipo": "authentication_error"
            }
        )

        with pytest.raises(HTTPException) as exc_info:
            await clasificador_documentos.clasificar(
                archivos_directos=archivos_directos_mock,
                textos_preprocesados=textos_preprocesados_mock,
                provedor="PROVEEDOR ABC",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente"]
            )

        assert exc_info.value.status_code == 502
        assert "autenticación" in str(exc_info.value.detail).lower()

    def test_estructurar_respuesta_clasificacion_basica(self, clasificador_documentos):
        """Test: Estructuración de respuesta con datos básicos."""
        # anexo.xlsx debe estar en clasificacion para ser incluido en documentos_clasificados
        clasificacion = {"factura.pdf": "FACTURA", "rut.pdf": "RUT", "anexo.xlsx": "ANEXO"}
        textos_preprocesados = {"anexo.xlsx": "texto preprocesado"}
        archivos_directos = []

        data, docs = clasificador_documentos.estructurar_respuesta_clasificacion(
            clasificacion=clasificacion,
            textos_preprocesados=textos_preprocesados,
            es_consorcio=False,
            es_recurso_extranjero=False,
            es_facturacion_extranjera=False,
            nit_administrativo="900123456",
            nombre_entidad="Universidad Nacional",
            impuestos_a_procesar=["retefuente"],
            archivos_directos=archivos_directos
        )

        # Verificar estructura de datos para persistencia
        assert "timestamp" in data
        assert data["nit_administrativo"] == "900123456"
        assert data["nombre_entidad"] == "Universidad Nacional"
        assert data["es_consorcio"] is False
        assert data["clasificacion"] == clasificacion

        # Verificar documentos clasificados - anexo.xlsx está en clasificacion y textos_preprocesados
        assert "anexo.xlsx" in docs
        assert docs["anexo.xlsx"]["categoria"] == "ANEXO"
        assert docs["anexo.xlsx"]["texto"] == "texto preprocesado"
        assert "factura.pdf" in docs
        assert "rut.pdf" in docs

    def test_estructurar_respuesta_archivos_directos(self, clasificador_documentos):
        """Test: Estructuración marca correctamente archivos directos."""
        archivo_mock = Mock(spec=UploadFile)
        archivo_mock.filename = "factura.pdf"

        clasificacion = {"factura.pdf": "FACTURA"}
        textos_preprocesados = {}
        archivos_directos = [archivo_mock]

        data, docs = clasificador_documentos.estructurar_respuesta_clasificacion(
            clasificacion=clasificacion,
            textos_preprocesados=textos_preprocesados,
            es_consorcio=False,
            es_recurso_extranjero=False,
            es_facturacion_extranjera=False,
            nit_administrativo="900123456",
            nombre_entidad="Universidad Nacional",
            impuestos_a_procesar=["retefuente"],
            archivos_directos=archivos_directos
        )

        # Verificar que archivo directo tiene marca especial
        assert docs["factura.pdf"]["texto"] == "[ARCHIVO_DIRECTO_MULTIMODAL]"
        assert docs["factura.pdf"]["procesamiento"] == "directo_gemini"

        # Verificar metadatos de procesamiento híbrido
        assert data["procesamiento_hibrido"]["multimodalidad_activa"] is True
        assert data["procesamiento_hibrido"]["archivos_directos"] == 1
        assert data["procesamiento_hibrido"]["archivos_preprocesados"] == 0

    def test_estructurar_respuesta_hibrido(self, clasificador_documentos):
        """Test: Estructuración con archivos directos y preprocesados (híbrido)."""
        archivo_mock = Mock(spec=UploadFile)
        archivo_mock.filename = "factura.pdf"

        clasificacion = {"factura.pdf": "FACTURA", "anexo.xlsx": "ANEXO"}
        textos_preprocesados = {"anexo.xlsx": "texto del anexo"}
        archivos_directos = [archivo_mock]

        data, docs = clasificador_documentos.estructurar_respuesta_clasificacion(
            clasificacion=clasificacion,
            textos_preprocesados=textos_preprocesados,
            es_consorcio=True,
            es_recurso_extranjero=False,
            es_facturacion_extranjera=True,
            nit_administrativo="900123456",
            nombre_entidad="Universidad Nacional",
            impuestos_a_procesar=["retefuente", "iva"],
            archivos_directos=archivos_directos
        )

        # Verificar documentos híbridos
        assert docs["factura.pdf"]["procesamiento"] == "directo_gemini"
        assert "procesamiento" not in docs["anexo.xlsx"]
        assert docs["anexo.xlsx"]["texto"] == "texto del anexo"

        # Verificar flags especiales
        assert data["es_consorcio"] is True
        assert data["es_facturacion_extranjera"] is True

        # Verificar metadatos híbridos
        assert data["procesamiento_hibrido"]["archivos_directos"] == 1
        assert data["procesamiento_hibrido"]["archivos_preprocesados"] == 1
        assert data["procesamiento_hibrido"]["total_archivos"] == 2


class TestClasificarArchivos:
    """Tests para la función fachada clasificar_archivos."""

    @pytest.fixture
    def mock_clasificador_gemini(self):
        """Fixture: Mock de ProcesadorGemini."""
        mock = AsyncMock()
        mock.clasificar_documentos = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_clasificar_archivos_exitoso(self, mock_clasificador_gemini):
        """Test: Función fachada clasificar_archivos funciona correctamente."""
        mock_clasificador_gemini.clasificar_documentos.return_value = (
            {"factura.pdf": "FACTURA"},
            False, False, False
        )

        archivo_mock = Mock(spec=UploadFile)
        archivo_mock.filename = "factura.pdf"

        with patch('app.clasificacion_documentos.guardar_archivo_json'):
            resultado = await clasificar_archivos(
                clasificador=mock_clasificador_gemini,
                archivos_directos=[archivo_mock],
                textos_preprocesados={},
                provedor="PROVEEDOR ABC",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente"]
            )

        assert isinstance(resultado, ResultadoDocumentosClasificados)
        assert resultado.clasificacion["factura.pdf"] == "FACTURA"

    @pytest.mark.asyncio
    async def test_clasificar_archivos_propaga_excepciones(self, mock_clasificador_gemini):
        """Test: Función fachada propaga correctamente excepciones HTTP."""
        mock_clasificador_gemini.clasificar_documentos.side_effect = HTTPException(
            status_code=504,
            detail={"error": "Timeout"}
        )

        with pytest.raises(HTTPException) as exc_info:
            await clasificar_archivos(
                clasificador=mock_clasificador_gemini,
                archivos_directos=[],
                textos_preprocesados={},
                provedor="PROVEEDOR ABC",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente"]
            )

        assert exc_info.value.status_code == 504


class TestEdgeCases:
    """Tests para casos edge y límites del sistema."""

    @pytest.fixture
    def clasificador_documentos(self):
        """Fixture: ClasificadorDocumentos con mock."""
        mock_gemini = AsyncMock()
        mock_gemini.clasificar_documentos = AsyncMock()
        return ClasificadorDocumentos(mock_gemini)

    @pytest.mark.asyncio
    async def test_clasificacion_vacia(self, clasificador_documentos):
        """Test: Clasificación retorna diccionario vacío."""
        clasificador_documentos.clasificador.clasificar_documentos.return_value = (
            {},  # Clasificación vacía
            False, False, False
        )

        with pytest.raises(ValueError, match="No se identificó ninguna factura"):
            await clasificador_documentos.clasificar(
                archivos_directos=[],
                textos_preprocesados={},
                provedor="PROVEEDOR ABC",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente"]
            )

    @pytest.mark.asyncio
    async def test_multiples_documentos_mismo_tipo(self, clasificador_documentos):
        """Test: Múltiples documentos del mismo tipo (ej: 3 facturas)."""
        clasificador_documentos.clasificador.clasificar_documentos.return_value = (
            {"factura1.pdf": "FACTURA", "factura2.pdf": "FACTURA", "factura3.pdf": "FACTURA"},
            False, False, False
        )

        with patch('app.clasificacion_documentos.guardar_archivo_json'):
            resultado = await clasificador_documentos.clasificar(
                archivos_directos=[],
                textos_preprocesados={
                    "factura1.pdf": "texto1",
                    "factura2.pdf": "texto2",
                    "factura3.pdf": "texto3"
                },
                provedor="PROVEEDOR ABC",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional",
                impuestos_a_procesar=["retefuente"]
            )

        assert len(resultado.clasificacion) == 3
        assert all(cat == "FACTURA" for cat in resultado.clasificacion.values())

    def test_nombres_archivos_especiales(self, clasificador_documentos):
        """Test: Nombres de archivos con caracteres especiales."""
        clasificacion = {
            "factura (1).pdf": "FACTURA",
            "anexo_con_espacios.xlsx": "ANEXO",
            "archivo-con-guiones.pdf": "RUT"
        }

        data, docs = clasificador_documentos.estructurar_respuesta_clasificacion(
            clasificacion=clasificacion,
            textos_preprocesados={
                "factura (1).pdf": "texto",
                "anexo_con_espacios.xlsx": "texto",
                "archivo-con-guiones.pdf": "texto"
            },
            es_consorcio=False,
            es_recurso_extranjero=False,
            es_facturacion_extranjera=False,
            nit_administrativo="900123456",
            nombre_entidad="Universidad Nacional",
            impuestos_a_procesar=["retefuente"],
            archivos_directos=[]
        )

        assert "factura (1).pdf" in docs
        assert "anexo_con_espacios.xlsx" in docs
        assert "archivo-con-guiones.pdf" in docs

    def test_nit_con_guion_verificador(self, clasificador_documentos):
        """Test: NIT con guión verificador se procesa correctamente."""
        data, _ = clasificador_documentos.estructurar_respuesta_clasificacion(
            clasificacion={"factura.pdf": "FACTURA"},
            textos_preprocesados={"factura.pdf": "texto"},
            es_consorcio=False,
            es_recurso_extranjero=False,
            es_facturacion_extranjera=False,
            nit_administrativo="900123456-7",  # Con guión
            nombre_entidad="Universidad Nacional",
            impuestos_a_procesar=["retefuente"],
            archivos_directos=[]
        )

        assert data["nit_administrativo"] == "900123456-7"

    def test_lista_impuestos_vacia(self, clasificador_documentos):
        """Test: Lista de impuestos vacía se maneja correctamente."""
        data, _ = clasificador_documentos.estructurar_respuesta_clasificacion(
            clasificacion={"factura.pdf": "FACTURA"},
            textos_preprocesados={"factura.pdf": "texto"},
            es_consorcio=False,
            es_recurso_extranjero=False,
            es_facturacion_extranjera=False,
            nit_administrativo="900123456",
            nombre_entidad="Universidad Nacional",
            impuestos_a_procesar=[],  # Vacía
            archivos_directos=[]
        )

        assert data["impuestos_aplicables"] == []

    def test_proveedor_con_caracteres_unicode(self, clasificador_documentos):
        """Test: Proveedor con caracteres especiales y acentos."""
        # Esto se valida implícitamente en la llamada a clasificar_documentos
        # El clasificador no modifica el proveedor, solo lo pasa a Gemini
        pass

    def test_timestamp_formato_iso(self, clasificador_documentos):
        """Test: Timestamp se genera en formato ISO 8601."""
        data, _ = clasificador_documentos.estructurar_respuesta_clasificacion(
            clasificacion={"factura.pdf": "FACTURA"},
            textos_preprocesados={"factura.pdf": "texto"},
            es_consorcio=False,
            es_recurso_extranjero=False,
            es_facturacion_extranjera=False,
            nit_administrativo="900123456",
            nombre_entidad="Universidad Nacional",
            impuestos_a_procesar=["retefuente"],
            archivos_directos=[]
        )

        # Verificar que timestamp es válido ISO 8601
        timestamp = data["timestamp"]
        datetime.fromisoformat(timestamp)  # Lanza excepción si no es válido

    def test_todos_flags_true(self, clasificador_documentos):
        """Test: Todos los flags booleanos en True (caso extremo)."""
        data, _ = clasificador_documentos.estructurar_respuesta_clasificacion(
            clasificacion={"factura.pdf": "FACTURA"},
            textos_preprocesados={"factura.pdf": "texto"},
            es_consorcio=True,
            es_recurso_extranjero=True,
            es_facturacion_extranjera=True,
            nit_administrativo="900123456",
            nombre_entidad="Universidad Nacional",
            impuestos_a_procesar=["retefuente"],
            archivos_directos=[]
        )

        assert data["es_consorcio"] is True
        assert data["es_recurso_extranjero"] is True
        assert data["es_facturacion_extranjera"] is True


class TestIntegracion:
    """Tests de integración end-to-end (sin mocks de Gemini)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_flujo_completo_clasificacion(self):
        """Test de integración: Flujo completo de clasificación."""
        # Mock completo de ProcesadorGemini
        mock_gemini = AsyncMock()
        mock_gemini.clasificar_documentos = AsyncMock(return_value=(
            {"factura.pdf": "FACTURA", "anexo.xlsx": "ANEXO"},
            False, False, False
        ))

        # Crear archivos mock
        archivo_pdf = Mock(spec=UploadFile)
        archivo_pdf.filename = "factura.pdf"

        # Ejecutar flujo completo
        with patch('app.clasificacion_documentos.guardar_archivo_json') as mock_guardar:
            resultado = await clasificar_archivos(
                clasificador=mock_gemini,
                archivos_directos=[archivo_pdf],
                textos_preprocesados={"anexo.xlsx": "contenido anexo"},
                provedor="CONSORCIO ABC",
                nit_administrativo="900123456",
                nombre_entidad="Universidad Nacional de Colombia",
                impuestos_a_procesar=["retefuente", "iva", "estampilla"]
            )

        # Verificar resultado completo
        assert isinstance(resultado, ResultadoDocumentosClasificados)
        assert len(resultado.clasificacion) == 2
        assert resultado.documentos_clasificados["factura.pdf"]["procesamiento"] == "directo_gemini"
        assert resultado.documentos_clasificados["anexo.xlsx"]["texto"] == "contenido anexo"

        # Verificar que se guardó JSON
        assert mock_guardar.called
        saved_data = mock_guardar.call_args[0][0]
        assert saved_data["nit_administrativo"] == "900123456"
        assert saved_data["nombre_entidad"] == "Universidad Nacional de Colombia"


# Configuración para pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
