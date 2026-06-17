"""
Tests de integracion para obtener_rangos_estampilla_universidad.

Incluye tests con API real de Nexura (saltables si no hay credenciales).
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, patch
from database.setup import inicializar_database_manager
from config import obtener_tarifa_estampilla_universidad, limpiar_cache_estampilla_universidad
import config


def tiene_conexion_nexura() -> bool:
    """Verifica si hay credenciales de Nexura configuradas"""
    return (
        os.getenv("NEXURA_API_BASE_URL") is not None and
        os.getenv("DATABASE_TYPE") == "nexura"
    )


@pytest.fixture(autouse=True)
def limpiar_cache_antes_de_cada_test():
    """Fixture que limpia el cache antes de cada test"""
    limpiar_cache_estampilla_universidad()
    yield
    limpiar_cache_estampilla_universidad()


@pytest.fixture(autouse=True)
def patch_uvt_2025():
    """Patch UVT_2025 para que no sea None durante los tests."""
    with patch.object(config, 'UVT_2025', 49799):
        yield


@pytest.mark.integration
@pytest.mark.skipif(
    not tiene_conexion_nexura(),
    reason="Sin conexion a Nexura API o credenciales faltantes"
)
class TestIntegracionNexuraReal:
    """Tests con API real de Nexura (requieren conexion)"""

    def test_flujo_completo_obtener_tarifa_real(self):
        """Test end-to-end: config → database → Nexura API"""
        # Inicializar DatabaseManager con Nexura
        db_manager, _ = asyncio.run(inicializar_database_manager())

        # Test: valor en primer rango (~2,500 UVT, bien por encima del mínimo de 26)
        resultado = obtener_tarifa_estampilla_universidad(120000000, db_manager)

        assert resultado['tarifa'] > 0
        assert resultado['rango_desde_uvt'] >= 0
        assert resultado['uvt_2025'] > 0
        assert resultado['fuente'] == 'database'

        print(f"\nTarifa obtenida: {resultado['tarifa']*100:.2f}%")
        print(f"Rango: {resultado['rango_desde_uvt']} - {resultado['rango_hasta_uvt']} UVT")

    def test_diferentes_valores_contrato(self):
        """Test con multiples valores de contrato"""
        db_manager, _ = asyncio.run(inicializar_database_manager())

        valores_prueba = [
            (3000000, "~60 UVT"),
            (5000000000, "~100k UVT"),
            (10000000000, "~200k UVT")
        ]

        for valor, descripcion in valores_prueba:
            resultado = obtener_tarifa_estampilla_universidad(valor, db_manager)

            assert resultado['tarifa'] > 0
            print(f"{descripcion}: ${valor:,.0f} → Tarifa: {resultado['tarifa']*100:.2f}%")

    def test_cache_funciona_con_bd_real(self):
        """Test que cache funciona correctamente con BD real"""
        db_manager, _ = asyncio.run(inicializar_database_manager())

        # Primera llamada (debe consultar BD) - valor en primer rango
        resultado1 = obtener_tarifa_estampilla_universidad(120000000, db_manager)

        # Segunda llamada (debe usar cache) - valor en primer rango
        resultado2 = obtener_tarifa_estampilla_universidad(200000000, db_manager)

        # Ambas deben retornar datos validos
        assert resultado1['fuente'] == 'database'
        assert resultado2['fuente'] == 'database'


@pytest.mark.integration
class TestFlujosIntegrados:
    """Tests de flujos completos usando mocks (no requieren API real)"""

    def test_flujo_liquidador_estampilla_con_bd(self):
        """Test integracion liquidador + config + database"""
        from Liquidador.liquidador_estampilla import LiquidadorEstampilla

        # Mock de DatabaseManager
        mock_db = Mock()
        mock_db.obtener_rangos_estampilla_universidad.return_value = {
            'success': True,
            'data': [
                {'id': 1, 'desde_uvt': 26.0, 'hasta_uvt': 52652.0, 'tarifa': 0.005}
            ]
        }

        # Crear liquidador con database_manager inyectado
        liquidador = LiquidadorEstampilla(database_manager=mock_db)

        # Ejecutar calculo (valor contrato ~2,500 UVT, bien por encima del minimo de 26)
        resultado = liquidador.calcular_estampilla(
            valor_contrato_pesos=120000000,
            valor_factura_sin_iva=800000
        )

        assert resultado['valor_estampilla'] > 0
        assert resultado['tarifa_aplicada'] == 0.005
        assert mock_db.obtener_rangos_estampilla_universidad.called

    def test_flujo_liquidador_error_bd(self):
        """Test que liquidador maneja errores de BD correctamente"""
        from Liquidador.liquidador_estampilla import LiquidadorEstampilla

        # Mock de DatabaseManager que falla
        mock_db = Mock()
        mock_db.obtener_rangos_estampilla_universidad.return_value = {
            'success': False,
            'data': None,
            'message': 'Error de conexion'
        }

        # Crear liquidador
        liquidador = LiquidadorEstampilla(database_manager=mock_db)

        # Ejecutar calculo (debe retornar error)
        resultado = liquidador.calcular_estampilla(
            valor_contrato_pesos=1000000,
            valor_factura_sin_iva=800000
        )

        assert 'error' in resultado
        assert resultado['error'] is True

    def test_flujo_config_sin_database_manager(self):
        """Test que config lanza ValueError sin database_manager"""
        with pytest.raises(ValueError, match="database_manager es requerido"):
            obtener_tarifa_estampilla_universidad(1000000, database_manager=None)

    def test_flujo_completo_con_cache(self):
        """Test flujo completo con cache"""
        mock_db = Mock()
        mock_db.obtener_rangos_estampilla_universidad.return_value = {
            'success': True,
            'data': [
                {'id': 1, 'desde_uvt': 26.0, 'hasta_uvt': 52652.0, 'tarifa': 0.005},
                {'id': 2, 'desde_uvt': 52652.0, 'hasta_uvt': 157904.0, 'tarifa': 0.01},
                {'id': 3, 'desde_uvt': 157904.0, 'hasta_uvt': float('inf'), 'tarifa': 0.02}
            ]
        }

        # Primera llamada - valor en primer rango (~2,500 UVT)
        resultado1 = obtener_tarifa_estampilla_universidad(120000000, mock_db)
        assert resultado1['tarifa'] == 0.005

        # Segunda llamada con valor diferente (usa cache) - valor en segundo rango
        resultado2 = obtener_tarifa_estampilla_universidad(5000000000, mock_db)
        assert resultado2['tarifa'] == 0.01

        # Solo debe haber consultado BD una vez
        assert mock_db.obtener_rangos_estampilla_universidad.call_count == 1

    def test_flujo_consorcio_con_bd(self):
        """Test calculo de estampilla para consorcio con BD"""
        from Liquidador.liquidador_estampilla import LiquidadorEstampilla

        mock_db = Mock()
        mock_db.obtener_rangos_estampilla_universidad.return_value = {
            'success': True,
            'data': [
                {'id': 1, 'desde_uvt': 26.0, 'hasta_uvt': 52652.0, 'tarifa': 0.005}
            ]
        }

        liquidador = LiquidadorEstampilla(database_manager=mock_db)

        consorciados = [
            {"nombre": "Empresa A", "participacion_porcentaje": 60},
            {"nombre": "Empresa B", "participacion_porcentaje": 40}
        ]

        # Valor contrato ~2,500 UVT, bien por encima del minimo de 26
        resultados = liquidador.calcular_estampilla_consorcio(
            valor_contrato_pesos=120000000,
            valor_factura_sin_iva=800000,
            consorciados=consorciados
        )

        assert len(resultados) == 2
        assert resultados[0]['valor_estampilla'] > 0
        assert resultados[1]['valor_estampilla'] > 0
        assert mock_db.obtener_rangos_estampilla_universidad.called


@pytest.mark.integration
@pytest.mark.skipif(
    not tiene_conexion_nexura(),
    reason="Sin conexion a Nexura API"
)
class TestValidacionDatosReales:
    """Tests de validacion con datos reales de Nexura"""

    def test_rangos_tienen_formato_correcto(self):
        """Test que rangos de BD tienen formato esperado"""
        db_manager, _ = asyncio.run(inicializar_database_manager())

        # Obtener rangos directamente de BD
        resultado = db_manager.obtener_rangos_estampilla_universidad()

        assert resultado['success'] is True
        assert isinstance(resultado['data'], list)
        assert len(resultado['data']) > 0

        # Verificar estructura de cada rango
        for rango in resultado['data']:
            assert 'desde_uvt' in rango
            assert 'hasta_uvt' in rango
            assert 'tarifa' in rango

            assert isinstance(rango['desde_uvt'], (int, float))
            assert isinstance(rango['hasta_uvt'], (int, float))
            assert isinstance(rango['tarifa'], float)

            # Tarifas deben estar en formato decimal (0.005, 0.01, 0.02)
            assert 0 < rango['tarifa'] < 1

    def test_rangos_ordenados_correctamente(self):
        """Test que rangos estan ordenados por desde_uvt"""
        db_manager, _ = asyncio.run(inicializar_database_manager())

        resultado = db_manager.obtener_rangos_estampilla_universidad()
        rangos = resultado['data']

        # Verificar orden ascendente
        for i in range(len(rangos) - 1):
            assert rangos[i]['desde_uvt'] <= rangos[i+1]['desde_uvt']

    def test_no_hay_gaps_entre_rangos(self):
        """Test que no hay gaps entre rangos consecutivos"""
        db_manager, _ = asyncio.run(inicializar_database_manager())

        resultado = db_manager.obtener_rangos_estampilla_universidad()
        rangos = resultado['data']

        # Verificar continuidad (con tolerancia para redondeo)
        for i in range(len(rangos) - 1):
            if rangos[i]['hasta_uvt'] != float('inf'):
                diferencia = abs(rangos[i]['hasta_uvt'] - rangos[i+1]['desde_uvt'])
                assert diferencia < 1.0  # Tolerancia de 1 UVT


if __name__ == "__main__":
    # Ejecutar tests de integracion manualmente
    print("Ejecutando tests de integracion...")

    if tiene_conexion_nexura():
        print("Credenciales Nexura disponibles - ejecutando tests completos")
        pytest.main([__file__, "-v", "-m", "integration"])
    else:
        print("Credenciales Nexura no disponibles - solo tests con mocks")
        pytest.main([__file__, "-v", "-m", "integration", "-k", "TestFlujosIntegrados"])
