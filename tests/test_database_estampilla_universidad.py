"""
Tests unitarios para obtener_rangos_estampilla_universidad en database layer.

Sigue patron establecido en test_database_tasa_prodeporte.py
"""

import pytest
from unittest.mock import Mock, patch
import requests
from pathlib import Path
import json
from database.database import NexuraAPIDatabase, SupabaseDatabase
from database.auth_provider import NoAuthProvider
import config


@pytest.fixture
def mock_auth_provider():
    """Mock del auth provider para NexuraAPIDatabase"""
    mock_auth = Mock()
    mock_auth.get_headers.return_value = {'Authorization': 'Bearer mock_token'}
    mock_auth.is_authenticated.return_value = True
    mock_auth.refresh_if_needed.return_value = None
    return mock_auth


@pytest.fixture
def db_nexura(mock_auth_provider):
    """Instancia de NexuraAPIDatabase con auth mockeado"""
    return NexuraAPIDatabase(
        base_url="https://mock-api.com",
        auth_provider=mock_auth_provider
    )


@pytest.fixture
def fixture_respuesta_exitosa():
    """Carga fixture de respuesta exitosa desde archivo JSON"""
    fixture_path = Path(__file__).parent / 'fixtures' / 'respuesta_nexura_estampilla_universidad.json'
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture
def fixture_respuesta_404():
    """Carga fixture de respuesta 404 desde archivo JSON"""
    fixture_path = Path(__file__).parent / 'fixtures' / 'respuesta_nexura_estampilla_404.json'
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def limpiar_cache_antes_de_cada_test():
    """Fixture que limpia el cache antes de cada test"""
    from config import limpiar_cache_estampilla_universidad
    limpiar_cache_estampilla_universidad()
    yield
    limpiar_cache_estampilla_universidad()


@pytest.fixture(autouse=True)
def patch_uvt_2025():
    """Patch UVT_2025 para que no sea None durante los tests."""
    with patch.object(config, 'UVT_2025', 49799):
        yield


@pytest.fixture
def mock_db_manager():
    """Mock de DatabaseManager para tests de config.py"""
    mock_db = Mock()
    mock_db.obtener_rangos_estampilla_universidad.return_value = {
        'success': True,
        'data': [
            {'id': 1, 'desde_uvt': 26.0, 'hasta_uvt': 52652.0, 'tarifa': 0.005},
            {'id': 2, 'desde_uvt': 52652.0, 'hasta_uvt': 157904.0, 'tarifa': 0.01},
            {'id': 3, 'desde_uvt': 157904.0, 'hasta_uvt': float('inf'), 'tarifa': 0.02}
        ]
    }
    return mock_db


