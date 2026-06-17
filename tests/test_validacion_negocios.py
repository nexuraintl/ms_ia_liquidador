"""
Tests para el módulo de validación de negocios.
Siguiendo TDD: Tests escritos antes de la implementación.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from app.validacion_negocios import ValidadorNegocio, ResultadoValidacion


class TestValidadorNegocio:
    """Tests para ValidadorNegocio"""

    def setup_method(self):
        """Setup ejecutado antes de cada test"""
        self.business_service = Mock()
        self.validador = ValidadorNegocio(self.business_service)

    def test_negocio_no_parametrizado_retorna_json_response(self):
        """Debe retornar JSONResponse cuando negocio no está parametrizado"""
        # Arrange
        resultado_negocio = {'success': False, 'data': None}
        codigo_negocio = "NEG001"

        # Act
        resultado = self.validador.validar(resultado_negocio, codigo_negocio)

        # Assert
        assert isinstance(resultado, JSONResponse)

    def test_negocio_sin_nit_retorna_json_response(self):
        """Debe retornar JSONResponse cuando negocio no tiene NIT"""
        # Arrange
        resultado_negocio = {'success': True, 'data': {'nombre': 'Test'}}
        codigo_negocio = "NEG001"

        # Act
        resultado = self.validador.validar(resultado_negocio, codigo_negocio)

        # Assert
        assert isinstance(resultado, JSONResponse)

    def test_validacion_exitosa_retorna_resultado_validacion(self):
        """Debe retornar ResultadoValidacion cuando validación es exitosa"""
        # Arrange
        resultado_negocio = {
            'success': True,
            'data': {'nit': '900123456', 'negocio': 'Test Negocio'}
        }
        codigo_negocio = "NEG001"

        # Mock de funciones de config
        with patch('app.validacion_negocios.validar_nit_administrativo') as mock_validar:
            with patch('app.validacion_negocios.detectar_impuestos_aplicables_por_codigo') as mock_detectar:
                # Setup mocks
                mock_validar.return_value = (True, 'Entidad Test', ['RETENCION_FUENTE'])
                mock_detectar.return_value = {
                    'aplica_estampilla_universidad': True,
                    'aplica_contribucion_obra_publica': False
                }

                # Act
                resultado = self.validador.validar(resultado_negocio, codigo_negocio)

                # Assert
                assert isinstance(resultado, ResultadoValidacion)
                assert resultado.nit_administrativo == '900123456'
                assert resultado.nombre_negocio == 'Test Negocio'
                assert 'RETENCION_FUENTE' in resultado.impuestos_a_procesar

    def test_nit_invalido_lanza_excepcion(self):
        """Debe lanzar HTTPException cuando NIT no es válido"""
        # Arrange
        resultado_negocio = {
            'success': True,
            'data': {'nit': '999999999', 'negocio': 'Test'}
        }
        codigo_negocio = "NEG001"

        with patch('app.validacion_negocios.validar_nit_administrativo') as mock_validar:
            mock_validar.return_value = (False, None, [])

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                self.validador.validar(resultado_negocio, codigo_negocio)

            assert exc_info.value.status_code == 400

    def test_impuestos_a_procesar_se_construye_correctamente(self):
        """Debe construir lista de impuestos según flags booleanos"""
        # Arrange
        resultado_negocio = {
            'success': True,
            'data': {'nit': '900123456', 'negocio': 'Test'}
        }
        codigo_negocio = "NEG001"

        with patch('app.validacion_negocios.validar_nit_administrativo') as mock_validar:
            with patch('app.validacion_negocios.detectar_impuestos_aplicables_por_codigo') as mock_detectar:
                with patch('app.validacion_negocios.nit_aplica_iva_reteiva') as mock_iva:
                    mock_validar.return_value = (True, 'Test', ['RETENCION_FUENTE'])
                    mock_detectar.return_value = {
                        'aplica_estampilla_universidad': True,
                        'aplica_contribucion_obra_publica': True
                    }
                    mock_iva.return_value = True

                    # Act
                    resultado = self.validador.validar(resultado_negocio, codigo_negocio)

                    # Assert
                    assert 'RETENCION_FUENTE' in resultado.impuestos_a_procesar
                    assert 'ESTAMPILLA_UNIVERSIDAD' in resultado.impuestos_a_procesar
                    assert 'CONTRIBUCION_OBRA_PUBLICA' in resultado.impuestos_a_procesar
                    assert 'IVA_RETEIVA' in resultado.impuestos_a_procesar


class TestResultadoValidacion:
    """Tests para ResultadoValidacion"""

    def test_puede_desempaquetar_como_tupla(self):
        """ResultadoValidacion debe ser desempaquetable como tupla para compatibilidad"""
        # Arrange
        resultado = ResultadoValidacion(
            impuestos_a_procesar=['RETENCION_FUENTE'],
            aplica_retencion=True,
            aplica_estampilla=False,
            aplica_obra_publica=False,
            aplica_iva=False,
            aplica_ica=False,
            aplica_timbre=False,
            aplica_tasa_prodeporte=False,
            nombre_negocio='Test',
            nit_administrativo='900123456',
            deteccion_impuestos={},
            nombre_entidad='Test Entity'
        )

        # Act
        (impuestos, retencion, estampilla, obra, iva, ica, timbre,
         prodeporte, nombre, nit, deteccion, entidad) = resultado

        # Assert
        assert impuestos == ['RETENCION_FUENTE']
        assert retencion is True
        assert nit == '900123456'