"""
TESTS PARA NEXURA API DATABASE - TEST COMPLETO
==============================================

Suite de tests para validar la implementacion de NexuraAPIDatabase
y el sistema de autenticacion modular.

PRINCIPIOS SOLID APLICADOS EN TESTS:
- SRP: Cada test valida una sola funcionalidad
- DIP: Tests usan mocks para dependencias externas
- Aislamiento: Tests unitarios independientes de la API real

COBERTURA:
1. Auth Providers (NoAuth, JWT, API Key)
2. NexuraAPIDatabase - obtener_por_codigo
3. Manejo de errores HTTP
4. Mapeo de respuestas
5. Health checks
6. Integracion con API real (opcional)

Autor: Sistema Preliquidador
Version: 3.0 - Clean Architecture
"""

import pytest
import os
import sys
import requests
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Agregar path del proyecto para imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture(autouse=True)
def _desactivar_flag_retefuente_new(monkeypatch):
    """
    Aisla los tests del flag experimental USE_RETEFUENTE_NEW: este archivo
    valida exclusivamente el comportamiento del endpoint legacy
    /preliquidador/retefuente/. Si el .env local tiene el flag en true,
    sin este fixture el switch en NexuraAPIDatabase rompe los tests.
    """
    monkeypatch.setenv("USE_RETEFUENTE_NEW", "false")

from database.auth_provider import (
    IAuthProvider,
    NoAuthProvider,
    JWTAuthProvider,
    APIKeyAuthProvider,
    AuthProviderFactory
)

from database.database import NexuraAPIDatabase
from database.setup import crear_database_por_tipo


# =====================================
# FIXTURES PARA TESTS
# =====================================

@pytest.fixture
def mock_response_exitoso():
    """
    Fixture con respuesta exitosa de Nexura API

    Retorna estructura real de la API segun documentacion del usuario
    """
    return {
        "error": {
            "code": 0,
            "message": "success",
            "detail": []
        },
        "data": [
            {
                "CODIGO_DEL_NEGOCIO": 3,
                "DESCRIPCION_DEL_NEGOCIO": "FID COL. DE COMERCIO EXTERIOR S.A.",
                "NIT_ASOCIADO": "800178148",
                "NOMBRE_DEL_ASOCIADO": "ENCARGOS FIDUCIARIOS-SOCIEDAD FDX"
            }
        ]
    }


@pytest.fixture
def mock_response_no_encontrado():
    """Fixture con respuesta cuando no se encuentra el negocio"""
    return {
        "error": {
            "code": 0,
            "message": "success",
            "detail": []
        },
        "data": []
    }


@pytest.fixture
def mock_response_error():
    """Fixture con respuesta de error de la API"""
    return {
        "error": {
            "code": 500,
            "message": "Internal Server Error",
            "detail": ["Database connection failed"]
        },
        "data": []
    }


@pytest.fixture
def no_auth_provider():
    """Fixture con provider sin autenticacion"""
    return NoAuthProvider()


@pytest.fixture
def jwt_auth_provider():
    """Fixture con provider JWT"""
    return JWTAuthProvider(
        token="test_jwt_token_12345",
        token_type="Bearer"
    )


@pytest.fixture
def api_key_provider():
    """Fixture con provider API Key"""
    return APIKeyAuthProvider(
        api_key="test_api_key_12345",
        header_name="X-API-Key"
    )


# =====================================
# TESTS DE AUTH PROVIDERS
# =====================================

class TestAuthProviders:
    """Tests para proveedores de autenticacion (SRP: solo auth)"""

    def test_no_auth_provider_headers_vacios(self, no_auth_provider):
        """NoAuthProvider debe retornar headers vacios"""
        headers = no_auth_provider.get_headers()
        assert headers == {}
        assert no_auth_provider.is_authenticated() is True
        assert no_auth_provider.refresh_if_needed() is True

    def test_jwt_auth_provider_headers_correctos(self, jwt_auth_provider):
        """JWTAuthProvider debe retornar header Authorization correcto"""
        headers = jwt_auth_provider.get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_jwt_token_12345"
        assert jwt_auth_provider.is_authenticated() is True

    def test_jwt_auth_provider_token_vacio(self):
        """JWTAuthProvider con token vacio no debe estar autenticado"""
        provider = JWTAuthProvider(token="")
        assert provider.is_authenticated() is False

    def test_api_key_provider_headers_correctos(self, api_key_provider):
        """APIKeyAuthProvider debe retornar header correcto"""
        headers = api_key_provider.get_headers()
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "test_api_key_12345"
        assert api_key_provider.is_authenticated() is True

    def test_api_key_provider_custom_header(self):
        """APIKeyAuthProvider debe permitir header personalizado"""
        provider = APIKeyAuthProvider(
            api_key="mi_api_key",
            header_name="X-Custom-Auth"
        )
        headers = provider.get_headers()
        assert "X-Custom-Auth" in headers
        assert headers["X-Custom-Auth"] == "mi_api_key"

    def test_auth_factory_crea_no_auth(self):
        """Factory debe crear NoAuthProvider para tipo 'none'"""
        provider = AuthProviderFactory.create_from_config(auth_type="none")
        assert isinstance(provider, NoAuthProvider)

    def test_auth_factory_crea_jwt(self):
        """Factory debe crear JWTAuthProvider para tipo 'jwt'"""
        provider = AuthProviderFactory.create_from_config(
            auth_type="jwt",
            token="test_token"
        )
        assert isinstance(provider, JWTAuthProvider)

    def test_auth_factory_crea_api_key(self):
        """Factory debe crear APIKeyAuthProvider para tipo 'api_key'"""
        provider = AuthProviderFactory.create_from_config(
            auth_type="api_key",
            api_key="test_key"
        )
        assert isinstance(provider, APIKeyAuthProvider)

    def test_auth_factory_tipo_invalido(self):
        """Factory debe lanzar error con tipo invalido"""
        with pytest.raises(ValueError):
            AuthProviderFactory.create_from_config(auth_type="invalid_type")

    def test_jwt_token_vacio_fallback_no_auth(self):
        """Factory debe retornar NoAuthProvider si JWT token esta vacio"""
        provider = AuthProviderFactory.create_from_config(
            auth_type="jwt",
            token=""
        )
        assert isinstance(provider, NoAuthProvider)