class TestNexuraAPIDatabaseEstampillaUniversidad:
    """Tests para obtener_rangos_estampilla_universidad en Nexura"""

    def test_obtener_rangos_exitoso_parsing_correcto(self, db_nexura, fixture_respuesta_exitosa):
        """Test parsing correcto: '0.5000' → 0.005, '52.626' → 52626.0"""
        with patch.object(db_nexura, '_hacer_request', return_value=fixture_respuesta_exitosa):
            resultado = db_nexura.obtener_rangos_estampilla_universidad()

            assert resultado['success'] is True
            assert resultado['data'] is not None
            assert len(resultado['data']) > 0

            # Verificar consolidacion de rangos (debe unir id 1 y 2)
            primer_rango = resultado['data'][0]
            assert primer_rango['desde_uvt'] == 26.0
            assert primer_rango['hasta_uvt'] == 52652.0  # Consolidado de "52.626" y "52.652"
            assert primer_rango['tarifa'] == 0.005  # 0.5% → 0.005

            # Verificar que hay rangos consolidados
            assert isinstance(resultado['data'], list)

    def test_obtener_rangos_estructura_respuesta(self, db_nexura, fixture_respuesta_exitosa):
        """Test que la estructura de respuesta es correcta"""
        with patch.object(db_nexura, '_hacer_request', return_value=fixture_respuesta_exitosa):
            resultado = db_nexura.obtener_rangos_estampilla_universidad()

            assert 'success' in resultado
            assert 'data' in resultado
            assert 'message' in resultado

            # Verificar estructura de cada rango
            for rango in resultado['data']:
                assert 'id' in rango
                assert 'desde_uvt' in rango
                assert 'hasta_uvt' in rango
                assert 'tarifa' in rango

    def test_parsear_uvt_casos_especiales(self, db_nexura):
        """Test parsing de UVT con diferentes formatos (punto = separador de miles)"""
        assert db_nexura._parsear_uvt("26") == 26.0
        assert db_nexura._parsear_uvt("52.626") == 52626.0  # Punto como separador de miles
        assert db_nexura._parsear_uvt("> 52.626") == 52626.0
        assert db_nexura._parsear_uvt("<= 52.652") == 52652.0
        assert db_nexura._parsear_uvt("157.904") == 157904.0
        assert db_nexura._parsear_uvt("") == float('inf')
        assert db_nexura._parsear_uvt("   ") == float('inf')

    def test_parsear_uvt_valores_invalidos(self, db_nexura):
        """Test parsing de UVT con valores invalidos"""
        assert db_nexura._parsear_uvt("abc") == 0.0
        assert db_nexura._parsear_uvt("---") == 0.0

    def test_consolidar_rangos_duplicados(self, db_nexura):
        """Test consolidacion de rangos con notaciones diferentes (valores enteros)"""
        rangos = [
            {'id': 1, 'desde_uvt': 26.0, 'hasta_uvt': 52626.0, 'tarifa': 0.005},
            {'id': 2, 'desde_uvt': 52626.0, 'hasta_uvt': 52652.0, 'tarifa': 0.005}
        ]

        consolidados = db_nexura._consolidar_rangos_estampilla(rangos)

        assert len(consolidados) == 1
        assert consolidados[0]['desde_uvt'] == 26.0
        assert consolidados[0]['hasta_uvt'] == 52652.0
        assert consolidados[0]['tarifa'] == 0.005

    def test_consolidar_rangos_diferentes(self, db_nexura):
        """Test consolidacion NO une rangos con tarifas diferentes"""
        rangos = [
            {'id': 1, 'desde_uvt': 26.0, 'hasta_uvt': 52652.0, 'tarifa': 0.005},
            {'id': 2, 'desde_uvt': 52652.0, 'hasta_uvt': 157904.0, 'tarifa': 0.01}
        ]

        consolidados = db_nexura._consolidar_rangos_estampilla(rangos)

        # No deben consolidarse porque tienen tarifas diferentes
        assert len(consolidados) == 2

    def test_consolidar_rangos_vacio(self, db_nexura):
        """Test consolidacion con lista vacia"""
        consolidados = db_nexura._consolidar_rangos_estampilla([])
        assert consolidados == []

    def test_obtener_rangos_404_no_encontrado(self, db_nexura, fixture_respuesta_404):
        """Test respuesta 404 cuando no hay configuracion"""
        with patch.object(db_nexura, '_hacer_request', return_value=fixture_respuesta_404):
            resultado = db_nexura.obtener_rangos_estampilla_universidad()

            assert resultado['success'] is False
            assert resultado['data'] is None
            assert 'no encontrada' in resultado['message'].lower()

    def test_obtener_rangos_timeout(self, db_nexura):
        """Test manejo de timeout en request"""
        with patch.object(db_nexura, '_hacer_request', side_effect=requests.exceptions.Timeout):
            resultado = db_nexura.obtener_rangos_estampilla_universidad()

            assert resultado['success'] is False
            assert resultado['error'] == 'Timeout'
            assert 'timeout' in resultado['message'].lower()

    def test_obtener_rangos_error_http_500(self, db_nexura):
        """Test manejo de error HTTP 500"""
        mock_response = Mock()
        mock_response.status_code = 500
        error = requests.exceptions.HTTPError(response=mock_response)

        with patch.object(db_nexura, '_hacer_request', side_effect=error):
            resultado = db_nexura.obtener_rangos_estampilla_universidad()

            assert resultado['success'] is False

    def test_obtener_rangos_data_array_vacio(self, db_nexura):
        """Test cuando API retorna data array vacio"""
        respuesta_vacia = {
            "error": {"code": 0, "message": "success"},
            "data": []
        }

        with patch.object(db_nexura, '_hacer_request', return_value=respuesta_vacia):
            resultado = db_nexura.obtener_rangos_estampilla_universidad()

            assert resultado['success'] is False
            assert 'no encontrada' in resultado['message'].lower()


class TestSupabaseDatabaseEstampillaUniversidad:
    """Tests para stub de Supabase"""

    @patch('database.database.create_client')
    def test_obtener_rangos_no_implementado(self, mock_create_client):
        """Test que Supabase retorna error descriptivo"""
        mock_client = Mock()
        mock_create_client.return_value = mock_client

        db = SupabaseDatabase(
            supabase_url="https://test.supabase.co",
            supabase_key="test_key"
        )

        resultado = db.obtener_rangos_estampilla_universidad()

        assert resultado['success'] is False
        assert resultado['data'] is None
        assert 'timeouts' in resultado['message'].lower()


