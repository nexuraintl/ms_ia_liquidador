"""
Tests para el modulo validar_tasa_prodeporte.py

Tests implementados:
- Validacion de Tasa Prodeporte con analisis exitoso
- Validacion cuando no hay analisis de Tasa Prodeporte
- Validacion del metodo _debe_procesar_tasa_prodeporte
- Validacion del metodo _crear_parametros
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

from app.validar_tasa_prodeporte import ValidadorTasaProdeporte, validar_tasa_prodeporte


class TestValidadorTasaProdeporte:
    """Tests para la clase ValidadorTasaProdeporte"""

    @pytest.fixture
    def mock_db_manager(self):
        """Fixture para mock de database manager"""
        return Mock()

    @pytest.fixture
    def mock_liquidador(self):
        """Fixture para mock de liquidador tasa prodeporte"""
        mock = Mock()
        # Crear mock del resultado Pydantic
        mock_resultado = Mock()
        mock_resultado.aplica = True
        mock_resultado.estado = "liquidado"
        mock_resultado.valor_imp = 150000.0
        mock_resultado.tarifa = 0.025
        mock_resultado.dict = Mock(return_value={
            "aplica": True,
            "estado": "liquidado",
            "valor_imp": 150000.0,
            "tarifa": 0.025,
            "valor_convenio_sin_iva": 6000000.0,
            "porcentaje_convenio": 100.0,
            "valor_contrato_municipio": 0.0,
            "factura_sin_iva": 6000000.0,
            "factura_con_iva": 6000000.0,
            "municipio_dept": "Bogotá D.C.",
            "numero_contrato": "CT-2024-001",
            "observaciones": "Liquidacion exitosa"
        })
        mock.liquidar = Mock(return_value=mock_resultado)
        return mock

    @pytest.fixture
    def validador(self, mock_db_manager):
        """Fixture para crear instancia de ValidadorTasaProdeporte"""
        return ValidadorTasaProdeporte(db_manager=mock_db_manager)

    @pytest.fixture
    def resultados_analisis_con_tp(self):
        """Fixture para resultados de analisis con Tasa Prodeporte"""
        return {
            "tasa_prodeporte": {
                "valor_factura_sin_iva": 6000000.0,
                "valor_factura_con_iva": 6000000.0,
                "municipio_departamento": "Bogotá D.C.",
                "observaciones_gemini": "Contrato de turismo"
            }
        }

    @pytest.fixture
    def resultados_analisis_sin_tp(self):
        """Fixture para resultados sin Tasa Prodeporte"""
        return {
            "retefuente": {
                "conceptos": ["Servicios generales"],
                "valor_factura": 1000000.0
            }
        }

    @pytest.fixture
    def parametros_endpoint(self):
        """Fixture para parametros del endpoint"""
        return {
            "observaciones_tp": "Contrato turismo",
            "genera_presupuesto": "SI",
            "rubro": "4.3.2.01",
            "centro_costos": 1001,
            "numero_contrato": "CT-2024-001",
            "valor_contrato_municipio": 10000000.0
        }

    # =========================================================================
    # TESTS DEL METODO validar()
    # =========================================================================

    @pytest.mark.asyncio
    async def test_validar_con_tp_exitoso(
        self,
        validador,
        mock_liquidador,
        resultados_analisis_con_tp,
        parametros_endpoint
    ):
        """Test: Validacion exitosa cuando existe analisis de Tasa Prodeporte"""
        validador.liquidador_tp = mock_liquidador

        resultado = await validador.validar(
            resultados_analisis=resultados_analisis_con_tp,
            **parametros_endpoint
        )

        assert resultado is not None
        assert resultado["aplica"] is True
        assert resultado["estado"] == "liquidado"
        assert resultado["valor_imp"] == 150000.0
        assert resultado["tarifa"] == 0.025
        mock_liquidador.liquidar.assert_called_once()

    @pytest.mark.asyncio
    async def test_validar_sin_tp_retorna_none(
        self,
        validador,
        resultados_analisis_sin_tp,
        parametros_endpoint
    ):
        """Test: Retorna None cuando no existe analisis de Tasa Prodeporte"""
        resultado = await validador.validar(
            resultados_analisis=resultados_analisis_sin_tp,
            **parametros_endpoint
        )

        assert resultado is None

    @pytest.mark.asyncio
    async def test_validar_con_resultados_vacios_retorna_none(
        self,
        validador,
        parametros_endpoint
    ):
        """Test: Retorna None cuando resultados_analisis esta vacio"""
        resultado = await validador.validar(
            resultados_analisis={},
            **parametros_endpoint
        )

        assert resultado is None

    @pytest.mark.asyncio
    async def test_validar_maneja_error_en_liquidacion(
        self,
        validador,
        mock_liquidador,
        resultados_analisis_con_tp,
        parametros_endpoint
    ):
        """Test: Maneja errores durante la liquidacion"""
        mock_liquidador.liquidar.side_effect = Exception("Error de prueba en liquidacion")
        validador.liquidador_tp = mock_liquidador

        resultado = await validador.validar(
            resultados_analisis=resultados_analisis_con_tp,
            **parametros_endpoint
        )

        assert resultado is not None
        assert resultado["aplica"] is False
        assert resultado["estado"] == "preliquidacion_sin_finalizar"
        assert "error" in resultado
        assert "Error de prueba en liquidacion" in resultado["error"]

    # =========================================================================
    # TESTS DEL METODO _debe_procesar_tasa_prodeporte()
    # =========================================================================

    def test_debe_procesar_tp_con_analisis_presente(
        self,
        validador,
        resultados_analisis_con_tp
    ):
        """Test: Debe procesar cuando analisis de TP esta presente"""
        resultado = validador._debe_procesar_tasa_prodeporte(resultados_analisis_con_tp)
        assert resultado is True

    def test_debe_procesar_tp_sin_analisis(
        self,
        validador,
        resultados_analisis_sin_tp
    ):
        """Test: No debe procesar cuando analisis de TP no esta presente"""
        resultado = validador._debe_procesar_tasa_prodeporte(resultados_analisis_sin_tp)
        assert resultado is False

    def test_debe_procesar_tp_con_dict_vacio(
        self,
        validador
    ):
        """Test: No debe procesar cuando resultados_analisis esta vacio"""
        resultado = validador._debe_procesar_tasa_prodeporte({})
        assert resultado is False

    # =========================================================================
    # TESTS DEL METODO _crear_parametros()
    # =========================================================================

    def test_crear_parametros_con_todos_los_datos(
        self,
        validador
    ):
        """Test: Crea parametros correctamente con todos los datos"""
        parametros = validador._crear_parametros(
            observaciones_tp="Contrato turismo",
            genera_presupuesto="SI",
            rubro="4.3.2.01",
            centro_costos=1001,
            numero_contrato="CT-2024-001",
            valor_contrato_municipio=10000000.0
        )

        assert parametros.observaciones == "Contrato turismo"
        assert parametros.genera_presupuesto == "SI"
        assert parametros.rubro == "4.3.2.01"
        assert parametros.centro_costos == 1001
        assert parametros.numero_contrato == "CT-2024-001"
        assert parametros.valor_contrato_municipio == 10000000.0

    def test_crear_parametros_con_valores_none(
        self,
        validador
    ):
        """Test: Crea parametros con valores None"""
        parametros = validador._crear_parametros(
            observaciones_tp=None,
            genera_presupuesto=None,
            rubro=None,
            centro_costos=None,
            numero_contrato=None,
            valor_contrato_municipio=None
        )

        assert parametros.observaciones is None
        assert parametros.genera_presupuesto is None
        assert parametros.rubro is None
        assert parametros.centro_costos is None
        assert parametros.numero_contrato is None
        assert parametros.valor_contrato_municipio is None

    # =========================================================================
    # TESTS DEL METODO _ejecutar_liquidacion()
    # =========================================================================

    def test_ejecutar_liquidacion_con_liquidador_inyectado(
        self,
        validador,
        mock_liquidador
    ):
        """Test: Usa liquidador inyectado si esta disponible"""
        validador.liquidador_tp = mock_liquidador

        from Liquidador.liquidador_TP import ParametrosTasaProdeporte
        parametros = ParametrosTasaProdeporte(
            observaciones="Test",
            genera_presupuesto="SI",
            rubro="4.3.2.01",
            centro_costos=1001,
            numero_contrato="CT-2024-001",
            valor_contrato_municipio=10000000.0
        )
        analisis = {"valor_factura_sin_iva": 6000000.0}

        resultado = validador._ejecutar_liquidacion(parametros, analisis)

        mock_liquidador.liquidar.assert_called_once_with(parametros, analisis)
        assert resultado.aplica is True

    @patch('app.validar_tasa_prodeporte.LiquidadorTasaProdeporte')
    def test_ejecutar_liquidacion_lazy_initialization(
        self,
        mock_liquidador_class,
        validador
    ):
        """Test: Crea liquidador si no fue inyectado (lazy initialization)"""
        mock_instance = Mock()
        mock_resultado = Mock()
        mock_resultado.aplica = True
        mock_resultado.valor_imp = 150000.0
        mock_instance.liquidar = Mock(return_value=mock_resultado)
        mock_liquidador_class.return_value = mock_instance

        validador.liquidador_tp = None

        from Liquidador.liquidador_TP import ParametrosTasaProdeporte
        parametros = ParametrosTasaProdeporte(
            observaciones="Test",
            genera_presupuesto="SI",
            rubro="4.3.2.01",
            centro_costos=1001,
            numero_contrato="CT-2024-001",
            valor_contrato_municipio=10000000.0
        )
        analisis = {"valor_factura_sin_iva": 6000000.0}

        resultado = validador._ejecutar_liquidacion(parametros, analisis)

        mock_liquidador_class.assert_called_once_with(db_interface=validador.db_manager)
        mock_instance.liquidar.assert_called_once()
        assert resultado.aplica is True

    # =========================================================================
    # TESTS DEL METODO _log_resultado()
    # =========================================================================

    def test_log_resultado_cuando_aplica(
        self,
        validador,
        caplog
    ):
        """Test: Logging correcto cuando Tasa Prodeporte aplica"""
        mock_resultado = Mock()
        mock_resultado.aplica = True
        mock_resultado.valor_imp = 150000.0
        mock_resultado.tarifa = 0.025
        mock_resultado.estado = "liquidado"

        with caplog.at_level(logging.INFO):
            validador._log_resultado(mock_resultado)

        assert "Tasa Prodeporte liquidada: $150,000.00" in caplog.text
        assert "Tarifa: 2.5%" in caplog.text

    def test_log_resultado_cuando_no_aplica(
        self,
        validador,
        caplog
    ):
        """Test: Logging correcto cuando Tasa Prodeporte no aplica"""
        mock_resultado = Mock()
        mock_resultado.aplica = False
        mock_resultado.estado = "no_aplica_impuesto"

        with caplog.at_level(logging.INFO):
            validador._log_resultado(mock_resultado)

        assert "Tasa Prodeporte: no_aplica_impuesto" in caplog.text

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

        assert "Error liquidando Tasa Prodeporte" in caplog.text

    # =========================================================================
    # TESTS DE LA FUNCION WRAPPER validar_tasa_prodeporte()
    # =========================================================================

    @pytest.mark.asyncio
    async def test_validar_tp_wrapper_exitoso(
        self,
        mock_db_manager,
        resultados_analisis_con_tp,
        parametros_endpoint
    ):
        """Test: Wrapper function crea validador y delega correctamente"""
        with patch('app.validar_tasa_prodeporte.ValidadorTasaProdeporte') as mock_validador_class:
            mock_instance = Mock()
            mock_instance.validar = AsyncMock(return_value={
                "aplica": True,
                "valor_imp": 150000.0,
                "estado": "liquidado"
            })
            mock_validador_class.return_value = mock_instance

            resultado = await validar_tasa_prodeporte(
                resultados_analisis=resultados_analisis_con_tp,
                db_manager=mock_db_manager,
                **parametros_endpoint
            )

            mock_validador_class.assert_called_once_with(db_manager=mock_db_manager)
            assert resultado is not None
            assert resultado["aplica"] is True

    @pytest.mark.asyncio
    async def test_validar_tp_wrapper_retorna_none(
        self,
        mock_db_manager,
        resultados_analisis_sin_tp,
        parametros_endpoint
    ):
        """Test: Wrapper retorna None cuando no aplica"""
        resultado = await validar_tasa_prodeporte(
            resultados_analisis=resultados_analisis_sin_tp,
            db_manager=mock_db_manager,
            **parametros_endpoint
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
        resultados_analisis_con_tp
    ):
        """Test: Flujo completo con liquidacion exitosa"""
        validador.liquidador_tp = mock_liquidador

        resultado = await validador.validar(
            resultados_analisis=resultados_analisis_con_tp,
            observaciones_tp="Contrato turismo",
            genera_presupuesto="SI",
            rubro="4.3.2.01",
            centro_costos=1001,
            numero_contrato="CT-2024-001",
            valor_contrato_municipio=10000000.0
        )

        assert resultado["aplica"] is True
        assert resultado["valor_imp"] == 150000.0
        assert resultado["numero_contrato"] == "CT-2024-001"
        assert resultado["municipio_dept"] == "Bogotá D.C."

    @pytest.mark.asyncio
    async def test_flujo_completo_con_parametros_opcionales_none(
        self,
        validador,
        mock_liquidador,
        resultados_analisis_con_tp
    ):
        """Test: Flujo completo con parametros opcionales en None"""
        validador.liquidador_tp = mock_liquidador

        resultado = await validador.validar(
            resultados_analisis=resultados_analisis_con_tp,
            observaciones_tp=None,
            genera_presupuesto=None,
            rubro=None,
            centro_costos=None,
            numero_contrato=None,
            valor_contrato_municipio=None
        )

        assert resultado is not None
        assert resultado["aplica"] is True
        mock_liquidador.liquidar.assert_called_once()


# =========================================================================
# TESTS PARAMETRIZADOS
# =========================================================================

class TestValidadorTasaProdeporteParametrizado:
    """Tests parametrizados para ValidadorTasaProdeporte"""

    @pytest.mark.parametrize("resultados_analisis,esperado", [
        # Caso: Con Tasa Prodeporte
        (
            {"tasa_prodeporte": {"valor_factura": 1000000.0}},
            True
        ),
        # Caso: Sin Tasa Prodeporte
        (
            {"retefuente": {"conceptos": ["Servicios"]}},
            False
        ),
        # Caso: Diccionario vacio
        (
            {},
            False
        ),
        # Caso: Tasa Prodeporte en None
        (
            {"tasa_prodeporte": None},
            True  # Porque "tasa_prodeporte" in dict es True
        ),
    ])
    def test_debe_procesar_tp_casos(
        self,
        resultados_analisis,
        esperado
    ):
        """Test parametrizado: Casos de _debe_procesar_tasa_prodeporte"""
        mock_db = Mock()
        validador = ValidadorTasaProdeporte(db_manager=mock_db)

        resultado = validador._debe_procesar_tasa_prodeporte(resultados_analisis)

        assert resultado == esperado

    @pytest.mark.parametrize("observaciones,genera,rubro,centro,contrato,valor", [
        # Caso: Todos los parametros completos
        ("Obs", "SI", "4.3.2.01", 1001, "CT-001", 10000000.0),
        # Caso: Todos None
        (None, None, None, None, None, None),
        # Caso: Algunos valores, otros None
        ("Obs", "SI", None, None, "CT-001", None),
    ])
    def test_crear_parametros_casos(
        self,
        observaciones,
        genera,
        rubro,
        centro,
        contrato,
        valor
    ):
        """Test parametrizado: Creacion de parametros con diferentes valores"""
        mock_db = Mock()
        validador = ValidadorTasaProdeporte(db_manager=mock_db)

        parametros = validador._crear_parametros(
            observaciones_tp=observaciones,
            genera_presupuesto=genera,
            rubro=rubro,
            centro_costos=centro,
            numero_contrato=contrato,
            valor_contrato_municipio=valor
        )

        assert parametros.observaciones == observaciones
        assert parametros.genera_presupuesto == genera
        assert parametros.rubro == rubro
        assert parametros.centro_costos == centro
        assert parametros.numero_contrato == contrato
        assert parametros.valor_contrato_municipio == valor
