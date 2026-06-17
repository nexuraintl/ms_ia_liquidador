"""
TESTS UNITARIOS Y DE INTEGRACION - PREPARACION DE TAREAS DE ANALISIS
======================================================================

Tests completos para el modulo app.preparacion_tareas_analisis.py
Cobertura de:
- Dataclasses
- InstanciadorClasificadores
- PreparadorCacheArchivos
- PreparadorTareasAnalisis
- CoordinadorPreparacionTareas
- Funcion fachada

Autor: Miguel Angel Jaramillo Durango
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

# Importar modulo a testear
from app.preparacion_tareas_analisis import (
    TareaAnalisis,
    ResultadoPreparacionTareas,
    InstanciadorClasificadores,
    PreparadorCacheArchivos,
    PreparadorTareasAnalisis,
    CoordinadorPreparacionTareas,
    preparar_tareas_analisis
)

# Importar dependencias para mocks
from Clasificador import ProcesadorGemini
from Clasificador.clasificador_retefuente import ClasificadorRetefuente
from Clasificador.clasificador_tp import ClasificadorTasaProdeporte
from Clasificador.clasificador_estampillas_g import ClasificadorEstampillasGenerales
from Clasificador.clasificador_iva import ClasificadorIva
from Clasificador.clasificador_obra_uni import ClasificadorObraUni
from database import DatabaseManager
from fastapi import UploadFile


# =================================
# FIXTURES COMUNES
# =================================


@pytest.fixture
def mock_clasificador_gemini():
    """Mock de ProcesadorGemini."""
    mock = Mock(spec=ProcesadorGemini)
    mock.preparar_archivos_para_workers_paralelos = AsyncMock(return_value={})
    mock.analizar_consorcio = Mock()
    mock.db_manager = Mock()
    return mock


@pytest.fixture
def mock_db_manager():
    """Mock de DatabaseManager."""
    return Mock(spec=DatabaseManager)


@pytest.fixture
def documentos_clasificados_mock():
    """Mock de documentos clasificados."""
    return {
        "factura.pdf": {
            "categoria": "FACTURA",
            "texto": "Factura N 123\nValor: $1000000"
        },
        "rut.pdf": {
            "categoria": "RUT",
            "texto": "RUT 900123456"
        }
    }


@pytest.fixture
def archivos_directos_mock():
    """Mock de archivos UploadFile."""
    mock_archivo = Mock(spec=UploadFile)
    mock_archivo.filename = "factura.pdf"
    return [mock_archivo]


# =================================
# TESTS UNITARIOS: DATACLASSES
# =================================


class TestTareaAnalisis:
    """Tests para dataclass TareaAnalisis."""

    def test_tarea_analisis_creacion(self):
        """Verifica creacion correcta de TareaAnalisis."""
        async def mock_coroutine():
            return {"aplica": True}

        tarea = TareaAnalisis(nombre="retefuente", coroutine=mock_coroutine())

        assert tarea.nombre == "retefuente"
        assert tarea.coroutine is not None

    def test_tarea_analisis_atributos(self):
        """Verifica acceso a atributos."""
        async def mock_coroutine():
            return {}

        tarea = TareaAnalisis(nombre="iva_reteiva", coroutine=mock_coroutine())

        assert hasattr(tarea, "nombre")
        assert hasattr(tarea, "coroutine")
        assert isinstance(tarea.nombre, str)


class TestResultadoPreparacionTareas:
    """Tests para dataclass ResultadoPreparacionTareas."""

    def test_resultado_creacion(self):
        """Verifica creacion correcta."""
        async def mock_coroutine():
            return {}

        tareas = [TareaAnalisis(nombre="retefuente", coroutine=mock_coroutine())]
        cache = {"archivo.pdf": Mock()}

        resultado = ResultadoPreparacionTareas(
            tareas_analisis=tareas,
            cache_archivos=cache,
            total_tareas=1,
            impuestos_preparados=["retefuente"]
        )

        assert resultado.total_tareas == 1
        assert len(resultado.tareas_analisis) == 1
        assert len(resultado.impuestos_preparados) == 1

    def test_resultado_desempaquetado(self):
        """Verifica desempaquetado con __iter__."""
        async def mock_coroutine():
            return {}

        tareas = [TareaAnalisis(nombre="retefuente", coroutine=mock_coroutine())]
        cache = {"archivo.pdf": Mock()}

        resultado = ResultadoPreparacionTareas(
            tareas_analisis=tareas,
            cache_archivos=cache,
            total_tareas=1,
            impuestos_preparados=["retefuente"]
        )

        # Desempaquetar
        tareas_out, cache_out = resultado

        assert tareas_out == tareas
        assert cache_out == cache

    def test_resultado_atributos(self):
        """Verifica todos los atributos."""
        async def mock_coroutine():
            return {}

        tareas = [TareaAnalisis(nombre="retefuente", coroutine=mock_coroutine())]
        cache = {}

        resultado = ResultadoPreparacionTareas(
            tareas_analisis=tareas,
            cache_archivos=cache,
            total_tareas=1,
            impuestos_preparados=["retefuente"]
        )

        assert hasattr(resultado, "tareas_analisis")
        assert hasattr(resultado, "cache_archivos")
        assert hasattr(resultado, "total_tareas")
        assert hasattr(resultado, "impuestos_preparados")


# =================================
# TESTS UNITARIOS: INSTANCIADOR DE CLASIFICADORES
# =================================


class TestInstanciadorClasificadores:
    """Tests para InstanciadorClasificadores."""

    @pytest.fixture
    def instanciador(self, mock_clasificador_gemini, mock_db_manager):
        """Fixture con instanciador configurado."""
        return InstanciadorClasificadores(
            clasificador=mock_clasificador_gemini,
            estructura_contable=123,
            db_manager=mock_db_manager
        )

    def test_instanciar_retefuente(self, instanciador):
        """Verifica instanciacion de ClasificadorRetefuente."""
        resultado = instanciador.instanciar_clasificadores(
            aplica_retencion=True,
            aplica_estampilla=False,
            aplica_obra_publica=False,
            aplica_iva=False,
            aplica_tasa_prodeporte=False
        )

        assert "retefuente" in resultado
        assert isinstance(resultado["retefuente"], ClasificadorRetefuente)

    def test_instanciar_multiples(self, instanciador):
        """Verifica instanciacion multiple."""
        resultado = instanciador.instanciar_clasificadores(
            aplica_retencion=True,
            aplica_estampilla=True,
            aplica_obra_publica=True,
            aplica_iva=True,
            aplica_tasa_prodeporte=True
        )

        # retefuente, obra_uni, iva, tp, estampillas_generales
        assert len(resultado) == 5
        assert "retefuente" in resultado
        assert "obra_uni" in resultado
        assert "iva" in resultado
        assert "tasa_prodeporte" in resultado
        assert "estampillas_generales" in resultado

    def test_estampillas_generales_siempre(self, instanciador):
        """Verifica que estampillas generales SIEMPRE se instancia."""
        resultado = instanciador.instanciar_clasificadores(
            aplica_retencion=False,
            aplica_estampilla=False,
            aplica_obra_publica=False,
            aplica_iva=False,
            aplica_tasa_prodeporte=False
        )

        # Solo estampillas_generales debe estar presente
        assert "estampillas_generales" in resultado
        assert len(resultado) == 1

    def test_instanciar_solo_iva(self, instanciador):
        """Verifica instanciacion solo de IVA."""
        resultado = instanciador.instanciar_clasificadores(
            aplica_retencion=False,
            aplica_estampilla=False,
            aplica_obra_publica=False,
            aplica_iva=True,
            aplica_tasa_prodeporte=False
        )

        assert "iva" in resultado
        assert "estampillas_generales" in resultado
        assert len(resultado) == 2

    def test_instanciar_obra_uni_con_estampilla(self, instanciador):
        """Verifica que obra_uni se instancia si estampilla=True."""
        resultado = instanciador.instanciar_clasificadores(
            aplica_retencion=False,
            aplica_estampilla=True,
            aplica_obra_publica=False,
            aplica_iva=False,
            aplica_tasa_prodeporte=False
        )

        assert "obra_uni" in resultado
        assert isinstance(resultado["obra_uni"], ClasificadorObraUni)


# =================================
# TESTS UNITARIOS: PREPARADOR CACHE ARCHIVOS
# =================================


class TestPreparadorCacheArchivos:
    """Tests para PreparadorCacheArchivos."""

    @pytest.fixture
    def preparador_cache(self, mock_clasificador_gemini):
        """Fixture con preparador configurado."""
        return PreparadorCacheArchivos(clasificador=mock_clasificador_gemini)

    @pytest.mark.asyncio
    async def test_preparar_cache_exitoso(self, preparador_cache, archivos_directos_mock):
        """Verifica preparacion exitosa de cache."""
        mock_cache = {"archivo1.pdf": Mock(), "archivo2.pdf": Mock()}

        preparador_cache.clasificador.preparar_archivos_para_workers_paralelos = AsyncMock(
            return_value=mock_cache
        )

        resultado = await preparador_cache.preparar_cache(archivos_directos_mock)

        assert resultado == mock_cache
        preparador_cache.clasificador.preparar_archivos_para_workers_paralelos.assert_called_once_with(
            archivos_directos_mock
        )

    @pytest.mark.asyncio
    async def test_preparar_cache_vacio(self, preparador_cache):
        """Verifica manejo de lista vacia."""
        preparador_cache.clasificador.preparar_archivos_para_workers_paralelos = AsyncMock(
            return_value={}
        )

        resultado = await preparador_cache.preparar_cache([])

        assert isinstance(resultado, dict)
        assert len(resultado) == 0


# =================================
# TESTS UNITARIOS: PREPARADOR TAREAS ANALISIS
# =================================


class TestPreparadorTareasAnalisis:
    """Tests para PreparadorTareasAnalisis."""

    @pytest.fixture
    def clasificadores_mock(self):
        """Mock de clasificadores instanciados."""
        return {
            "retefuente": Mock(spec=ClasificadorRetefuente),
            "iva": Mock(spec=ClasificadorIva),
            "obra_uni": Mock(spec=ClasificadorObraUni),
            "tasa_prodeporte": Mock(spec=ClasificadorTasaProdeporte),
            "estampillas_generales": Mock(spec=ClasificadorEstampillasGenerales)
        }

    @pytest.fixture
    def preparador(self, clasificadores_mock, mock_clasificador_gemini, mock_db_manager):
        """Fixture con preparador configurado."""
        return PreparadorTareasAnalisis(
            clasificadores=clasificadores_mock,
            clasificador_base=mock_clasificador_gemini,
            db_manager=mock_db_manager
        )

    def test_crear_tarea_retefuente_normal(
        self,
        preparador,
        documentos_clasificados_mock
    ):
        """Verifica creacion de tarea retefuente normal."""
        # Mock del coroutine
        preparador.clasificadores["retefuente"].analizar_factura = Mock()

        tarea = preparador._crear_tarea_retefuente(
            documentos_clasificados=documentos_clasificados_mock,
            cache_archivos={},
            aplica_retencion=True,
            es_recurso_extranjero=False,
            es_consorcio=False,
            es_facturacion_extranjera=False,
            proveedor="Test SAS",
            nit_administrativo="900123456"
        )

        assert tarea is not None
        assert tarea.nombre == "retefuente"
        assert isinstance(tarea, TareaAnalisis)

    def test_crear_tarea_retefuente_consorcio(self, preparador):
        """Verifica creacion de tarea retefuente para consorcio."""
        # Mock del coroutine
        preparador.clasificador_base.analizar_consorcio = Mock()

        tarea = preparador._crear_tarea_retefuente(
            documentos_clasificados={},
            cache_archivos={},
            aplica_retencion=True,
            es_recurso_extranjero=False,
            es_consorcio=True,
            es_facturacion_extranjera=False,
            proveedor="CONSORCIO ABC",
            nit_administrativo="900123456"
        )

        assert tarea is not None
        assert tarea.nombre == "retefuente"

    def test_crear_tarea_retefuente_recurso_extranjero(self, preparador):
        """Verifica skip de retefuente para recurso extranjero."""
        tarea = preparador._crear_tarea_retefuente(
            documentos_clasificados={},
            cache_archivos={},
            aplica_retencion=True,
            es_recurso_extranjero=True,  # Recurso extranjero
            es_consorcio=False,
            es_facturacion_extranjera=False,
            proveedor="Test",
            nit_administrativo="900123456"
        )

        assert tarea is None  # No se crea tarea

    def test_crear_tarea_impuestos_especiales(self, preparador):
        """Verifica creacion de tarea impuestos especiales."""
        preparador.clasificadores["obra_uni"].analizar_estampilla = Mock()

        tarea = preparador._crear_tarea_impuestos_especiales(
            documentos_clasificados={},
            cache_archivos={},
            aplica_estampilla=True,
            aplica_obra_publica=False
        )

        assert tarea is not None
        assert tarea.nombre == "impuestos_especiales"

    def test_crear_tarea_iva(self, preparador):
        """Verifica creacion de tarea IVA."""
        preparador.clasificadores["iva"].analizar_iva = Mock()

        tarea = preparador._crear_tarea_iva(
            documentos_clasificados={},
            cache_archivos={},
            aplica_iva=True,
            es_recurso_extranjero=False,
            nit_administrativo="900123456"
        )

        assert tarea is not None
        assert tarea.nombre == "iva_reteiva"

    def test_crear_tarea_estampillas_generales_siempre(self, preparador):
        """Verifica que estampillas generales SIEMPRE se crea."""
        preparador.clasificadores["estampillas_generales"].analizar_estampillas_generales = Mock()

        tarea = preparador._crear_tarea_estampillas_generales(
            documentos_clasificados={},
            cache_archivos={}
        )

        assert tarea is not None
        assert tarea.nombre == "estampillas_generales"

    def test_crear_tarea_tasa_prodeporte(self, preparador):
        """Verifica creacion de tarea Tasa Prodeporte."""
        preparador.clasificadores["tasa_prodeporte"].analizar_tasa_prodeporte = Mock()

        tarea = preparador._crear_tarea_tasa_prodeporte(
            documentos_clasificados={},
            cache_archivos={},
            aplica_tasa_prodeporte=True,
            observaciones_tp="Test",
            nit_administrativo="900649119"
        )

        assert tarea is not None
        assert tarea.nombre == "tasa_prodeporte"

    @pytest.mark.asyncio
    async def test_crear_wrapper_ica_exitoso(self, preparador):
        """Verifica wrapper ICA exitoso."""
        with patch('app.preparacion_tareas_analisis.ClasificadorICA') as MockClasificadorICA:
            mock_clasificador_ica = Mock()
            mock_clasificador_ica.analizar_ica = AsyncMock(return_value={"aplica": True})
            MockClasificadorICA.return_value = mock_clasificador_ica

            resultado = await preparador._crear_wrapper_ica(
                documentos_clasificados={},
                cache_archivos={},
                nit_administrativo="900123456",
                estructura_contable=123
            )

            assert resultado == {"aplica": True}

    @pytest.mark.asyncio
    async def test_crear_wrapper_ica_error(self, preparador):
        """Verifica manejo de error en wrapper ICA."""
        with patch('app.preparacion_tareas_analisis.ClasificadorICA') as MockClasificadorICA:
            mock_clasificador_ica = Mock()
            mock_clasificador_ica.analizar_ica = AsyncMock(side_effect=Exception("Test error"))
            MockClasificadorICA.return_value = mock_clasificador_ica

            resultado = await preparador._crear_wrapper_ica(
                documentos_clasificados={},
                cache_archivos={},
                nit_administrativo="900123456",
                estructura_contable=123
            )

            assert resultado["aplica"] == False
            assert resultado["estado"] == "preliquidacion_sin_finalizar"
            assert "Error en analisis ICA" in resultado["observaciones"][0]

    @pytest.mark.asyncio
    async def test_crear_wrapper_timbre_exitoso(self, preparador):
        """Verifica wrapper Timbre exitoso."""
        with patch('app.preparacion_tareas_analisis.ClasificadorTimbre') as MockClasificadorTimbre:
            mock_clasificador_timbre = Mock()
            mock_clasificador_timbre.analizar_observaciones_timbre = AsyncMock(
                return_value={"aplica_timbre": True}
            )
            MockClasificadorTimbre.return_value = mock_clasificador_timbre

            resultado = await preparador._crear_wrapper_timbre(observaciones_tp="Test")

            assert resultado == {"aplica_timbre": True}

    @pytest.mark.asyncio
    async def test_crear_wrapper_timbre_error(self, preparador):
        """Verifica manejo de error en wrapper Timbre."""
        with patch('app.preparacion_tareas_analisis.ClasificadorTimbre') as MockClasificadorTimbre:
            mock_clasificador_timbre = Mock()
            mock_clasificador_timbre.analizar_observaciones_timbre = AsyncMock(
                side_effect=Exception("Test error")
            )
            MockClasificadorTimbre.return_value = mock_clasificador_timbre

            resultado = await preparador._crear_wrapper_timbre(observaciones_tp="Test")

            assert resultado["aplica_timbre"] == False
            assert resultado["base_gravable_obs"] == 0.0


# =================================
# TESTS DE INTEGRACION: COORDINADOR
# =================================


class TestCoordinadorPreparacionTareas:
    """Tests de integracion para CoordinadorPreparacionTareas."""

    @pytest.fixture
    def coordinador(self, mock_clasificador_gemini, mock_db_manager):
        """Fixture con coordinador configurado."""
        return CoordinadorPreparacionTareas(
            clasificador=mock_clasificador_gemini,
            estructura_contable=123,
            db_manager=mock_db_manager
        )

    @pytest.mark.asyncio
    async def test_preparar_tareas_flujo_completo(
        self,
        coordinador,
        documentos_clasificados_mock,
        archivos_directos_mock
    ):
        """Verifica flujo completo de preparacion de tareas."""
        # Configurar mocks
        mock_cache = {"archivo1.pdf": Mock()}
        coordinador.preparador_cache.preparar_cache = AsyncMock(return_value=mock_cache)

        # Mock de preparar_tareas
        with patch.object(PreparadorTareasAnalisis, 'preparar_tareas', new_callable=AsyncMock) as mock_preparar:
            async def mock_coroutine():
                return {}

            mock_tareas = [TareaAnalisis(nombre="retefuente", coroutine=mock_coroutine())]
            mock_preparar.return_value = mock_tareas

            resultado = await coordinador.preparar_tareas_analisis(
                documentos_clasificados=documentos_clasificados_mock,
                archivos_directos=archivos_directos_mock,
                aplica_retencion=True,
                aplica_estampilla=False,
                aplica_obra_publica=False,
                aplica_iva=False,
                aplica_ica=False,
                aplica_timbre=False,
                aplica_tasa_prodeporte=False,
                es_consorcio=False,
                es_recurso_extranjero=False,
                es_facturacion_extranjera=False,
                proveedor="Test",
                nit_administrativo="900123456",
                observaciones_tp="",
                impuestos_a_procesar=["retefuente"]
            )

            # Verificaciones
            assert isinstance(resultado, ResultadoPreparacionTareas)
            assert resultado.cache_archivos == mock_cache
            assert resultado.total_tareas > 0

    @pytest.mark.asyncio
    async def test_preparar_tareas_desempaquetado(self, coordinador):
        """Verifica desempaquetado de resultado."""
        mock_cache = {}
        coordinador.preparador_cache.preparar_cache = AsyncMock(return_value=mock_cache)

        with patch.object(PreparadorTareasAnalisis, 'preparar_tareas', new_callable=AsyncMock) as mock_preparar:
            mock_preparar.return_value = []

            resultado = await coordinador.preparar_tareas_analisis(
                documentos_clasificados={},
                archivos_directos=[],
                aplica_retencion=False,
                aplica_estampilla=False,
                aplica_obra_publica=False,
                aplica_iva=False,
                aplica_ica=False,
                aplica_timbre=False,
                aplica_tasa_prodeporte=False,
                es_consorcio=False,
                es_recurso_extranjero=False,
                es_facturacion_extranjera=False,
                proveedor="Test",
                nit_administrativo="900123456",
                observaciones_tp="",
                impuestos_a_procesar=[]
            )

            # Desempaquetar
            tareas, cache = resultado

            assert isinstance(tareas, list)
            assert isinstance(cache, dict)


# =================================
# TESTS DE LA FUNCION FACHADA
# =================================


class TestFuncionFachada:
    """Tests para funcion fachada preparar_tareas_analisis."""

    @pytest.mark.asyncio
    async def test_funcion_fachada(self, mock_clasificador_gemini, mock_db_manager):
        """Verifica funcionamiento de funcion fachada."""
        with patch('app.preparacion_tareas_analisis.CoordinadorPreparacionTareas') as MockCoordinador:
            mock_coordinador_instance = MockCoordinador.return_value

            async def mock_coroutine():
                return {}

            mock_resultado = ResultadoPreparacionTareas(
                tareas_analisis=[],
                cache_archivos={},
                total_tareas=0,
                impuestos_preparados=[]
            )
            mock_coordinador_instance.preparar_tareas_analisis = AsyncMock(
                return_value=mock_resultado
            )

            resultado = await preparar_tareas_analisis(
                clasificador=mock_clasificador_gemini,
                estructura_contable=123,
                db_manager=mock_db_manager,
                documentos_clasificados={},
                archivos_directos=[],
                aplica_retencion=True,
                aplica_estampilla=False,
                aplica_obra_publica=False,
                aplica_iva=False,
                aplica_ica=False,
                aplica_timbre=False,
                aplica_tasa_prodeporte=False,
                es_consorcio=False,
                es_recurso_extranjero=False,
                es_facturacion_extranjera=False,
                proveedor="Test",
                nit_administrativo="900123456",
                observaciones_tp="",
                impuestos_a_procesar=["retefuente"]
            )

            assert resultado == mock_resultado
            MockCoordinador.assert_called_once()


# =================================
# COMANDO PARA EJECUTAR TESTS
# =================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.preparacion_tareas_analisis", "--cov-report=html"])
