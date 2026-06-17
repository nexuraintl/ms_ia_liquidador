"""
Tests para obtener_datos_rubro_tasa_prodeporte en database.py

Cobertura:
- NexuraAPIDatabase: parsing de porcentajes, manejo de errores
- SupabaseDatabase: metodo no implementado
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import requests
import json
from pathlib import Path

# Importar clases a testear
from database.database import NexuraAPIDatabase, SupabaseDatabase


# ===============================
# FIXTURES
# ===============================

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
def db_supabase():
    """Instancia de SupabaseDatabase (sin usar para estos tests)"""
    # Nota: Estos tests solo verifican el metodo, no requieren cliente real
    with patch('database.database.create_client'):
        db = SupabaseDatabase(
            supabase_url="https://mock.supabase.co",
            supabase_key="mock_key"
        )
        return db


@pytest.fixture
def fixture_respuesta_exitosa():
    """Carga fixture de respuesta exitosa de Nexura"""
    fixture_path = Path(__file__).parent / 'fixtures' / 'respuesta_nexura_tasa_prodeporte.json'
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture
def fixture_respuesta_404():
    """Carga fixture de respuesta 404 de Nexura"""
    fixture_path = Path(__file__).parent / 'fixtures' / 'respuesta_nexura_404.json'
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ===============================
# TESTS - NexuraAPIDatabase
# ===============================

class TestNexuraAPIDatabaseTasaProdeporte:
    """Tests para obtener_datos_rubro_tasa_prodeporte en Nexura"""

    def test_obtener_rubro_exitoso_parsing_correcto(self, db_nexura, fixture_respuesta_exitosa):
        """Test parsing correcto de 'Si aplica 1,5%' -> 0.015"""
        with patch.object(db_nexura, '_hacer_request', return_value=fixture_respuesta_exitosa):
            resultado = db_nexura.obtener_datos_rubro_tasa_prodeporte("280101010210")

            assert resultado['success'] is True
            assert resultado['data'] is not None
            assert resultado['data']['tarifa'] == 0.015  # 1.5% -> 0.015
            assert resultado['data']['centro_costo'] == 11783
            assert resultado['data']['municipio_departamento'] == "El jardin"
            assert '280101010210' in resultado['message']

    def test_obtener_rubro_404_no_encontrado(self, db_nexura, fixture_respuesta_404):
        """Test respuesta 404 cuando rubro no existe"""
        with patch.object(db_nexura, '_hacer_request', return_value=fixture_respuesta_404):
            resultado = db_nexura.obtener_datos_rubro_tasa_prodeporte("999999999999")

            assert resultado['success'] is False
            assert resultado['data'] is None
            assert 'no esta almacenado' in resultado['message']
            assert '999999999999' in resultado['message']

    def test_obtener_rubro_timeout(self, db_nexura):
        """Test manejo de timeout en request"""
        with patch.object(db_nexura, '_hacer_request', side_effect=requests.exceptions.Timeout):
            resultado = db_nexura.obtener_datos_rubro_tasa_prodeporte("280101010210")

            assert resultado['success'] is False
            assert resultado['error'] == 'Timeout'
            assert 'Timeout' in resultado['message']

    def test_obtener_rubro_http_error_500(self, db_nexura):
        """Test error HTTP 500 del servidor"""
        with patch.object(db_nexura, '_hacer_request', side_effect=requests.exceptions.HTTPError("500 Server Error")):
            resultado = db_nexura.obtener_datos_rubro_tasa_prodeporte("280101010210")

            assert resultado['success'] is False
            assert 'Error HTTP' in resultado['message']

    def test_parsear_porcentaje_formato_estandar(self, db_nexura):
        """Test casos estandar: 'Si aplica 1,5%', 'Si aplica 2,5%'"""
        assert db_nexura._parsear_porcentaje_prodeporte("Si aplica 1,5%") == 0.015
        assert db_nexura._parsear_porcentaje_prodeporte("Si aplica 2,5%") == 0.025
        assert db_nexura._parsear_porcentaje_prodeporte("Si aplica 0,5%") == 0.005

    def test_parsear_porcentaje_variaciones(self, db_nexura):
        """Test variaciones de formato: '1.5%', '2,5 %', etc."""
        assert db_nexura._parsear_porcentaje_prodeporte("1.5%") == 0.015
        assert db_nexura._parsear_porcentaje_prodeporte("2,5 %") == 0.025
        assert db_nexura._parsear_porcentaje_prodeporte("1,5") == 0.015

    def test_parsear_porcentaje_no_aplica(self, db_nexura):
        """Test 'No aplica' -> None"""
        assert db_nexura._parsear_porcentaje_prodeporte("No aplica") is None
        assert db_nexura._parsear_porcentaje_prodeporte("no aplica") is None

    def test_parsear_porcentaje_formato_invalido(self, db_nexura):
        """Test formatos invalidos: '', 'abc', None"""
        assert db_nexura._parsear_porcentaje_prodeporte("") is None
        assert db_nexura._parsear_porcentaje_prodeporte("abc") is None
        assert db_nexura._parsear_porcentaje_prodeporte("texto sin numeros") is None

    def test_obtener_rubro_campo_centro_costos_invalido(self, db_nexura):
        """Test CENTRO_COSTOS no numerico -> fallback a 0"""
        respuesta_mock = {
            "error": {"code": 0, "message": "success"},
            "data": [{
                "RUBRO_PRESUPUESTO": "280101010210",
                "CENTRO_COSTOS": "abc",  # No numerico
                "PORCENTAJE_PRODEPORTE": "Si aplica 1,5%",
                "MUNICIPIO": "Test"
            }]
        }

        with patch.object(db_nexura, '_hacer_request', return_value=respuesta_mock):
            resultado = db_nexura.obtener_datos_rubro_tasa_prodeporte("280101010210")

            assert resultado['success'] is True
            assert resultado['data']['centro_costo'] == 0  # Fallback

    def test_parsear_porcentaje_con_comas_europeas(self, db_nexura):
        """Test formato europeo: '1,5' -> 0.015"""
        assert db_nexura._parsear_porcentaje_prodeporte("1,5") == 0.015
        assert db_nexura._parsear_porcentaje_prodeporte("2,0") == 0.020

    def test_obtener_rubro_data_array_vacio(self, db_nexura):
        """Test data=[] -> success=False"""
        respuesta_mock = {
            "error": {"code": 0, "message": "success"},
            "data": []  # Array vacio
        }

        with patch.object(db_nexura, '_hacer_request', return_value=respuesta_mock):
            resultado = db_nexura.obtener_datos_rubro_tasa_prodeporte("280101010210")

            assert resultado['success'] is False
            assert 'no esta almacenado' in resultado['message']


# ===============================
# TESTS - SupabaseDatabase
# ===============================

class TestSupabaseDatabaseTasaProdeporte:
    """Tests para SupabaseDatabase (no implementado)"""

    def test_obtener_datos_rubro_no_implementado_supabase(self, db_supabase):
        """Test Supabase retorna error 'no implementado'"""
        resultado = db_supabase.obtener_datos_rubro_tasa_prodeporte("280101010210")

        assert resultado['success'] is False
        assert (
            'no disponible' in resultado['message'].lower()
            or 'no implementada' in resultado['message'].lower()
            or 'error consultando' in resultado['message'].lower()
        )
        assert resultado['data'] is None
