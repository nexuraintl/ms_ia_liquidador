"""
Tests para LiquidadorTasaProdeporte con inyeccion de dependencias

Cobertura:
- Constructor con DIP
- Liquidacion con consulta a BD
- Manejo de errores de BD
- Validaciones del liquidador
"""

import pytest
from unittest.mock import Mock
import json
from pathlib import Path

# Importar clases a testear
from Liquidador.liquidador_TP import LiquidadorTasaProdeporte, ParametrosTasaProdeporte


# ===============================
# FIXTURES
# ===============================

@pytest.fixture
def mock_db_interface():
    """Mock de DatabaseInterface para inyeccion de dependencias"""
    return Mock()


@pytest.fixture
def fixture_analisis_gemini():
    """Carga fixture de analisis Gemini"""
    fixture_path = Path(__file__).parent / 'fixtures' / 'analisis_gemini_tasa_prodeporte.json'
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture
def fixture_parametros():
    """Carga fixture de parametros"""
    fixture_path = Path(__file__).parent / 'fixtures' / 'parametros_tasa_prodeporte.json'
    with open(fixture_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return ParametrosTasaProdeporte(**data)


# ===============================
# TESTS - Constructor DIP
# ===============================

class TestConstructorDIP:
    """Tests para constructor con inyeccion de dependencias"""

    def test_constructor_requiere_db_interface(self):
        """Test ValueError si db_interface es None"""
        with pytest.raises(ValueError, match="requiere db_interface"):
            LiquidadorTasaProdeporte(db_interface=None)

    def test_constructor_acepta_db_interface(self, mock_db_interface):
        """Test constructor exitoso con mock DatabaseInterface"""
        liquidador = LiquidadorTasaProdeporte(db_interface=mock_db_interface)

        assert liquidador.db is mock_db_interface


# ===============================
# TESTS - Liquidacion con BD
# ===============================

class TestLiquidacionConBD:
    """Tests para liquidar() usando BD en lugar de diccionario"""

    def test_liquidar_rubro_valido_encontrado_bd(self, mock_db_interface, fixture_parametros, fixture_analisis_gemini):
        """Test liquidacion exitosa con rubro encontrado en BD"""
        # Configurar mock de BD
        mock_db_interface.obtener_datos_rubro_tasa_prodeporte.return_value = {
            'success': True,
            'data': {
                'tarifa': 0.015,
                'centro_costo': 11783,
                'municipio_departamento': 'El jardin'
            },
            'message': 'Rubro encontrado'
        }

        liquidador = LiquidadorTasaProdeporte(db_interface=mock_db_interface)
        resultado = liquidador.liquidar(fixture_parametros, fixture_analisis_gemini)

        assert resultado.estado == "preliquidado"
        assert resultado.aplica is True
        assert resultado.tarifa == 0.015
        assert resultado.valor_imp > 0
        mock_db_interface.obtener_datos_rubro_tasa_prodeporte.assert_called_once_with("280101010210")

    def test_liquidar_rubro_no_encontrado_bd(self, mock_db_interface, fixture_parametros, fixture_analisis_gemini):
        """Test rubro no encontrado en BD -> preliquidacion_sin_finalizar"""
        # Configurar mock de BD para retornar error
        mock_db_interface.obtener_datos_rubro_tasa_prodeporte.return_value = {
            'success': False,
            'data': None,
            'message': 'Rubro no esta almacenado en la Base de datos'
        }

        liquidador = LiquidadorTasaProdeporte(db_interface=mock_db_interface)
        resultado = liquidador.liquidar(fixture_parametros, fixture_analisis_gemini)

        assert resultado.estado == "preliquidacion_sin_finalizar"
        assert "no esta almacenado" in resultado.observaciones

    def test_liquidar_bd_timeout(self, mock_db_interface, fixture_parametros, fixture_analisis_gemini):
        """Test timeout de BD -> preliquidacion_sin_finalizar"""
        mock_db_interface.obtener_datos_rubro_tasa_prodeporte.return_value = {
            'success': False,
            'error': 'Timeout',
            'message': 'Timeout al consultar rubro'
        }

        liquidador = LiquidadorTasaProdeporte(db_interface=mock_db_interface)
        resultado = liquidador.liquidar(fixture_parametros, fixture_analisis_gemini)

        assert resultado.estado == "preliquidacion_sin_finalizar"
        assert "Timeout" in resultado.observaciones

    def test_liquidar_validacion_centro_costos_no_coincide(self, mock_db_interface, fixture_analisis_gemini):
        """Test advertencia cuando centro_costos parametro != BD"""
        # Mock BD con centro_costo diferente
        mock_db_interface.obtener_datos_rubro_tasa_prodeporte.return_value = {
            'success': True,
            'data': {
                'tarifa': 0.015,
                'centro_costo': 11783,  # BD dice 11783
                'municipio_departamento': 'El jardin'
            }
        }

        # Parametros con centro_costos diferente
        parametros = ParametrosTasaProdeporte(
            observaciones="Aplica tasa prodeporte",
            genera_presupuesto="si",
            rubro="280101010210",
            centro_costos=99999,  # Usuario envia 99999
            numero_contrato="TEST-001",
            valor_contrato_municipio=500000
        )

        liquidador = LiquidadorTasaProdeporte(db_interface=mock_db_interface)
        resultado = liquidador.liquidar(parametros, fixture_analisis_gemini)

        assert resultado.estado == "preliquidado"
        assert "Incongruencia" in resultado.observaciones
        assert "11783" in resultado.observaciones
        assert "99999" in resultado.observaciones

    def test_liquidar_calculo_matematico_correcto(self, mock_db_interface, fixture_parametros, fixture_analisis_gemini):
        """Test calculo exacto: valor_convenio_sin_iva * tarifa"""
        mock_db_interface.obtener_datos_rubro_tasa_prodeporte.return_value = {
            'success': True,
            'data': {
                'tarifa': 0.015,
                'centro_costo': 11783,
                'municipio_departamento': 'El jardin'
            }
        }

        liquidador = LiquidadorTasaProdeporte(db_interface=mock_db_interface)
        resultado = liquidador.liquidar(fixture_parametros, fixture_analisis_gemini)

        # Verificar calculo
        # porcentaje_convenio = valor_contrato_municipio / factura_con_iva
        # valor_convenio_sin_iva = factura_sin_iva * porcentaje_convenio
        # valor_imp = valor_convenio_sin_iva * tarifa
        porcentaje_convenio = 500000 / 1190000
        valor_convenio_sin_iva = 1000000 * porcentaje_convenio
        valor_esperado = valor_convenio_sin_iva * 0.015

        assert abs(resultado.valor_imp - valor_esperado) < 0.01

    def test_liquidar_no_aplica_por_observaciones(self, mock_db_interface, fixture_parametros):
        """Test no_aplica cuando Gemini dice aplica_tasa_prodeporte=False"""
        analisis_gemini = {
            'aplica_tasa_prodeporte': False,  # Gemini dice que NO aplica
            'factura_sin_iva': 1000000,
            'factura_con_iva': 1190000
        }

        liquidador = LiquidadorTasaProdeporte(db_interface=mock_db_interface)
        resultado = liquidador.liquidar(fixture_parametros, analisis_gemini)

        assert resultado.estado == "no_aplica_impuesto"
        assert "no menciona" in resultado.observaciones.lower()
        # No debe consultar BD si no aplica
        mock_db_interface.obtener_datos_rubro_tasa_prodeporte.assert_not_called()

    def test_liquidar_no_genera_presupuesto(self, mock_db_interface, fixture_analisis_gemini):
        """Test no_aplica cuando genera_presupuesto != 'si'"""
        parametros = ParametrosTasaProdeporte(
            observaciones="Test",
            genera_presupuesto="no",  # No genera presupuesto
            rubro="280101010210",
            centro_costos=11783,
            numero_contrato="TEST-001",
            valor_contrato_municipio=500000
        )

        liquidador = LiquidadorTasaProdeporte(db_interface=mock_db_interface)
        resultado = liquidador.liquidar(parametros, fixture_analisis_gemini)

        assert resultado.estado == "no_aplica_impuesto"
        assert "no genera Presupuesto" in resultado.observaciones
        # No debe consultar BD si no genera presupuesto
        mock_db_interface.obtener_datos_rubro_tasa_prodeporte.assert_not_called()

    def test_liquidar_rubro_no_inicia_con_28(self, mock_db_interface, fixture_analisis_gemini):
        """Test no_aplica cuando rubro no inicia con '28'"""
        parametros = ParametrosTasaProdeporte(
            observaciones="Test",
            genera_presupuesto="si",
            rubro="180101010210",  # No inicia con 28
            centro_costos=11783,
            numero_contrato="TEST-001",
            valor_contrato_municipio=500000
        )

        liquidador = LiquidadorTasaProdeporte(db_interface=mock_db_interface)
        resultado = liquidador.liquidar(parametros, fixture_analisis_gemini)

        assert resultado.estado == "no_aplica_impuesto"
        assert "no inicia con 28" in resultado.observaciones
        # No debe consultar BD si rubro no es valido
        mock_db_interface.obtener_datos_rubro_tasa_prodeporte.assert_not_called()