# =====================================
# TESTS DE NEXURA API DATABASE
# =====================================

class TestNexuraAPIDatabase:
    """Tests para NexuraAPIDatabase (SRP: solo API REST)"""

    def test_inicializacion_correcta(self, no_auth_provider):
        """Database debe inicializarse correctamente"""
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider,
            timeout=30
        )
        assert db.base_url == "https://api.example.com"
        assert db.timeout == 30
        assert db.auth_provider is not None

    def test_base_url_sin_trailing_slash(self, no_auth_provider):
        """Database debe remover trailing slash de base_url"""
        db = NexuraAPIDatabase(
            base_url="https://api.example.com/",
            auth_provider=no_auth_provider
        )
        assert db.base_url == "https://api.example.com"

    @patch('database.database.requests.Session.request')
    def test_obtener_por_codigo_exitoso(
        self,
        mock_request,
        no_auth_provider,
        mock_response_exitoso
    ):
        """obtener_por_codigo debe retornar datos correctamente"""
        # Configurar mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_exitoso
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.obtener_por_codigo("3")

        # Validar resultado
        assert resultado['success'] is True
        assert resultado['data'] is not None
        assert resultado['data']['codigo'] == 3
        assert resultado['data']['negocio'] == "FID COL. DE COMERCIO EXTERIOR S.A."
        assert resultado['data']['nit'] == "800178148"
        assert resultado['data']['nombre_fiduciario'] == "ENCARGOS FIDUCIARIOS-SOCIEDAD FDX"
        assert 'message' in resultado

    @patch('database.database.requests.Session.request')
    def test_obtener_por_codigo_no_encontrado(
        self,
        mock_request,
        no_auth_provider,
        mock_response_no_encontrado
    ):
        """obtener_por_codigo debe manejar codigo no encontrado"""
        # Configurar mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_no_encontrado
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.obtener_por_codigo("99999")

        # Validar resultado
        assert resultado['success'] is False
        assert resultado['data'] is None
        assert 'No existe negocio' in resultado['message']

    @patch('database.database.requests.Session.request')
    def test_obtener_por_codigo_error_api(
        self,
        mock_request,
        no_auth_provider,
        mock_response_error
    ):
        """obtener_por_codigo debe manejar errores de la API"""
        # Configurar mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_error
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.obtener_por_codigo("3")

        # Validar resultado
        assert resultado['success'] is False
        assert resultado['data'] is None
        assert 'Error en API' in resultado['message']

    @patch('database.database.requests.Session.request')
    def test_obtener_por_codigo_timeout(self, mock_request, no_auth_provider):
        """obtener_por_codigo debe manejar timeout"""
        # Configurar mock para lanzar timeout
        import requests
        mock_request.side_effect = requests.exceptions.Timeout("Connection timeout")

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.obtener_por_codigo("3")

        # Validar resultado
        assert resultado['success'] is False
        assert resultado['error'] == 'Timeout'
        assert 'Timeout' in resultado['message']

    @patch('database.database.requests.Session.request')
    def test_obtener_por_codigo_http_error(self, mock_request, no_auth_provider):
        """obtener_por_codigo debe manejar errores HTTP"""
        # Configurar mock para lanzar HTTPError
        import requests
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_request.return_value = mock_response

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.obtener_por_codigo("3")

        # Validar resultado
        assert resultado['success'] is False
        assert 'Error HTTP' in resultado['message']

    def test_mapear_respuesta_negocio_correcta(self, no_auth_provider):
        """Mapeo de respuesta debe transformar correctamente"""
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )

        data_nexura = [
            {
                "CODIGO_DEL_NEGOCIO": 42,
                "DESCRIPCION_DEL_NEGOCIO": "Test Negocio",
                "NIT_ASOCIADO": "123456789",
                "NOMBRE_DEL_ASOCIADO": "Test Asociado"
            }
        ]

        resultado = db._mapear_respuesta_negocio(data_nexura)

        assert resultado is not None
        assert resultado['codigo'] == 42
        assert resultado['negocio'] == "Test Negocio"
        assert resultado['nit'] == "123456789"
        assert resultado['nombre_fiduciario'] == "Test Asociado"

    def test_mapear_respuesta_negocio_vacia(self, no_auth_provider):
        """Mapeo debe retornar None si array vacio"""
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )

        resultado = db._mapear_respuesta_negocio([])
        assert resultado is None

    @patch('database.database.requests.Session.request')
    def test_health_check_exitoso(self, mock_request, no_auth_provider):
        """health_check debe retornar True si API responde"""
        # Configurar mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error": {"code": 0, "message": "success"},
            "data": []
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.health_check()

        assert resultado is True

    @patch('database.database.requests.Session.request')
    def test_health_check_fallido(self, mock_request, no_auth_provider):
        """health_check debe retornar False si API falla"""
        # Configurar mock para lanzar excepcion
        import requests
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection failed")

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.health_check()

        assert resultado is False

    def test_close_cierra_session(self, no_auth_provider):
        """close debe cerrar la session HTTP"""
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )

        # Mock del metodo close de session
        db.session.close = Mock()

        # Ejecutar
        db.close()

        # Validar que se llamo close
        db.session.close.assert_called_once()


