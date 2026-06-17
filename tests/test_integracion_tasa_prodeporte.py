"""
Tests de integracion end-to-end para Tasa Prodeporte

NOTA: Estos tests requieren conexion a Nexura API real
Usar: pytest tests/test_integracion_tasa_prodeporte.py -v -m integration
"""

import pytest
import os

# Importar clases necesarias
from database.database import NexuraAPIDatabase
from Liquidador.liquidador_TP import LiquidadorTasaProdeporte, ParametrosTasaProdeporte


# ===============================
# HELPERS
# ===============================

def tiene_conexion_nexura():
    """Verifica si hay conexion y credenciales para Nexura API"""
    # Verificar variables de entorno necesarias
    return all([
        os.getenv('NEXURA_API_URL'),
        os.getenv('NEXURA_API_KEY')
    ])


# ===============================
# TESTS DE INTEGRACION
# ===============================

@pytest.mark.integration
@pytest.mark.skipif(not tiene_conexion_nexura(), reason="Sin conexion a Nexura API o credenciales faltantes")
class TestIntegracionNexuraReal:
    """Tests con API real de Nexura (requieren conexion)"""

    @pytest.fixture(scope="class")
    def db_nexura_real(self):
        """
        Instancia real de NexuraAPIDatabase

        IMPORTANTE: Requiere variables de entorno:
        - NEXURA_API_URL
        - NEXURA_API_KEY o configuracion de auth
        """
        # Nota: La implementacion exacta dependera de como se configure
        # el auth_provider en el entorno real
        pytest.skip("Implementacion de auth provider pendiente para tests de integracion")

    def test_consultar_rubro_conocido_280101010210(self, db_nexura_real):
        """Test consultar rubro real '280101010210' -> El jardin 1.5%"""
        resultado = db_nexura_real.obtener_datos_rubro_tasa_prodeporte("280101010210")

        assert resultado['success'] is True
        assert resultado['data']['tarifa'] == 0.015
        assert resultado['data']['centro_costo'] == 11783
        assert 'jardin' in resultado['data']['municipio_departamento'].lower()

    def test_consultar_rubro_inexistente(self, db_nexura_real):
        """Test consultar rubro que no existe -> 404"""
        resultado = db_nexura_real.obtener_datos_rubro_tasa_prodeporte("999999999999")

        assert resultado['success'] is False
        assert 'no esta almacenado' in resultado['message']

    def test_flujo_completo_liquidacion_con_nexura_real(self, db_nexura_real):
        """Test end-to-end: parametros -> consulta BD -> liquidacion"""
        # Crear liquidador con BD real
        liquidador = LiquidadorTasaProdeporte(db_interface=db_nexura_real)

        # Parametros reales
        parametros = ParametrosTasaProdeporte(
            rubro="280101010210",
            genera_presupuesto="si",
            centro_costos=11783,
            numero_contrato="FNTC-350-2021",
            valor_contrato_municipio=500000,
            observaciones="Aplica tasa prodeporte segun convenio"
        )

        # Analisis Gemini simulado
        analisis_gemini = {
            'aplica_tasa_prodeporte': True,
            'factura_sin_iva': 1000000,
            'factura_con_iva': 1190000,
            'iva': 190000
        }

        # Ejecutar liquidacion completa
        resultado = liquidador.liquidar(parametros, analisis_gemini)

        # Verificar resultado final
        assert resultado.estado == "preliquidado"
        assert resultado.aplica is True
        assert resultado.tarifa == 0.015
        assert resultado.valor_imp > 0
        assert resultado.municipio_dept == "El jardin"


# ===============================
# TESTS UNITARIOS CON MOCKS
# ===============================

class TestFlujosIntegrados:
    """Tests de flujos completos usando mocks (no requieren API real)"""

    def test_flujo_completo_mock(self):
        """Test flujo completo con todas las piezas integradas (mock)"""
        from unittest.mock import Mock

        # Mock de BD
        mock_db = Mock()
        mock_db.obtener_datos_rubro_tasa_prodeporte.return_value = {
            'success': True,
            'data': {
                'tarifa': 0.015,
                'centro_costo': 11783,
                'municipio_departamento': 'El jardin'
            },
            'message': 'Rubro encontrado'
        }

        # Crear liquidador
        liquidador = LiquidadorTasaProdeporte(db_interface=mock_db)

        # Datos de entrada
        parametros = ParametrosTasaProdeporte(
            rubro="280101010210",
            genera_presupuesto="si",
            centro_costos=11783,
            numero_contrato="TEST-001",
            valor_contrato_municipio=500000,
            observaciones="Test integracion"
        )

        analisis_gemini = {
            'aplica_tasa_prodeporte': True,
            'factura_sin_iva': 1000000,
            'factura_con_iva': 1190000,
            'iva': 190000
        }

        # Ejecutar
        resultado = liquidador.liquidar(parametros, analisis_gemini)

        # Verificar flujo completo
        assert resultado.estado == "preliquidado"
        assert resultado.aplica is True
        assert mock_db.obtener_datos_rubro_tasa_prodeporte.called
