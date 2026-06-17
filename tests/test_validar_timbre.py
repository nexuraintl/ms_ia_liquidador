"""
Tests para el modulo validar_timbre.py

Tests implementados:
- Validacion de Timbre con doble analisis de Gemini
- Validacion cuando no aplica segun observaciones
- Validacion cuando no hay analisis de Timbre
- Validacion del metodo _debe_procesar_timbre
- Validacion del metodo _verifica_aplicabilidad_observaciones
- Validacion del metodo _extraer_datos_contrato
- Validacion del metodo _ejecutar_liquidacion
- Manejo de errores en liquidacion
- Lazy initialization del liquidador
- Logging de resultados

Autor: Sistema Preliquidador
Version: 1.0
"""

import pytest
import logging
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from app.validar_timbre import ValidadorTimbre, validar_timbre


class TestValidadorTimbre:
    """Tests para la clase ValidadorTimbre"""

    @pytest.fixture
    def mock_db_manager(self):
        """Fixture para mock de database manager"""
        return Mock()

    @pytest.fixture
    def mock_clasificador_gemini(self):
        """Fixture para mock de clasificador Gemini"""
        return Mock()

    @pytest.fixture
    def mock_liquidador(self):
        """Fixture para mock de liquidador timbre"""
        mock = Mock()
        mock_resultado = Mock()
        mock_resultado.aplica = True
        mock_resultado.estado = "liquidado"
        mock_resultado.valor = 250000.0
        mock_resultado.tarifa = 0.01
        mock_resultado.tipo_cuantia = "menor_cuantia"
        mock_resultado.base_gravable = 25000000.0
        mock_resultado.ID_contrato = "CT-2024-001"
        mock_resultado.dict = Mock(return_value={
            "aplica": True,
            "estado": "liquidado",
            "valor": 250000.0,
            "tarifa": 0.01,
            "tipo_cuantia": "menor_cuantia",
            "base_gravable": 25000000.0,
            "ID_contrato": "CT-2024-001",
            "observaciones": "Liquidacion exitosa"
        })
        mock.liquidar_timbre = Mock(return_value=mock_resultado)
        return mock

    @pytest.fixture
    def validador(self, mock_db_manager, mock_clasificador_gemini):
        """Fixture para crear instancia de ValidadorTimbre"""
        return ValidadorTimbre(
            db_manager=mock_db_manager,
            clasificador_gemini=mock_clasificador_gemini
        )

    @pytest.fixture
    def resultados_analisis_con_timbre_aplica(self):
        """Fixture para resultados con Timbre que aplica"""
        return {
            "timbre": {
                "aplica_timbre": True,
                "observaciones_pgd": "Contrato de obra publica"
            }
        }

    @pytest.fixture
    def resultados_analisis_con_timbre_no_aplica(self):
        """Fixture para resultados con Timbre que no aplica"""
        return {
            "timbre": {
                "aplica_timbre": False,
                "observaciones_pgd": "No aplica timbre"
            }
        }

    @pytest.fixture
    def resultados_analisis_sin_timbre(self):
        """Fixture para resultados sin Timbre"""
        return {
            "retefuente": {
                "conceptos": ["Servicios generales"]
            }
        }

    @pytest.fixture
    def datos_contrato_mock(self):
        """Fixture para datos de contrato extraidos"""
        return {
            "valor_contrato": 25000000.0,
            "tipo_cuantia": "menor_cuantia",
            "ID_contrato": "CT-2024-001"
        }

    @pytest.fixture
    def parametros_validacion(self):
        """Fixture para parametros de validacion"""
        return {
            "nit_administrativo": "900123456",
            "codigo_del_negocio": 1001,
            "proveedor": "Proveedor Test",
            "documentos_clasificados": {"factura.pdf": {"categoria": "factura"}},
            "archivos_directos": [],
            "cache_archivos": {}
        }

    # =========================================================================
    # TESTS DEL METODO validar()
    # =========================================================================

    @pytest.mark.asyncio
    async def test_validar_con_timbre_exitoso(
        self,
        validador,
        mock_liquidador,
        resultados_analisis_con_timbre_aplica,
        parametros_validacion
    ):
        """Test: Validacion exitosa cuando Timbre aplica"""
        validador.liquidador_timbre = mock_liquidador

        # Mock de extraccion de datos
        with patch.object(validador, '_extraer_datos_contrato', new_callable=AsyncMock) as mock_extraer:
            mock_extraer.return_value = {"valor_contrato": 25000000.0}

            resultado = await validador.validar(
                resultados_analisis=resultados_analisis_con_timbre_aplica,
                aplica_timbre=True,
                **parametros_validacion
            )

            assert resultado is not None
            assert resultado["aplica"] is True
            assert resultado["estado"] == "liquidado"
            assert resultado["valor"] == 250000.0
            mock_liquidador.liquidar_timbre.assert_called_once()
            mock_extraer.assert_called_once()

    @pytest.mark.asyncio
    async def test_validar_con_timbre_no_aplica_observaciones(
        self,
        validador,
        resultados_analisis_con_timbre_no_aplica,
        parametros_validacion
    ):
        """Test: Retorna resultado no aplica cuando observaciones lo indican"""
        resultado = await validador.validar(
            resultados_analisis=resultados_analisis_con_timbre_no_aplica,
            aplica_timbre=True,
            **parametros_validacion
        )

        assert resultado is not None
        assert resultado["aplica"] is False
        assert resultado["estado"] == "no_aplica_impuesto"
        assert "No se identifico aplicacion" in resultado["observaciones"]

    @pytest.mark.asyncio
    async def test_validar_sin_timbre_retorna_none(
        self,
        validador,
        resultados_analisis_sin_timbre,
        parametros_validacion
    ):
        """Test: Retorna None cuando no existe analisis de Timbre"""
        resultado = await validador.validar(
            resultados_analisis=resultados_analisis_sin_timbre,
            aplica_timbre=True,
            **parametros_validacion
        )

        assert resultado is None

    @pytest.mark.asyncio
    async def test_validar_con_aplica_timbre_false_retorna_none(
        self,
        validador,
        resultados_analisis_con_timbre_aplica,
        parametros_validacion
    ):
        """Test: Retorna None cuando aplica_timbre es False"""
        resultado = await validador.validar(
            resultados_analisis=resultados_analisis_con_timbre_aplica,
            aplica_timbre=False,
            **parametros_validacion
        )

        assert resultado is None

    @pytest.mark.asyncio
    async def test_validar_maneja_error_en_liquidacion(
        self,
        validador,
        mock_liquidador,
        resultados_analisis_con_timbre_aplica,
        parametros_validacion
    ):
        """Test: Maneja errores durante la liquidacion"""
        mock_liquidador.liquidar_timbre.side_effect = Exception("Error de prueba")
        validador.liquidador_timbre = mock_liquidador

        with patch.object(validador, '_extraer_datos_contrato', new_callable=AsyncMock) as mock_extraer:
            mock_extraer.return_value = {"valor_contrato": 25000000.0}

            resultado = await validador.validar(
                resultados_analisis=resultados_analisis_con_timbre_aplica,
                aplica_timbre=True,
                **parametros_validacion
            )

            assert resultado is not None
            assert resultado["aplica"] is False
            assert resultado["estado"] == "preliquidacion_sin_finalizar"
            assert "error" in resultado
            assert "Error de prueba" in resultado["error"]

    # =========================================================================
    # TESTS DEL METODO _debe_procesar_timbre()
    # =========================================================================

    def test_debe_procesar_timbre_con_analisis_y_flag_true(
        self,
        validador,
        resultados_analisis_con_timbre_aplica
    ):
        """Test: Debe procesar cuando existe analisis y flag es True"""
        resultado = validador._debe_procesar_timbre(
            resultados_analisis_con_timbre_aplica,
            aplica_timbre=True
        )
        assert resultado is True

    def test_debe_procesar_timbre_sin_analisis(
        self,
        validador,
        resultados_analisis_sin_timbre
    ):
        """Test: No debe procesar cuando no existe analisis"""
        resultado = validador._debe_procesar_timbre(
            resultados_analisis_sin_timbre,
            aplica_timbre=True
        )
        assert resultado is False

    def test_debe_procesar_timbre_con_flag_false(
        self,
        validador,
        resultados_analisis_con_timbre_aplica
    ):
        """Test: No debe procesar cuando flag es False"""
        resultado = validador._debe_procesar_timbre(
            resultados_analisis_con_timbre_aplica,
            aplica_timbre=False
        )
        assert resultado is False

    # =========================================================================
    # TESTS DEL METODO _verifica_aplicabilidad_observaciones()
    # =========================================================================

    def test_verifica_aplicabilidad_cuando_aplica(
        self,
        validador
    ):
        """Test: Verifica correctamente cuando aplica segun observaciones"""
        analisis = {"aplica_timbre": True}
        resultado = validador._verifica_aplicabilidad_observaciones(analisis)
        assert resultado is True

    def test_verifica_aplicabilidad_cuando_no_aplica(
        self,
        validador
    ):
        """Test: Verifica correctamente cuando no aplica segun observaciones"""
        analisis = {"aplica_timbre": False}
        resultado = validador._verifica_aplicabilidad_observaciones(analisis)
        assert resultado is False

    def test_verifica_aplicabilidad_con_campo_faltante(
        self,
        validador
    ):
        """Test: Retorna False cuando campo aplica_timbre no existe"""
        analisis = {}
        resultado = validador._verifica_aplicabilidad_observaciones(analisis)
        assert resultado is False

    # =========================================================================
    # TESTS DEL METODO _crear_resultado_no_aplica_observaciones()
    # =========================================================================

    def test_crear_resultado_no_aplica_observaciones(
        self,
        validador,
        caplog
    ):
        """Test: Crea resultado correcto cuando no aplica por observaciones"""
        with caplog.at_level(logging.INFO):
            resultado = validador._crear_resultado_no_aplica_observaciones()

        assert resultado["aplica"] is False
        assert resultado["estado"] == "no_aplica_impuesto"
        assert resultado["valor"] == 0.0
        assert resultado["tarifa"] == 0.0
        assert "No se identifico aplicacion" in resultado["observaciones"]
        assert "No aplica según observaciones" in caplog.text

    # =========================================================================
    # TESTS DEL METODO _extraer_datos_contrato()
    # =========================================================================

    @pytest.mark.asyncio
    async def test_extraer_datos_contrato_exitoso(
        self,
        validador,
        datos_contrato_mock
    ):
        """Test: Extrae datos del contrato correctamente"""
        with patch('app.validar_timbre.ClasificadorTimbre') as mock_clasificador_class:
            mock_instance = Mock()
            mock_instance.extraer_datos_contrato = AsyncMock(return_value=datos_contrato_mock)
            mock_clasificador_class.return_value = mock_instance

            resultado = await validador._extraer_datos_contrato(
                documentos_clasificados={"factura.pdf": {}},
                archivos_directos=[],
                cache_archivos={}
            )

            assert resultado == datos_contrato_mock
            mock_instance.extraer_datos_contrato.assert_called_once()

    # =========================================================================
    # TESTS DEL METODO _ejecutar_liquidacion()
    # =========================================================================

    def test_ejecutar_liquidacion_con_liquidador_inyectado(
        self,
        validador,
        mock_liquidador
    ):
        """Test: Usa liquidador inyectado si esta disponible"""
        validador.liquidador_timbre = mock_liquidador

        resultado = validador._ejecutar_liquidacion(
            nit_administrativo="900123456",
            codigo_del_negocio=1001,
            proveedor="Proveedor Test",
            analisis_observaciones={"aplica_timbre": True},
            datos_contrato={"valor_contrato": 25000000.0}
        )

        mock_liquidador.liquidar_timbre.assert_called_once()
        assert resultado.aplica is True

    @patch('app.validar_timbre.LiquidadorTimbre')
    def test_ejecutar_liquidacion_lazy_initialization(
        self,
        mock_liquidador_class,
        validador
    ):
        """Test: Crea liquidador si no fue inyectado (lazy initialization)"""
        mock_instance = Mock()
        mock_resultado = Mock()
        mock_resultado.aplica = True
        mock_resultado.valor = 250000.0
        mock_instance.liquidar_timbre = Mock(return_value=mock_resultado)
        mock_liquidador_class.return_value = mock_instance

        validador.liquidador_timbre = None

        resultado = validador._ejecutar_liquidacion(
            nit_administrativo="900123456",
            codigo_del_negocio=1001,
            proveedor="Proveedor Test",
            analisis_observaciones={"aplica_timbre": True},
            datos_contrato={"valor_contrato": 25000000.0}
        )

        mock_liquidador_class.assert_called_once_with(db_manager=validador.db_manager)
        mock_instance.liquidar_timbre.assert_called_once()
        assert resultado.aplica is True

    # =========================================================================
    # TESTS DEL METODO _log_resultado()
    # =========================================================================

    def test_log_resultado_cuando_aplica(
        self,
        validador,
        caplog
    ):
        """Test: Logging correcto cuando Timbre aplica"""
        mock_resultado = Mock()
        mock_resultado.aplica = True
        mock_resultado.valor = 250000.0
        mock_resultado.tarifa = 0.01
        mock_resultado.estado = "liquidado"

        with caplog.at_level(logging.INFO):
            validador._log_resultado(mock_resultado)

        assert "Timbre liquidado: $250,000.00" in caplog.text
        assert "Tarifa: 1.0%" in caplog.text

    def test_log_resultado_cuando_no_aplica(
        self,
        validador,
        caplog
    ):
        """Test: Logging correcto cuando Timbre no aplica"""
        mock_resultado = Mock()
        mock_resultado.aplica = False
        mock_resultado.estado = "no_aplica_impuesto"

        with caplog.at_level(logging.INFO):
            validador._log_resultado(mock_resultado)

        assert "Timbre: no_aplica_impuesto" in caplog.text

    # =========================================================================
    # TESTS DEL METODO _manejar_error()
    # =========================================================================

    def test_manejar_error_genera_estructura_correcta(
        self,
        validador,
        caplog
    ):
        """Test: Genera estructura de error correcta"""
        excepcion = ValueError("Error de prueba en validacion")

        with caplog.at_level(logging.ERROR):
            resultado = validador._manejar_error(excepcion)

        assert resultado["aplica"] is False
        assert resultado["estado"] == "preliquidacion_sin_finalizar"
        assert "error" in resultado
        assert resultado["error"] == "Error de prueba en validacion"
        assert "Error liquidando Timbre" in caplog.text

    # =========================================================================
    # TESTS DE LA FUNCION WRAPPER validar_timbre()
    # =========================================================================

    @pytest.mark.asyncio
    async def test_validar_timbre_wrapper_exitoso(
        self,
        mock_db_manager,
        mock_clasificador_gemini,
        resultados_analisis_con_timbre_aplica,
        parametros_validacion
    ):
        """Test: Wrapper function crea validador y delega correctamente"""
        with patch('app.validar_timbre.ValidadorTimbre') as mock_validador_class:
            mock_instance = Mock()
            mock_instance.validar = AsyncMock(return_value={
                "aplica": True,
                "valor": 250000.0,
                "estado": "liquidado"
            })
            mock_validador_class.return_value = mock_instance

            resultado = await validar_timbre(
                resultados_analisis=resultados_analisis_con_timbre_aplica,
                aplica_timbre=True,
                db_manager=mock_db_manager,
                clasificador_gemini=mock_clasificador_gemini,
                **parametros_validacion
            )

            mock_validador_class.assert_called_once_with(
                db_manager=mock_db_manager,
                clasificador_gemini=mock_clasificador_gemini
            )
            assert resultado is not None
            assert resultado["aplica"] is True

    @pytest.mark.asyncio
    async def test_validar_timbre_wrapper_retorna_none(
        self,
        mock_db_manager,
        mock_clasificador_gemini,
        resultados_analisis_sin_timbre,
        parametros_validacion
    ):
        """Test: Wrapper retorna None cuando no aplica"""
        resultado = await validar_timbre(
            resultados_analisis=resultados_analisis_sin_timbre,
            aplica_timbre=True,
            db_manager=mock_db_manager,
            clasificador_gemini=mock_clasificador_gemini,
            **parametros_validacion
        )

        assert resultado is None

    # =========================================================================
    # TESTS DE INTEGRACION
    # =========================================================================

    @pytest.mark.asyncio
    async def test_flujo_completo_liquidacion_exitosa(
        self,
        validador,
        mock_liquidador,
        resultados_analisis_con_timbre_aplica
    ):
        """Test: Flujo completo con doble llamada a Gemini"""
        validador.liquidador_timbre = mock_liquidador

        with patch.object(validador, '_extraer_datos_contrato', new_callable=AsyncMock) as mock_extraer:
            mock_extraer.return_value = {
                "valor_contrato": 25000000.0,
                "tipo_cuantia": "menor_cuantia",
                "ID_contrato": "CT-2024-001"
            }

            resultado = await validador.validar(
                resultados_analisis=resultados_analisis_con_timbre_aplica,
                aplica_timbre=True,
                nit_administrativo="900123456",
                codigo_del_negocio=1001,
                proveedor="Proveedor Test",
                documentos_clasificados={"contrato.pdf": {}},
                archivos_directos=[],
                cache_archivos={}
            )

            assert resultado["aplica"] is True
            assert resultado["valor"] == 250000.0
            assert resultado["ID_contrato"] == "CT-2024-001"
            mock_extraer.assert_called_once()
            mock_liquidador.liquidar_timbre.assert_called_once()