# =====================================
# TESTS DE INTEGRACION CON API REAL
# =====================================

class TestIntegracionNexuraAPIReal:
    """
    Tests de integracion con API real de Nexura (OPCIONAL)

    Estos tests hacen requests reales a la API. Solo ejecutar si:
    1. Variables de entorno estan configuradas
    2. Se quiere validar conectividad real
    3. Se esta en ambiente de desarrollo/testing

    Para ejecutar solo estos tests:
        pytest tests/test_nexura_database.py::TestIntegracionNexuraAPIReal -v
    """

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="NEXURA_API_BASE_URL no configurada"
    )
    def test_integracion_obtener_por_codigo_real(self):
        """
        Test de integracion con API real

        IMPORTANTE: Solo ejecutar si API esta disponible
        """
        # Crear auth provider desde config
        auth_type = os.getenv("NEXURA_AUTH_TYPE", "none")
        auth_provider = AuthProviderFactory.create_from_config(
            auth_type=auth_type,
            token=os.getenv("NEXURA_JWT_TOKEN", ""),
            api_key=os.getenv("NEXURA_API_KEY", "")
        )

        # Crear database
        db = NexuraAPIDatabase(
            base_url=os.getenv("NEXURA_API_BASE_URL"),
            auth_provider=auth_provider,
            timeout=30
        )

        # Probar health check
        assert db.health_check() is True, "API no responde correctamente"

        # Probar obtener_por_codigo con codigo de prueba
        # Usar codigo que sabemos que existe segun Postman: codigo=32
        resultado = db.obtener_por_codigo("32")

        # Validar estructura de respuesta
        assert 'success' in resultado
        assert 'data' in resultado
        assert 'message' in resultado

        # Si fue exitoso, validar estructura de datos
        if resultado['success']:
            assert resultado['data'] is not None
            assert 'codigo' in resultado['data']
            assert 'negocio' in resultado['data']
            assert 'nit' in resultado['data']
            assert 'nombre_fiduciario' in resultado['data']

            print(f"\nDatos obtenidos de API real:")
            print(f"  Codigo: {resultado['data']['codigo']}")
            print(f"  Negocio: {resultado['data']['negocio']}")
            print(f"  NIT: {resultado['data']['nit']}")

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="NEXURA_API_BASE_URL no configurada"
    )
    def test_integracion_codigo_no_existente(self):
        """Test con codigo que no existe en la API real"""
        # Crear database usando factory
        db_implementation = crear_database_por_tipo("nexura")

        if db_implementation:
            # Probar con codigo que probablemente no existe
            resultado = db_implementation.obtener_por_codigo("999999")

            # Debe retornar success=False
            assert resultado['success'] is False
            assert resultado['data'] is None


# =====================================
# TESTS DE FACTORY DE SETUP
# =====================================

class TestFactorySetup:
    """Tests para factory de database en setup.py"""

    @patch.dict(os.environ, {
        "NEXURA_API_BASE_URL": "https://api.test.com",
        "NEXURA_AUTH_TYPE": "none"
    })
    def test_crear_database_por_tipo_nexura(self):
        """Factory debe crear NexuraAPIDatabase correctamente"""
        db = crear_database_por_tipo("nexura")

        assert db is not None
        assert isinstance(db, NexuraAPIDatabase)
        assert db.base_url == "https://api.test.com"

    @patch.dict(os.environ, {
        "SUPABASE_URL": "https://supabase.test.com",
        "SUPABASE_KEY": "test_key_12345"
    })
    @patch('database.database.create_client')
    def test_crear_database_por_tipo_supabase(self, mock_create_client):
        """Factory debe crear SupabaseDatabase correctamente"""
        from database.database import SupabaseDatabase
        from unittest.mock import MagicMock
        mock_create_client.return_value = MagicMock()

        db = crear_database_por_tipo("supabase")

        assert db is not None
        assert isinstance(db, SupabaseDatabase)

    def test_crear_database_tipo_invalido(self):
        """Factory debe retornar None con tipo invalido"""
        db = crear_database_por_tipo("tipo_invalido")
        assert db is None

    @patch.dict(os.environ, {}, clear=True)
    def test_crear_database_sin_config(self):
        """Factory debe retornar None si falta configuracion"""
        db = crear_database_por_tipo("nexura")
        assert db is None


# =====================================
# TESTS: obtener_conceptos_retefuente
# =====================================