class TestConfigObtenerTarifaEstampillaUniversidad:
    """Tests para config.obtener_tarifa_estampilla_universidad"""

    def test_requiere_database_manager(self):
        """Test que lanza ValueError si database_manager es None"""
        from config import obtener_tarifa_estampilla_universidad

        with pytest.raises(ValueError, match="database_manager es requerido"):
            obtener_tarifa_estampilla_universidad(1000000, database_manager=None)

    def test_valor_menor_a_26_uvt_no_aplica(self, mock_db_manager):
        """Test que valores menores a 26 UVT lanzan excepción NO_APLICA"""
        from config import obtener_tarifa_estampilla_universidad

        # Test: valor muy bajo (~21 UVT, menor al mínimo de 26)
        valor_muy_bajo = 1000000

        with pytest.raises(ValueError, match="NO_APLICA_ESTAMPILLA_UNIVERSIDAD"):
            obtener_tarifa_estampilla_universidad(valor_muy_bajo, mock_db_manager)

    def test_busca_rango_correcto_valor_en_primer_rango(self, mock_db_manager):
        """Test que encuentra el rango correcto para valor en primer rango (26-52652 UVT)"""
        from config import obtener_tarifa_estampilla_universidad

        # Test: valor en primer rango (~2,500 UVT)
        valor_primer_rango = 120000000  # ~2,548 UVT
        resultado = obtener_tarifa_estampilla_universidad(valor_primer_rango, mock_db_manager)

        assert resultado['tarifa'] == 0.005
        assert resultado['fuente'] == 'database'
        assert 'valor_contrato_uvt' in resultado
        assert 'uvt_2025' in resultado

    def test_busca_rango_correcto_valor_medio(self, mock_db_manager):
        """Test que encuentra el rango correcto para valor medio (52652-157904 UVT)"""
        from config import obtener_tarifa_estampilla_universidad

        # Test: valor medio (~100k UVT)
        valor_medio = 5000000000
        resultado = obtener_tarifa_estampilla_universidad(valor_medio, mock_db_manager)

        assert resultado['tarifa'] == 0.01

    def test_busca_rango_correcto_valor_alto(self, mock_db_manager):
        """Test que encuentra el rango correcto para valor alto (>157904 UVT)"""
        from config import obtener_tarifa_estampilla_universidad

        # Test: valor alto (~200k UVT)
        valor_alto = 10000000000
        resultado = obtener_tarifa_estampilla_universidad(valor_alto, mock_db_manager)

        assert resultado['tarifa'] == 0.02

    def test_usa_cache_en_segunda_llamada(self, mock_db_manager):
        """Test que usa cache en llamadas subsecuentes"""
        from config import obtener_tarifa_estampilla_universidad

        # Primera llamada (valor ~2,500 UVT, bien por encima del minimo de 26)
        obtener_tarifa_estampilla_universidad(120000000, mock_db_manager)
        assert mock_db_manager.obtener_rangos_estampilla_universidad.call_count == 1

        # Segunda llamada (debe usar cache)
        obtener_tarifa_estampilla_universidad(200000000, mock_db_manager)
        assert mock_db_manager.obtener_rangos_estampilla_universidad.call_count == 1  # No aumenta

    def test_limpiar_cache_funciona(self, mock_db_manager):
        """Test que limpiar cache fuerza nueva consulta"""
        from config import obtener_tarifa_estampilla_universidad, limpiar_cache_estampilla_universidad

        # Primera llamada (valor ~2,500 UVT, bien por encima del minimo de 26)
        obtener_tarifa_estampilla_universidad(120000000, mock_db_manager)

        # Limpiar cache manualmente
        limpiar_cache_estampilla_universidad()

        # Segunda llamada (debe consultar BD nuevamente)
        obtener_tarifa_estampilla_universidad(120000000, mock_db_manager)
        assert mock_db_manager.obtener_rangos_estampilla_universidad.call_count == 2

    def test_error_bd_lanza_valueerror(self, mock_db_manager):
        """Test que error en BD lanza ValueError"""
        from config import obtener_tarifa_estampilla_universidad

        # Mock error de BD
        mock_db_manager.obtener_rangos_estampilla_universidad.return_value = {
            'success': False,
            'data': None,
            'message': 'Error de conexion'
        }

        with pytest.raises(ValueError, match="No se pudo obtener rangos"):
            obtener_tarifa_estampilla_universidad(1000000, mock_db_manager)

    def test_estructura_retorno_completa(self, mock_db_manager):
        """Test que retorna todos los campos requeridos"""
        from config import obtener_tarifa_estampilla_universidad

        # Valor ~2,500 UVT, bien por encima del minimo de 26
        resultado = obtener_tarifa_estampilla_universidad(120000000, mock_db_manager)

        # Verificar campos obligatorios
        assert 'tarifa' in resultado
        assert 'rango_desde_uvt' in resultado
        assert 'rango_hasta_uvt' in resultado
        assert 'valor_contrato_uvt' in resultado
        assert 'uvt_2025' in resultado
        assert 'fuente' in resultado

        # Verificar tipos
        assert isinstance(resultado['tarifa'], float)
        assert isinstance(resultado['valor_contrato_uvt'], float)
        assert isinstance(resultado['uvt_2025'], int)
        assert resultado['fuente'] == 'database'
