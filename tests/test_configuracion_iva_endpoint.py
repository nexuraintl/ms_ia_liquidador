"""
TESTS PARA CONFIGURACION IVA DESDE ENDPOINT
============================================

Suite de tests para validar la obtencion de configuracion IVA desde
Nexura API endpoint y el sistema de cache/fallback.

PRINCIPIOS SOLID APLICADOS EN TESTS:
- SRP: Cada test valida una sola funcionalidad
- DIP: Tests usan mocks para dependencias externas
- Aislamiento: Tests unitarios independientes de la API real

COBERTURA:
1. NexuraAPIDatabase.obtener_configuracion_iva_db()
2. config.obtener_configuracion_iva() con database_manager
3. Sistema de cache
4. Fallback a valores hardcodeados
5. Manejo de errores HTTP
6. Integracion con API real (opcional)

Autor: Sistema Preliquidador
Version: 3.0 - Clean Architecture
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import requests

# Agregar path del proyecto para imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import NexuraAPIDatabase, DatabaseManager
from database.auth_provider import NoAuthProvider
from config import obtener_configuracion_iva, limpiar_cache_configuracion_iva


# =====================================
# FIXTURES PARA TESTS
# =====================================

@pytest.fixture
def mock_response_exitoso_iva():
    """
    Fixture con respuesta exitosa de configuracion IVA desde Nexura API

    Simula estructura real del endpoint /preliquidador/impuestoValorAgregado/
    Los datos vienen como objeto (no array) con arrays de strings
    """
    return {
        "error": {
            "code": 0,
            "message": "success",
            "detail": []
        },
        "data": {
            "BIENES_NO_CAUSAN_IVA": [
                "Animales vivos de la especie porcina",
                "Animales vivos de las especies ovina o caprina",
                "Gallos, gallinas, patos, gansos, pavos",
                "Los demas animales vivos"
            ],
            "BIENES_EXENTOS_IVA": [
                "Animales vivos de la especie bovina, excepto los de lidia",
                "Pollitos de un dia de nacidos",
                "Carne de animales de la especie bovina"
            ],
            "SERVICIOS_EXCLUIDOS_IVA": [
                "Los servicios medicos, odontologicos, hospitalarios",
                "Los servicios de administracion de fondos del Estado",
                "Comisiones por intermediacion"
            ]
        }
    }


@pytest.fixture
def mock_response_vacio_iva():
    """Fixture con respuesta cuando no se encuentra configuracion IVA"""
    return {
        "error": {
            "code": 0,
            "message": "success",
            "detail": []
        },
        "data": {}
    }


@pytest.fixture
def mock_response_error_500_iva():
    """Fixture con error 500 del servidor"""
    return {
        "error": {
            "code": 500,
            "message": "Internal Server Error",
            "detail": ["Error en el servidor de base de datos"]
        },
        "data": None
    }


@pytest.fixture
def mock_response_error_timeout():
    """Fixture para simular timeout de conexion"""
    return None  # Se usara para lanzar excepcion de timeout


@pytest.fixture
def mock_response_error_iva():
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


@pytest.fixture(autouse=True)
def limpiar_cache_antes_de_cada_test():
    """Limpia el cache antes de cada test para aislar tests"""
    limpiar_cache_configuracion_iva()
    yield
    limpiar_cache_configuracion_iva()


# =====================================
# TESTS DE NEXURA API DATABASE
# =====================================

class TestNexuraAPIDatabase:
    """Tests para obtener_configuracion_iva_db en NexuraAPIDatabase"""

    @patch('database.database.requests.Session.request')
    def test_obtener_configuracion_iva_exitoso(
        self,
        mock_request,
        no_auth_provider,
        mock_response_exitoso_iva
    ):
        """obtener_configuracion_iva_db debe retornar datos correctamente"""
        # Configurar mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_exitoso_iva
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.obtener_configuracion_iva_db()

        # Validar resultado
        assert resultado['success'] is True
        assert resultado['data'] is not None
        assert 'bienes_no_causan_iva' in resultado['data']
        assert 'bienes_exentos_iva' in resultado['data']
        assert 'servicios_excluidos_iva' in resultado['data']

        # Validar contenido
        assert len(resultado['data']['bienes_no_causan_iva']) == 4
        assert len(resultado['data']['bienes_exentos_iva']) == 3
        assert len(resultado['data']['servicios_excluidos_iva']) == 3

        # Validar mensaje
        assert 'exitosamente' in resultado['message']
        assert 'fuente' not in resultado  # fuente se agrega en config.py

    @patch('database.database.requests.Session.request')
    def test_obtener_configuracion_iva_no_encontrado(
        self,
        mock_request,
        no_auth_provider,
        mock_response_vacio_iva
    ):
        """obtener_configuracion_iva_db debe manejar cuando no hay datos"""
        # Configurar mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_vacio_iva
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.obtener_configuracion_iva_db()

        # Validar resultado
        assert resultado['success'] is False
        assert resultado['data'] is None
        assert 'No se encontro' in resultado['message']

    @patch('database.database.requests.Session.request')
    def test_obtener_configuracion_iva_error_api(
        self,
        mock_request,
        no_auth_provider,
        mock_response_error_iva
    ):
        """obtener_configuracion_iva_db debe manejar errores de la API"""
        # Configurar mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_error_iva
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.obtener_configuracion_iva_db()

        # Validar resultado
        assert resultado['success'] is False
        assert resultado['data'] is None
        assert 'Error de API' in resultado['message']

    @patch('database.database.requests.Session.request')
    def test_obtener_configuracion_iva_timeout(self, mock_request, no_auth_provider):
        """obtener_configuracion_iva_db debe manejar timeout"""
        # Configurar mock para lanzar timeout
        mock_request.side_effect = requests.exceptions.Timeout("Connection timeout")

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.obtener_configuracion_iva_db()

        # Validar resultado
        assert resultado['success'] is False
        assert resultado['error'] == 'Timeout'
        assert 'Timeout' in resultado['message']

    @patch('database.database.requests.Session.request')
    def test_obtener_configuracion_iva_http_error(self, mock_request, no_auth_provider):
        """obtener_configuracion_iva_db debe manejar errores HTTP"""
        # Configurar mock para lanzar HTTPError
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_request.return_value = mock_response

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.obtener_configuracion_iva_db()

        # Validar resultado
        assert resultado['success'] is False
        assert 'Error HTTP' in resultado['message']

    @patch('database.database.requests.Session.request')
    def test_obtener_configuracion_iva_404(self, mock_request, no_auth_provider):
        """obtener_configuracion_iva_db debe manejar 404 correctamente"""
        # Configurar mock para 404
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': {'code': 404, 'message': 'Not found'},
            'data': []
        }
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        # Crear database y ejecutar
        db = NexuraAPIDatabase(
            base_url="https://api.example.com",
            auth_provider=no_auth_provider
        )
        resultado = db.obtener_configuracion_iva_db()

        # Validar resultado
        assert resultado['success'] is False
        assert resultado['data'] is None
        assert 'skip_fallback' in resultado
        assert resultado['skip_fallback'] is True


# =====================================
# TESTS DE CONFIG.PY
# =====================================

class TestObtenerConfiguracionIva:
    """Tests para obtener_configuracion_iva en config.py"""

    def test_obtener_sin_database_manager_lanza_excepcion(self):
        """Sin database_manager debe lanzar ValueError"""
        with pytest.raises(ValueError) as exc_info:
            obtener_configuracion_iva(database_manager=None)

        assert "database_manager es requerido" in str(exc_info.value)

    def test_obtener_con_database_manager_exitoso(self):
        """Con database_manager exitoso debe usar datos de BD"""
        # Mock database manager
        mock_db_manager = Mock()
        mock_db_manager.obtener_configuracion_iva_db.return_value = {
            'success': True,
            'data': {
                'bienes_no_causan_iva': {'1': 'Test bienes no causan'},
                'bienes_exentos_iva': {'1': 'Test bienes exentos'},
                'servicios_excluidos_iva': {'1': 'Test servicios excluidos'}
            },
            'message': 'Exito'
        }

        resultado = obtener_configuracion_iva(database_manager=mock_db_manager)

        assert resultado is not None
        assert resultado['fuente'] == 'database'
        assert resultado['bienes_no_causan_iva'] == {'1': 'Test bienes no causan'}
        assert resultado['bienes_exentos_iva'] == {'1': 'Test bienes exentos'}
        assert resultado['servicios_excluidos_iva'] == {'1': 'Test servicios excluidos'}

        # Verificar que se llamo al database manager
        mock_db_manager.obtener_configuracion_iva_db.assert_called_once()

    def test_obtener_con_database_manager_fallo_lanza_excepcion(self):
        """Si database_manager falla debe lanzar ValueError"""
        # Mock database manager que falla
        mock_db_manager = Mock()
        mock_db_manager.obtener_configuracion_iva_db.return_value = {
            'success': False,
            'data': None,
            'message': 'Error'
        }

        with pytest.raises(ValueError) as exc_info:
            obtener_configuracion_iva(database_manager=mock_db_manager)

        assert "No se pudo obtener configuracion IVA desde BD" in str(exc_info.value)

    def test_obtener_con_database_manager_excepcion_lanza_valor_error(self):
        """Si database_manager lanza excepcion debe lanzar ValueError"""
        # Mock database manager que lanza excepcion
        mock_db_manager = Mock()
        mock_db_manager.obtener_configuracion_iva_db.side_effect = Exception("Error de conexion")

        with pytest.raises(ValueError) as exc_info:
            obtener_configuracion_iva(database_manager=mock_db_manager)

        assert "Error obteniendo configuracion IVA desde base de datos" in str(exc_info.value)


# =====================================
# TESTS DE SISTEMA DE CACHE
# =====================================

class TestSistemaCache:
    """Tests para sistema de cache de configuracion IVA"""

    def test_cache_funciona_correctamente(self):
        """El cache debe evitar llamadas repetidas al database manager"""
        # Mock database manager
        mock_db_manager = Mock()
        mock_db_manager.obtener_configuracion_iva_db.return_value = {
            'success': True,
            'data': {
                'bienes_no_causan_iva': {'1': 'Test cache'},
                'bienes_exentos_iva': {'1': 'Test cache'},
                'servicios_excluidos_iva': {'1': 'Test cache'}
            },
            'message': 'Exito'
        }

        # Primera llamada - debe consultar database
        resultado1 = obtener_configuracion_iva(database_manager=mock_db_manager, usar_cache=True)
        assert resultado1['fuente'] == 'database'
        assert mock_db_manager.obtener_configuracion_iva_db.call_count == 1

        # Segunda llamada - debe usar cache
        resultado2 = obtener_configuracion_iva(database_manager=mock_db_manager, usar_cache=True)
        assert resultado2['fuente'] == 'database'
        assert mock_db_manager.obtener_configuracion_iva_db.call_count == 1  # No debe aumentar

        # Verificar que retorna los mismos datos
        assert resultado1 == resultado2

    def test_cache_deshabilitado_consulta_siempre(self):
        """Con usar_cache=False debe consultar siempre"""
        # Mock database manager
        mock_db_manager = Mock()
        mock_db_manager.obtener_configuracion_iva_db.return_value = {
            'success': True,
            'data': {
                'bienes_no_causan_iva': {'1': 'Test'},
                'bienes_exentos_iva': {'1': 'Test'},
                'servicios_excluidos_iva': {'1': 'Test'}
            },
            'message': 'Exito'
        }

        # Primera llamada
        resultado1 = obtener_configuracion_iva(database_manager=mock_db_manager, usar_cache=False)
        assert mock_db_manager.obtener_configuracion_iva_db.call_count == 1

        # Segunda llamada - debe consultar de nuevo
        resultado2 = obtener_configuracion_iva(database_manager=mock_db_manager, usar_cache=False)
        assert mock_db_manager.obtener_configuracion_iva_db.call_count == 2

    def test_limpiar_cache_funciona(self):
        """limpiar_cache_configuracion_iva debe limpiar el cache"""
        # Mock database manager
        mock_db_manager = Mock()
        mock_db_manager.obtener_configuracion_iva_db.return_value = {
            'success': True,
            'data': {
                'bienes_no_causan_iva': {'1': 'Test'},
                'bienes_exentos_iva': {'1': 'Test'},
                'servicios_excluidos_iva': {'1': 'Test'}
            },
            'message': 'Exito'
        }

        # Primera llamada - cachea
        resultado1 = obtener_configuracion_iva(database_manager=mock_db_manager, usar_cache=True)
        assert mock_db_manager.obtener_configuracion_iva_db.call_count == 1

        # Limpiar cache
        limpiar_cache_configuracion_iva()

        # Segunda llamada - debe consultar de nuevo
        resultado2 = obtener_configuracion_iva(database_manager=mock_db_manager, usar_cache=True)
        assert mock_db_manager.obtener_configuracion_iva_db.call_count == 2


# =====================================
# TESTS DE INTEGRACION CON API REAL
# =====================================

class TestIntegracionAPIReal:
    """
    Tests de integracion con API real de Nexura (OPCIONAL)

    Estos tests hacen requests reales a la API. Solo ejecutar si:
    1. Variables de entorno estan configuradas
    2. Se quiere validar conectividad real
    3. Se esta en ambiente de desarrollo/testing

    Para ejecutar solo estos tests:
        pytest tests/test_configuracion_iva_endpoint.py::TestIntegracionAPIReal -v
    """

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="NEXURA_API_BASE_URL no configurada"
    )
    def test_integracion_obtener_configuracion_iva_real(self):
        """Test de integracion con API real"""
        # Crear database con configuracion real
        base_url = os.getenv("NEXURA_API_BASE_URL")
        db = NexuraAPIDatabase(
            base_url=base_url,
            auth_provider=NoAuthProvider(),
            timeout=30
        )

        # Ejecutar consulta real
        resultado = db.obtener_configuracion_iva_db()

        # Validar estructura de respuesta
        assert 'success' in resultado
        assert 'message' in resultado

        # Imprimir resultado para debugging
        print(f"\nResultado API real - configuracion IVA:")
        print(f"  Success: {resultado['success']}")
        print(f"  Message: {resultado['message']}")

        if resultado['success']:
            assert 'data' in resultado
            assert resultado['data'] is not None
            assert 'bienes_no_causan_iva' in resultado['data']
            assert 'bienes_exentos_iva' in resultado['data']
            assert 'servicios_excluidos_iva' in resultado['data']

            # Imprimir cantidades
            print(f"  Bienes no causan IVA: {len(resultado['data']['bienes_no_causan_iva'])}")
            print(f"  Bienes exentos IVA: {len(resultado['data']['bienes_exentos_iva'])}")
            print(f"  Servicios excluidos IVA: {len(resultado['data']['servicios_excluidos_iva'])}")

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="NEXURA_API_BASE_URL no configurada"
    )
    def test_integracion_config_completa_con_database_manager(self):
        """Test de integracion completa usando database manager"""
        from database.setup import inicializar_database_manager

        # Inicializar database manager
        db_manager, _ = asyncio.run(inicializar_database_manager())

        if not db_manager:
            pytest.skip("No se pudo inicializar database manager")

        # Obtener configuracion
        config = obtener_configuracion_iva(database_manager=db_manager, usar_cache=False)

        # Validar
        assert config is not None
        assert 'bienes_no_causan_iva' in config
        assert 'bienes_exentos_iva' in config
        assert 'servicios_excluidos_iva' in config

        print(f"\nFuente de configuracion: {config.get('fuente', 'unknown')}")

        # Si vino de BD, validar estructura
        if config.get('fuente') == 'database':
            assert len(config['bienes_no_causan_iva']) > 0
            assert len(config['bienes_exentos_iva']) > 0
            assert len(config['servicios_excluidos_iva']) > 0

    @pytest.mark.skipif(
        not os.getenv("NEXURA_API_BASE_URL"),
        reason="NEXURA_API_BASE_URL no configurada"
    )
    def test_integracion_prompt_iva_obtiene_datos_api_real(self):
        """Test de integracion: PROMPT_ANALISIS_IVA obtiene datos de API real correctamente"""
        from database.setup import inicializar_database_manager
        from prompts.prompt_iva import PROMPT_ANALISIS_IVA

        # Inicializar database manager real
        db_manager, _ = asyncio.run(inicializar_database_manager())

        if not db_manager:
            pytest.skip("No se pudo inicializar database manager")

        # Llamar a PROMPT_ANALISIS_IVA con database_manager real
        prompt = PROMPT_ANALISIS_IVA(
            factura_texto="Factura de prueba",
            rut_texto="RUT de prueba",
            anexos_texto="Anexos de prueba",
            cotizaciones_texto="Cotizaciones de prueba",
            anexo_contrato="Anexo contrato de prueba",
            nombres_archivos_directos=["factura.pdf"],
            database_manager=db_manager
        )

        # Validar que el prompt fue generado
        assert prompt is not None
        assert isinstance(prompt, str)
        assert len(prompt) > 0

        # Validar que el prompt contiene las secciones esperadas
        assert "CATEGORÍAS DE CLASIFICACIÓN" in prompt
        assert "BIENES QUE NO CAUSAN IVA:" in prompt
        assert "BIENES EXENTOS DE IVA:" in prompt
        assert "SERVICIOS EXCLUIDOS DE IVA:" in prompt

        # Validar que contiene datos reales (no solo texto vacío)
        # Buscar estructuras JSON en el prompt
        assert '"' in prompt  # Debe tener comillas de JSON

        print("\n" + "="*80)
        print("TEST INTEGRACION: PROMPT_ANALISIS_IVA con API REAL")
        print("="*80)
        print(f"Longitud del prompt generado: {len(prompt)} caracteres")
        print("Contiene categorias: OK")
        print("Contiene datos JSON: OK")

        # Mostrar una muestra del prompt (primeros 500 caracteres de las categorías)
        inicio_categorias = prompt.find("BIENES QUE NO CAUSAN IVA:")
        if inicio_categorias != -1:
            muestra = prompt[inicio_categorias:inicio_categorias + 500]
            print("\nMuestra de datos obtenidos de la API:")
            print("-" * 80)
            print(muestra)
            print("-" * 80)


# =====================================
# TESTS DE DATABASE MANAGER
# =====================================

class TestManejErroresFlujCompleto:
    """Tests para verificar que el flujo completo no se rompe ante errores"""

    def test_error_500_servidor_no_rompe_flujo(self):
        """Error 500 del servidor debe lanzar ValueError sin romper el flujo"""
        # Mock database manager que retorna error 500
        mock_db_manager = Mock()
        mock_db_manager.obtener_configuracion_iva_db.return_value = {
            'success': False,
            'data': None,
            'message': 'Error HTTP 500: Internal Server Error'
        }

        # Verificar que lanza ValueError con mensaje apropiado
        with pytest.raises(ValueError) as exc_info:
            obtener_configuracion_iva(database_manager=mock_db_manager)

        assert "No se pudo obtener configuracion IVA desde BD" in str(exc_info.value)
        assert "500" in str(exc_info.value)

    def test_timeout_no_rompe_flujo(self):
        """Timeout de conexion debe lanzar ValueError sin romper el flujo"""
        import requests

        # Mock database manager que simula timeout
        mock_db_manager = Mock()
        mock_db_manager.obtener_configuracion_iva_db.side_effect = requests.exceptions.Timeout("Connection timeout")

        # Verificar que lanza ValueError
        with pytest.raises(ValueError) as exc_info:
            obtener_configuracion_iva(database_manager=mock_db_manager)

        assert "Error obteniendo configuracion IVA desde base de datos" in str(exc_info.value)

    def test_prompt_iva_con_error_servidor(self):
        """PROMPT_ANALISIS_IVA debe propagar error cuando falla obtencion de config"""
        from prompts.prompt_iva import PROMPT_ANALISIS_IVA

        # Mock database manager con error
        mock_db_manager = Mock()
        mock_db_manager.obtener_configuracion_iva_db.return_value = {
            'success': False,
            'data': None,
            'message': 'Error 500'
        }

        # Verificar que PROMPT_ANALISIS_IVA lanza ValueError
        with pytest.raises(ValueError) as exc_info:
            PROMPT_ANALISIS_IVA(
                factura_texto="Test",
                rut_texto="Test",
                anexos_texto="Test",
                cotizaciones_texto="Test",
                anexo_contrato="Test",
                database_manager=mock_db_manager
            )

        assert "No se pudo obtener configuracion IVA desde BD" in str(exc_info.value)

    def test_conexion_perdida_durante_request(self):
        """Perdida de conexion durante request debe manejarse correctamente"""
        import requests

        # Mock database manager que simula ConnectionError
        mock_db_manager = Mock()
        mock_db_manager.obtener_configuracion_iva_db.side_effect = requests.exceptions.ConnectionError("Connection refused")

        # Verificar que lanza ValueError con mensaje apropiado
        with pytest.raises(ValueError) as exc_info:
            obtener_configuracion_iva(database_manager=mock_db_manager)

        assert "Error obteniendo configuracion IVA desde base de datos" in str(exc_info.value)

    def test_detalle_manejo_error_500_con_logging(self, caplog):
        """Test detallado: Verificar logs y respuesta exacta ante error 500"""
        import logging
        caplog.set_level(logging.INFO)

        # Mock database manager que retorna error 500 con estructura realista
        mock_db_manager = Mock()
        mock_db_manager.obtener_configuracion_iva_db.return_value = {
            'success': False,
            'data': None,
            'message': 'Error HTTP 500: Internal Server Error - Database connection failed',
            'error': 'Internal Server Error'
        }

        # Ejecutar y capturar excepcion
        with pytest.raises(ValueError) as exc_info:
            obtener_configuracion_iva(database_manager=mock_db_manager)

        # Verificar mensaje de error
        error_msg = str(exc_info.value)
        assert "No se pudo obtener configuracion IVA desde BD" in error_msg
        assert "Database connection failed" in error_msg

        # Verificar logs
        assert any("Obteniendo configuracion IVA desde base de datos" in record.message for record in caplog.records)
        assert any("No se pudo obtener configuracion IVA desde BD" in record.message for record in caplog.records)

        print("\nRESULTADO ANTE ERROR 500:")
        print(f"  Excepcion lanzada: ValueError")
        print(f"  Mensaje: {error_msg}")
        print(f"  Flujo controlado: SI (ValueError capturada)")
        print(f"  Aplicacion rota: NO (error manejado correctamente)")


class TestDatabaseManager:
    """Tests para DatabaseManager.obtener_configuracion_iva_db"""

    def test_database_manager_delega_correctamente(self):
        """DatabaseManager debe delegar a la implementacion correctamente"""
        # Mock de implementacion
        mock_db_implementation = Mock()
        mock_db_implementation.obtener_configuracion_iva_db.return_value = {
            'success': True,
            'data': {'bienes_no_causan_iva': {}, 'bienes_exentos_iva': {}, 'servicios_excluidos_iva': {}},
            'message': 'Test'
        }

        # Crear database manager
        db_manager = DatabaseManager(mock_db_implementation)

        # Ejecutar
        resultado = db_manager.obtener_configuracion_iva_db()

        # Validar
        assert resultado['success'] is True
        mock_db_implementation.obtener_configuracion_iva_db.assert_called_once()


# =====================================
# MAIN - EJECUTAR TESTS
# =====================================

if __name__ == "__main__":
    """
    Ejecutar tests desde linea de comandos

    Ejemplos:
        python tests/test_configuracion_iva_endpoint.py
        pytest tests/test_configuracion_iva_endpoint.py -v
        pytest tests/test_configuracion_iva_endpoint.py -k "cache"
    """
    pytest.main([__file__, "-v", "--tb=short"])