# =========================================================================
# TESTS PARAMETRIZADOS
# =========================================================================

class TestValidadorTimbreParametrizado:
    """Tests parametrizados para ValidadorTimbre"""

    @pytest.mark.parametrize("resultados_analisis,aplica_flag,esperado", [
        # Caso: Con analisis y flag True
        ({"timbre": {"aplica_timbre": True}}, True, True),
        # Caso: Con analisis pero flag False
        ({"timbre": {"aplica_timbre": True}}, False, False),
        # Caso: Sin analisis
        ({"retefuente": {}}, True, False),
        # Caso: Diccionario vacio
        ({}, True, False),
    ])
    def test_debe_procesar_timbre_casos(
        self,
        resultados_analisis,
        aplica_flag,
        esperado
    ):
        """Test parametrizado: Casos de _debe_procesar_timbre"""
        mock_db = Mock()
        mock_clasificador = Mock()
        validador = ValidadorTimbre(
            db_manager=mock_db,
            clasificador_gemini=mock_clasificador
        )

        resultado = validador._debe_procesar_timbre(resultados_analisis, aplica_flag)

        assert resultado == esperado

    @pytest.mark.parametrize("analisis,esperado", [
        # Caso: Aplica True
        ({"aplica_timbre": True}, True),
        # Caso: Aplica False
        ({"aplica_timbre": False}, False),
        # Caso: Campo faltante
        ({}, False),
        # Caso: Valor None
        ({"aplica_timbre": None}, False),
    ])
    def test_verifica_aplicabilidad_casos(
        self,
        analisis,
        esperado
    ):
        """Test parametrizado: Casos de _verifica_aplicabilidad_observaciones"""
        mock_db = Mock()
        mock_clasificador = Mock()
        validador = ValidadorTimbre(
            db_manager=mock_db,
            clasificador_gemini=mock_clasificador
        )

        resultado = validador._verifica_aplicabilidad_observaciones(analisis)

        assert resultado == esperado