class TestObtenerConceptosRetefuente:
    """Tests para obtener_conceptos_retefuente - Migracion v3.3.0"""

    @patch('database.database.requests.Session')
    def test_obtener_conceptos_estructura_18_exitoso(self, mock_session_class):
        """Debe retornar conceptos para estructura contable 18"""
        # Mock de respuesta exitosa con multiples conceptos
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {'code': 0, 'message': 'success'},
            'data': [
                {
                    'id': 1,
                    'estructura_contable': 18,
                    'codigo_concepto': 'CO1',
                    'descripcion_concepto': 'GASTOS REEMBOLSABLES 11%',
                    'porcentaje': 11
                },
                {
                    'id': 2,
                    'estructura_contable': 18,
                    'codigo_concepto': 'AF6',
                    'descripcion_concepto': 'INTERVENTORIA 6%',
                    'porcentaje': 6
                }
            ]
        }

        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_conceptos_retefuente(estructura_contable=18)

        assert resultado['success'] is True
        assert 'data' in resultado
        assert len(resultado['data']) == 2
        assert resultado['total'] == 2

        # Validar mapeo correcto
        primer_concepto = resultado['data'][0]
        assert primer_concepto['descripcion_concepto'] == 'GASTOS REEMBOLSABLES 11%'
        assert primer_concepto['index'] == 1

        segundo_concepto = resultado['data'][1]
        assert segundo_concepto['descripcion_concepto'] == 'INTERVENTORIA 6%'
        assert segundo_concepto['index'] == 2

    @patch('database.database.requests.Session')
    def test_obtener_conceptos_estructura_no_existe_404(self, mock_session_class):
        """Debe manejar estructura contable inexistente (404)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {
                'code': 404,
                'message': 'No se encontraron datos con los criterios proporcionados.'
            },
            'data': []
        }

        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_conceptos_retefuente(estructura_contable=999)

        assert resultado['success'] is False
        assert resultado['data'] == []
        assert resultado['total'] == 0
        assert 'No se encontraron conceptos' in resultado['message']

    @patch('database.database.requests.Session')
    def test_obtener_conceptos_data_vacio(self, mock_session_class):
        """Debe manejar respuesta exitosa pero con data vacio"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {'code': 0, 'message': 'success'},
            'data': []
        }

        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_conceptos_retefuente(estructura_contable=18)

        assert resultado['success'] is False
        assert resultado['data'] == []
        assert resultado['total'] == 0

    @patch('database.database.requests.Session')
    def test_obtener_conceptos_estructura_17_exitoso(self, mock_session_class):
        """Debe retornar conceptos para estructura contable 17"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {'code': 0, 'message': 'success'},
            'data': [
                {
                    'id': 194,
                    'estructura_contable': 17,
                    'codigo_concepto': 'P20',
                    'descripcion_concepto': 'PAGO EXT 20%-OTRAS ASESORIAS',
                    'porcentaje': 20
                }
            ]
        }

        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_conceptos_retefuente(estructura_contable=17)

        assert resultado['success'] is True
        assert len(resultado['data']) == 1
        assert resultado['data'][0]['index'] == 194

    @patch('database.database.requests.Session')
    def test_obtener_conceptos_timeout(self, mock_session_class):
        """Debe manejar timeout correctamente"""
        mock_session = Mock()
        mock_session.request.side_effect = requests.exceptions.Timeout("Connection timed out")
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_conceptos_retefuente(estructura_contable=18)

        assert resultado['success'] is False
        assert 'Timeout' in resultado['message']

    @patch('database.database.requests.Session')
    def test_obtener_conceptos_error_red(self, mock_session_class):
        """Debe manejar errores de red"""
        mock_session = Mock()
        mock_session.request.side_effect = requests.exceptions.RequestException("Network error")
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_conceptos_retefuente(estructura_contable=18)

        assert resultado['success'] is False
        assert 'Error de red' in resultado['message']


# =====================================
# TESTS DE INTEGRACION: obtener_conceptos_retefuente
# =====================================

class TestObtenerConceptosRetefuenteIntegracion:
    """Tests de integracion con API real"""

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="Requiere NEXURA_API_BASE_URL configurado en .env"
    )
    def test_integracion_obtener_conceptos_estructura_18(self):
        """Test de integracion real - estructura contable 18"""
        base_url = os.getenv("NEXURA_API_BASE_URL")

        db = NexuraAPIDatabase(
            base_url=base_url,
            auth_provider=NoAuthProvider(),
            timeout=30
        )

        resultado = db.obtener_conceptos_retefuente(estructura_contable=18)

        print(f"\nResultado API real estructura 18:")
        print(f"  Success: {resultado['success']}")
        print(f"  Total: {resultado.get('total', 0)}")
        print(f"  Message: {resultado['message']}")

        if resultado['success']:
            print(f"  Primeros 3 conceptos:")
            for concepto in resultado['data'][:3]:
                print(f"    - [{concepto['index']}] {concepto['descripcion_concepto']}")

        assert resultado['success'] is True
        assert 'data' in resultado
        assert len(resultado['data']) > 0

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="Requiere NEXURA_API_BASE_URL configurado en .env"
    )
    def test_integracion_obtener_conceptos_estructura_no_existe(self):
        """Test de integracion real - estructura inexistente"""
        base_url = os.getenv("NEXURA_API_BASE_URL")

        db = NexuraAPIDatabase(
            base_url=base_url,
            auth_provider=NoAuthProvider(),
            timeout=30
        )

        resultado = db.obtener_conceptos_retefuente(estructura_contable=999)

        print(f"\nResultado API real estructura 999 (no existe):")
        print(f"  Success: {resultado['success']}")
        print(f"  Message: {resultado['message']}")

        assert resultado['success'] is False
        assert resultado['data'] == []


# =====================================
# TESTS: obtener_concepto_por_index
# =====================================

class TestObtenerConceptoPorIndex:
    """Tests para obtener_concepto_por_index - Migracion v3.4.0"""

    @patch('database.database.requests.Session')
    def test_obtener_concepto_por_index_exitoso(self, mock_session_class):
        """Debe retornar concepto completo con todos los campos"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {'code': 0, 'message': 'success'},
            'data': [
                {
                    'id': 1,
                    'estructura_contable': 18,
                    'codigo_concepto': 'CO1',
                    'descripcion_concepto': 'GASTOS REEMBOLSABLES 11%',
                    'porcentaje': 11,
                    'base': 1000000.0
                }
            ]
        }

        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_concepto_por_index(index=1, estructura_contable=18)

        assert resultado['success'] is True
        assert 'data' in resultado
        assert resultado['data']['index'] == 1
        assert resultado['data']['descripcion_concepto'] == 'GASTOS REEMBOLSABLES 11%'
        assert resultado['data']['porcentaje'] == 11
        assert resultado['data']['base'] == 1000000.0
        assert resultado['data']['codigo_concepto'] == 'CO1'
        assert resultado['data']['estructura_contable'] == 18
        assert 'raw_data' in resultado

    @patch('database.database.requests.Session')
    def test_obtener_concepto_index_no_existe(self, mock_session_class):
        """Debe manejar index inexistente (404)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {
                'code': 404,
                'message': 'No se encontraron datos con los criterios proporcionados.'
            },
            'data': []
        }

        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_concepto_por_index(index=99999, estructura_contable=18)

        assert resultado['success'] is False
        assert resultado['data'] is None
        assert 'No existe concepto' in resultado['message']

    @patch('database.database.requests.Session')
    def test_obtener_concepto_estructura_invalida(self, mock_session_class):
        """Debe manejar estructura contable invalida"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {'code': 0, 'message': 'success'},
            'data': []
        }

        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_concepto_por_index(index=1, estructura_contable=999)

        assert resultado['success'] is False
        assert resultado['data'] is None

    @patch('database.database.requests.Session')
    def test_obtener_concepto_conversion_decimal(self, mock_session_class):
        """Debe convertir formato decimal con coma (3,5 -> 3.5)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {'code': 0, 'message': 'success'},
            'data': [
                {
                    'id': 720,
                    'estructura_contable': 17,
                    'codigo_concepto': 'RLC',
                    'descripcion_concepto': 'RETENCION LICENCIAS 3.5%',
                    'porcentaje': '3,5',
                    'base': '500000,50'
                }
            ]
        }

        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_concepto_por_index(index=720, estructura_contable=17)

        assert resultado['success'] is True
        assert resultado['data']['porcentaje'] == 3.5
        assert resultado['data']['base'] == 500000.50

    @patch('database.database.requests.Session')
    def test_obtener_concepto_timeout(self, mock_session_class):
        """Debe manejar timeout correctamente"""
        mock_session = Mock()
        mock_session.request.side_effect = requests.exceptions.Timeout("Connection timed out")
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_concepto_por_index(index=1, estructura_contable=18)

        assert resultado['success'] is False
        assert 'Timeout' in resultado['message']

    @patch('database.database.requests.Session')
    def test_obtener_concepto_error_red(self, mock_session_class):
        """Debe manejar errores de red"""
        mock_session = Mock()
        mock_session.request.side_effect = requests.exceptions.RequestException("Network error")
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_concepto_por_index(index=1, estructura_contable=18)

        assert resultado['success'] is False
        assert 'Error de red' in resultado['message']


# =====================================
# TESTS DE INTEGRACION: obtener_concepto_por_index
# =====================================

class TestObtenerConceptoPorIndexIntegracion:
    """Tests de integracion con API real"""

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="Requiere NEXURA_API_BASE_URL configurado en .env"
    )
    def test_integracion_obtener_concepto_index_1_estructura_18(self):
        """Test de integracion real - index 1, estructura 18"""
        base_url = os.getenv("NEXURA_API_BASE_URL")

        db = NexuraAPIDatabase(
            base_url=base_url,
            auth_provider=NoAuthProvider(),
            timeout=30
        )

        resultado = db.obtener_concepto_por_index(index=1, estructura_contable=18)

        print(f"\nResultado API real index 1, estructura 18:")
        print(f"  Success: {resultado['success']}")
        print(f"  Message: {resultado['message']}")

        if resultado['success']:
            print(f"  Concepto:")
            print(f"    Index: {resultado['data']['index']}")
            print(f"    Descripcion: {resultado['data']['descripcion_concepto']}")
            print(f"    Porcentaje: {resultado['data']['porcentaje']}%")
            print(f"    Base: ${resultado['data']['base']:,.2f}")
            print(f"    Codigo: {resultado['data']['codigo_concepto']}")

        assert resultado['success'] is True
        assert 'data' in resultado
        assert resultado['data']['index'] == 1
        assert resultado['data']['estructura_contable'] == 18

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="Requiere NEXURA_API_BASE_URL configurado en .env"
    )
    def test_integracion_obtener_concepto_index_invalido(self):
        """Test de integracion real - index inexistente"""
        base_url = os.getenv("NEXURA_API_BASE_URL")

        db = NexuraAPIDatabase(
            base_url=base_url,
            auth_provider=NoAuthProvider(),
            timeout=30
        )

        resultado = db.obtener_concepto_por_index(index=99999, estructura_contable=18)

        print(f"\nResultado API real index 99999 (no existe):")
        print(f"  Success: {resultado['success']}")
        print(f"  Message: {resultado['message']}")

        assert resultado['success'] is False
        assert resultado['data'] is None


# =====================================
# TESTS: obtener_tipo_recurso
# =====================================

class TestObtenerTipoRecurso:
    """Tests para obtener_tipo_recurso - Migracion v3.5.0"""

    @patch('database.database.requests.Session')
    def test_obtener_tipo_recurso_publicos_exitoso(self, mock_session_class):
        """Debe retornar 'Publicos' correctamente"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {'code': 0, 'message': 'success'},
            'data': [
                {
                    'id': 1,
                    'CODIGO_NEGOCIO': 1027,
                    'PUBLICO_PRIVADO': 'Públicos',
                    'NIT': '830.054.060',
                    'NOMBRE_FIDEICOMISO': 'CREDITOS LITIGIOSOS ALCALIS'
                }
            ]
        }

        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_tipo_recurso(codigo_negocio='1027')

        assert resultado['success'] is True
        assert 'data' in resultado
        assert resultado['data']['tipo_recurso'] == 'Públicos'
        assert resultado['data']['codigo_negocio'] == '1027'
        assert 'raw_data' in resultado

    @patch('database.database.requests.Session')
    def test_obtener_tipo_recurso_privados_exitoso(self, mock_session_class):
        """Debe retornar 'Privados' correctamente"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {'code': 0, 'message': 'success'},
            'data': [
                {
                    'id': 2,
                    'CODIGO_NEGOCIO': 5000,
                    'PUBLICO_PRIVADO': 'Privados',
                    'NIT': '900123456',
                    'NOMBRE_FIDEICOMISO': 'FIDEICOMISO PRIVADO'
                }
            ]
        }

        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_tipo_recurso(codigo_negocio='5000')

        assert resultado['success'] is True
        assert resultado['data']['tipo_recurso'] == 'Privados'
        assert resultado['data']['codigo_negocio'] == '5000'

    @patch('database.database.requests.Session')
    def test_obtener_tipo_recurso_codigo_no_existe(self, mock_session_class):
        """Debe manejar codigo no parametrizado (404)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {
                'code': 404,
                'message': 'No se encontraron recursos con los criterios proporcionados.'
            },
            'data': []
        }

        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_tipo_recurso(codigo_negocio='99999')

        assert resultado['success'] is False
        assert resultado['data'] is None
        assert 'No existe parametrización' in resultado['message']

    @patch('database.database.requests.Session')
    def test_obtener_tipo_recurso_data_vacio(self, mock_session_class):
        """Debe manejar respuesta exitosa pero con data vacio"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {'code': 0, 'message': 'success'},
            'data': []
        }

        mock_session = Mock()
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_tipo_recurso(codigo_negocio='1027')

        assert resultado['success'] is False
        assert resultado['data'] is None

    @patch('database.database.requests.Session')
    def test_obtener_tipo_recurso_timeout(self, mock_session_class):
        """Debe manejar timeout correctamente"""
        mock_session = Mock()
        mock_session.request.side_effect = requests.exceptions.Timeout("Connection timed out")
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_tipo_recurso(codigo_negocio='1027')

        assert resultado['success'] is False
        assert 'Timeout' in resultado['message']

    @patch('database.database.requests.Session')
    def test_obtener_tipo_recurso_error_red(self, mock_session_class):
        """Debe manejar errores de red"""
        mock_session = Mock()
        mock_session.request.side_effect = requests.exceptions.RequestException("Network error")
        mock_session_class.return_value = mock_session

        db = NexuraAPIDatabase(
            base_url="https://api.test.com",
            auth_provider=NoAuthProvider(),
            timeout=10
        )

        resultado = db.obtener_tipo_recurso(codigo_negocio='1027')

        assert resultado['success'] is False
        assert 'Error de red' in resultado['message']


# =====================================
# TESTS DE INTEGRACION: obtener_tipo_recurso
# =====================================

class TestObtenerTipoRecursoIntegracion:
    """Tests de integracion con API real"""

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="Requiere NEXURA_API_BASE_URL configurado en .env"
    )
    def test_integracion_tipo_recurso_codigo_1027(self):
        """Test de integracion real - codigo 1027 (Publicos)"""
        base_url = os.getenv("NEXURA_API_BASE_URL")

        db = NexuraAPIDatabase(
            base_url=base_url,
            auth_provider=NoAuthProvider(),
            timeout=30
        )

        resultado = db.obtener_tipo_recurso(codigo_negocio='1027')

        print(f"\nResultado API real codigo 1027:")
        print(f"  Success: {resultado['success']}")
        print(f"  Message: {resultado['message']}")

        if resultado['success']:
            print(f"  Datos:")
            print(f"    Tipo recurso: {resultado['data']['tipo_recurso']}")
            print(f"    Codigo negocio: {resultado['data']['codigo_negocio']}")

        assert resultado['success'] is True
        assert 'data' in resultado
        assert resultado['data']['tipo_recurso'] == 'Públicos'
        assert resultado['data']['codigo_negocio'] == '1027'

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="Requiere NEXURA_API_BASE_URL configurado en .env"
    )
    def test_integracion_tipo_recurso_codigo_invalido(self):
        """Test de integracion real - codigo inexistente"""
        base_url = os.getenv("NEXURA_API_BASE_URL")

        db = NexuraAPIDatabase(
            base_url=base_url,
            auth_provider=NoAuthProvider(),
            timeout=30
        )

        resultado = db.obtener_tipo_recurso(codigo_negocio='999999')

        print(f"\nResultado API real codigo 999999 (no existe):")
        print(f"  Success: {resultado['success']}")
        print(f"  Message: {resultado['message']}")

        assert resultado['success'] is False
        assert resultado['data'] is None


# =====================================
# TESTS: obtener_conceptos_extranjeros()
# =====================================

class TestObtenerConceptosExtranjeros:
    """Tests unitarios para obtener_conceptos_extranjeros en NexuraAPIDatabase"""

    def test_obtener_conceptos_extranjeros_exitoso(self):
        """Test exitoso - retorna lista de conceptos"""
        mock_auth = Mock(spec=IAuthProvider)
        db = NexuraAPIDatabase(
            base_url='https://test.com/api',
            auth_provider=mock_auth,
            timeout=10
        )

        mock_response = {
            'error': {'code': 0, 'message': 'success'},
            'data': [
                {
                    'id': 1,
                    'nombre_concepto': 'Intereses y regalias',
                    'base_pesos': '0',
                    'tarifa_normal': '20',
                    'tarifa_convenio': '10'
                },
                {
                    'id': 2,
                    'nombre_concepto': 'Consultoria y asistencia tecnica',
                    'base_pesos': '100000',
                    'tarifa_normal': '20',
                    'tarifa_convenio': '10'
                }
            ]
        }

        with patch.object(db, '_hacer_request', return_value=mock_response):
            resultado = db.obtener_conceptos_extranjeros()

        assert resultado['success'] is True
        assert 'data' in resultado
        assert isinstance(resultado['data'], list)
        assert len(resultado['data']) == 2
        assert resultado['count'] == 2

        # Verificar primer concepto con mapeo id -> index
        concepto1 = resultado['data'][0]
        assert concepto1['index'] == 1  # Mapeo: id -> index
        assert concepto1['nombre_concepto'] == 'Intereses y regalias'
        assert concepto1['base_pesos'] == 0.0
        assert concepto1['tarifa_normal'] == 20.0
        assert concepto1['tarifa_convenio'] == 10.0

    def test_obtener_conceptos_extranjeros_conversion_decimal(self):
        """Test conversion de formato con coma decimal"""
        mock_auth = Mock(spec=IAuthProvider)
        db = NexuraAPIDatabase(
            base_url='https://test.com/api',
            auth_provider=mock_auth,
            timeout=10
        )

        mock_response = {
            'error': {'code': 0, 'message': 'success'},
            'data': [
                {
                    'id': 3,
                    'nombre_concepto': 'Rendimientos financieros',
                    'base_pesos': '50000,5',
                    'tarifa_normal': '15,5',
                    'tarifa_convenio': '7,5'
                }
            ]
        }

        with patch.object(db, '_hacer_request', return_value=mock_response):
            resultado = db.obtener_conceptos_extranjeros()

        assert resultado['success'] is True
        concepto = resultado['data'][0]
        assert concepto['base_pesos'] == 50000.5
        assert concepto['tarifa_normal'] == 15.5
        assert concepto['tarifa_convenio'] == 7.5

    def test_obtener_conceptos_extranjeros_no_encontrados(self):
        """Test cuando no hay conceptos"""
        mock_auth = Mock(spec=IAuthProvider)
        db = NexuraAPIDatabase(
            base_url='https://test.com/api',
            auth_provider=mock_auth,
            timeout=10
        )

        mock_response = {
            'error': {'code': 0, 'message': 'success'},
            'data': []
        }

        with patch.object(db, '_hacer_request', return_value=mock_response):
            resultado = db.obtener_conceptos_extranjeros()

        assert resultado['success'] is False
        assert resultado['data'] == []
        assert resultado['count'] == 0
        assert 'No se encontraron' in resultado['message']

    def test_obtener_conceptos_extranjeros_error_api(self):
        """Test error de API"""
        mock_auth = Mock(spec=IAuthProvider)
        db = NexuraAPIDatabase(
            base_url='https://test.com/api',
            auth_provider=mock_auth,
            timeout=10
        )

        mock_response = {
            'error': {'code': 500, 'message': 'Error interno del servidor'},
            'data': []
        }

        with patch.object(db, '_hacer_request', return_value=mock_response):
            resultado = db.obtener_conceptos_extranjeros()

        assert resultado['success'] is False
        assert resultado['data'] == []
        assert 'Error de API' in resultado['message']

    def test_obtener_conceptos_extranjeros_timeout(self):
        """Test timeout de red"""
        mock_auth = Mock(spec=IAuthProvider)
        db = NexuraAPIDatabase(
            base_url='https://test.com/api',
            auth_provider=mock_auth,
            timeout=10
        )

        with patch.object(db, '_hacer_request', side_effect=requests.exceptions.Timeout):
            resultado = db.obtener_conceptos_extranjeros()

        assert resultado['success'] is False
        assert resultado['data'] == []
        assert 'Timeout' in resultado['message']

    def test_obtener_conceptos_extranjeros_error_red(self):
        """Test error de red"""
        mock_auth = Mock(spec=IAuthProvider)
        db = NexuraAPIDatabase(
            base_url='https://test.com/api',
            auth_provider=mock_auth,
            timeout=10
        )

        with patch.object(db, '_hacer_request', side_effect=requests.exceptions.RequestException("Connection error")):
            resultado = db.obtener_conceptos_extranjeros()

        assert resultado['success'] is False
        assert resultado['data'] == []
        assert 'Error de red' in resultado['message']


# =====================================
# TESTS: obtener_paises_con_convenio()
# =====================================

class TestObtenerPaisesConConvenio:
    """Tests unitarios para obtener_paises_con_convenio en NexuraAPIDatabase"""

    def test_obtener_paises_exitoso(self):
        """Test exitoso - retorna lista de paises"""
        mock_auth = Mock(spec=IAuthProvider)
        db = NexuraAPIDatabase(
            base_url='https://test.com/api',
            auth_provider=mock_auth,
            timeout=10
        )

        mock_response = {
            'error': {'code': 0, 'message': 'success'},
            'data': [
                {'id': 1, 'nombre_pais': 'francia'},
                {'id': 2, 'nombre_pais': 'italia'},
                {'id': 3, 'nombre_pais': 'reino unido'},
                {'id': 4, 'nombre_pais': 'españa'}
            ]
        }

        with patch.object(db, '_hacer_request', return_value=mock_response):
            resultado = db.obtener_paises_con_convenio()

        assert resultado['success'] is True
        assert 'data' in resultado
        assert isinstance(resultado['data'], list)
        assert len(resultado['data']) == 4
        assert resultado['count'] == 4

        # Verificar que retorna solo nombres de paises (no objetos completos)
        assert resultado['data'] == ['francia', 'italia', 'reino unido', 'españa']

    def test_obtener_paises_no_encontrados(self):
        """Test cuando no hay paises"""
        mock_auth = Mock(spec=IAuthProvider)
        db = NexuraAPIDatabase(
            base_url='https://test.com/api',
            auth_provider=mock_auth,
            timeout=10
        )

        mock_response = {
            'error': {'code': 0, 'message': 'success'},
            'data': []
        }

        with patch.object(db, '_hacer_request', return_value=mock_response):
            resultado = db.obtener_paises_con_convenio()

        assert resultado['success'] is False
        assert resultado['data'] == []
        assert resultado['count'] == 0
        assert 'No se encontraron' in resultado['message']

    def test_obtener_paises_filtra_nulos(self):
        """Test filtrado de registros con nombre_pais nulo"""
        mock_auth = Mock(spec=IAuthProvider)
        db = NexuraAPIDatabase(
            base_url='https://test.com/api',
            auth_provider=mock_auth,
            timeout=10
        )

        mock_response = {
            'error': {'code': 0, 'message': 'success'},
            'data': [
                {'id': 1, 'nombre_pais': 'francia'},
                {'id': 2, 'nombre_pais': None},
                {'id': 3, 'nombre_pais': 'italia'}
            ]
        }

        with patch.object(db, '_hacer_request', return_value=mock_response):
            resultado = db.obtener_paises_con_convenio()

        assert resultado['success'] is True
        assert len(resultado['data']) == 2
        assert resultado['data'] == ['francia', 'italia']

    def test_obtener_paises_error_api(self):
        """Test error de API"""
        mock_auth = Mock(spec=IAuthProvider)
        db = NexuraAPIDatabase(
            base_url='https://test.com/api',
            auth_provider=mock_auth,
            timeout=10
        )

        mock_response = {
            'error': {'code': 500, 'message': 'Error interno del servidor'},
            'data': []
        }

        with patch.object(db, '_hacer_request', return_value=mock_response):
            resultado = db.obtener_paises_con_convenio()

        assert resultado['success'] is False
        assert resultado['data'] == []
        assert 'Error de API' in resultado['message']

    def test_obtener_paises_timeout(self):
        """Test timeout de red"""
        mock_auth = Mock(spec=IAuthProvider)
        db = NexuraAPIDatabase(
            base_url='https://test.com/api',
            auth_provider=mock_auth,
            timeout=10
        )

        with patch.object(db, '_hacer_request', side_effect=requests.exceptions.Timeout):
            resultado = db.obtener_paises_con_convenio()

        assert resultado['success'] is False
        assert resultado['data'] == []
        assert 'Timeout' in resultado['message']

    def test_obtener_paises_error_red(self):
        """Test error de red"""
        mock_auth = Mock(spec=IAuthProvider)
        db = NexuraAPIDatabase(
            base_url='https://test.com/api',
            auth_provider=mock_auth,
            timeout=10
        )

        with patch.object(db, '_hacer_request', side_effect=requests.exceptions.RequestException("Connection error")):
            resultado = db.obtener_paises_con_convenio()

        assert resultado['success'] is False
        assert resultado['data'] == []
        assert 'Error de red' in resultado['message']


# =====================================
# TESTS DE INTEGRACION: conceptosExtranjeros y paisesConvenio
# =====================================

class TestObtenerConceptosExtranjerosIntegracion:
    """Tests de integracion con API real para obtener_conceptos_extranjeros"""

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="Requiere NEXURA_API_BASE_URL configurado en .env"
    )
    def test_integracion_obtener_conceptos_extranjeros(self):
        """Test de integracion real - obtener conceptos extranjeros"""
        base_url = os.getenv("NEXURA_API_BASE_URL")

        db = NexuraAPIDatabase(
            base_url=base_url,
            auth_provider=NoAuthProvider(),
            timeout=30
        )

        resultado = db.obtener_conceptos_extranjeros()

        print(f"\nResultado API real - conceptos extranjeros:")
        print(f"  Success: {resultado['success']}")
        print(f"  Count: {resultado.get('count', 0)}")
        print(f"  Message: {resultado['message']}")

        if resultado['success'] and resultado['data']:
            print(f"\n  Primer concepto:")
            concepto = resultado['data'][0]
            print(f"    Index: {concepto.get('index')}")
            print(f"    Nombre: {concepto.get('nombre_concepto')[:50]}...")
            print(f"    Tarifa normal: {concepto.get('tarifa_normal')}%")
            print(f"    Tarifa convenio: {concepto.get('tarifa_convenio')}%")

        assert resultado['success'] is True
        assert 'data' in resultado
        assert isinstance(resultado['data'], list)
        assert len(resultado['data']) > 0
        assert resultado['count'] > 0

        # Verificar estructura del primer concepto
        concepto = resultado['data'][0]
        assert 'index' in concepto
        assert 'nombre_concepto' in concepto
        assert 'base_pesos' in concepto
        assert 'tarifa_normal' in concepto
        assert 'tarifa_convenio' in concepto


class TestObtenerPaisesConConvenioIntegracion:
    """Tests de integracion con API real para obtener_paises_con_convenio"""

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="Requiere NEXURA_API_BASE_URL configurado en .env"
    )
    def test_integracion_obtener_paises_con_convenio(self):
        """Test de integracion real - obtener paises con convenio"""
        base_url = os.getenv("NEXURA_API_BASE_URL")

        db = NexuraAPIDatabase(
            base_url=base_url,
            auth_provider=NoAuthProvider(),
            timeout=30
        )

        resultado = db.obtener_paises_con_convenio()

        print(f"\nResultado API real - paises con convenio:")
        print(f"  Success: {resultado['success']}")
        print(f"  Count: {resultado.get('count', 0)}")
        print(f"  Message: {resultado['message']}")

        if resultado['success'] and resultado['data']:
            print(f"\n  Primeros 5 paises:")
            for i, pais in enumerate(resultado['data'][:5], 1):
                print(f"    {i}. {pais}")

        assert resultado['success'] is True
        assert 'data' in resultado
        assert isinstance(resultado['data'], list)
        assert len(resultado['data']) > 0
        assert resultado['count'] > 0

        # Verificar que son strings, no objetos
        assert all(isinstance(pais, str) for pais in resultado['data'])


# =====================================
# MAIN - EJECUTAR TESTS
# =====================================

if __name__ == "__main__":
    """
    Ejecutar tests desde linea de comandos

    Ejemplos:
        python tests/test_nexura_database.py          # Todos los tests
        pytest tests/test_nexura_database.py -v       # Con pytest verbose
        pytest tests/test_nexura_database.py -k "auth"  # Solo tests de auth
    """
    pytest.main([__file__, "-v", "--tb=short"])
