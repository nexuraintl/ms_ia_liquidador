"""
Tests para el modulo Conversor TRM
SRP: Solo testea la funcionalidad del conversor TRM
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import requests

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Conversor.conversor_trm import ConversorTRM
from Conversor.exceptions import TRMServiceError, TRMValidationError


class TestConversorTRM(unittest.TestCase):
    """Test cases para ConversorTRM"""

    def setUp(self):
        """Configuracion inicial para cada test"""
        self.conversor = ConversorTRM(timeout=10)

        # Respuesta SOAP de ejemplo valida
        self.respuesta_soap_valida = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <ns2:queryTCRMResponse xmlns:ns2="http://action.trm.services.generic.action.superfinanciera.nexura.sc.com.co/">
            <return>
                <id>2521951</id>
                <unit>COP</unit>
                <validityFrom>2020-03-06T00:00:00-05:00</validityFrom>
                <validityTo>2020-03-06T00:00:00-05:00</validityTo>
                <value>3468.78</value>
                <success>true</success>
            </return>
        </ns2:queryTCRMResponse>
    </soap:Body>
</soap:Envelope>"""

    def tearDown(self):
        """Limpieza despues de cada test"""
        self.conversor.cerrar_sesion()

    # ========== TESTS DE CONSTRUCCION DE REQUESTS ==========

    def test_construir_soap_request_sin_fecha(self):
        """Test: construir SOAP request sin fecha"""
        request = self.conversor._construir_soap_request()

        self.assertIn('queryTCRM', request)
        self.assertIn('soapenv:Envelope', request)
        self.assertNotIn('tcrmQueryAssociatedDate', request)

    def test_construir_soap_request_con_fecha(self):
        """Test: construir SOAP request con fecha especifica"""
        fecha = "2020-03-06"
        request = self.conversor._construir_soap_request(fecha)

        self.assertIn('queryTCRM', request)
        self.assertIn('soapenv:Envelope', request)
        self.assertIn(f'<tcrmQueryAssociatedDate>{fecha}</tcrmQueryAssociatedDate>', request)

    # ========== TESTS DE VALIDACION DE FECHA ==========

    def test_validar_formato_fecha_valido(self):
        """Test: validar formato de fecha correcto"""
        self.assertTrue(self.conversor._validar_formato_fecha("2020-03-06"))
        self.assertTrue(self.conversor._validar_formato_fecha("2023-12-31"))
        self.assertTrue(self.conversor._validar_formato_fecha("2024-01-01"))

    def test_validar_formato_fecha_invalido(self):
        """Test: validar formato de fecha incorrecto"""
        with self.assertRaises(TRMValidationError):
            self.conversor._validar_formato_fecha("06-03-2020")  # Formato incorrecto

        with self.assertRaises(TRMValidationError):
            self.conversor._validar_formato_fecha("2020/03/06")  # Separador incorrecto

        with self.assertRaises(TRMValidationError):
            self.conversor._validar_formato_fecha("2020-13-01")  # Mes invalido

        with self.assertRaises(TRMValidationError):
            self.conversor._validar_formato_fecha("no-es-fecha")  # No es fecha

    # ========== TESTS DE EXTRACCION DE RESPUESTA ==========

    def test_extraer_trm_de_respuesta_valida(self):
        """Test: extraer TRM de respuesta XML valida"""
        resultado = self.conversor._extraer_trm_de_respuesta(self.respuesta_soap_valida)

        self.assertEqual(resultado['id'], '2521951')
        self.assertEqual(resultado['unit'], 'COP')
        self.assertEqual(resultado['value'], 3468.78)
        self.assertEqual(resultado['success'], 'true')
        self.assertIn('validityFrom', resultado)
        self.assertIn('validityTo', resultado)

    def test_extraer_trm_de_respuesta_invalida(self):
        """Test: error al extraer TRM de respuesta XML invalida"""
        respuesta_invalida = """<?xml version="1.0"?><invalid>data</invalid>"""

        with self.assertRaises(TRMServiceError):
            self.conversor._extraer_trm_de_respuesta(respuesta_invalida)

    def test_extraer_trm_respuesta_no_exitosa(self):
        """Test: manejar respuesta con success=false"""
        respuesta_error = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <ns2:queryTCRMResponse xmlns:ns2="http://action.trm.services.generic.action.superfinanciera.nexura.sc.com.co/">
            <return>
                <success>false</success>
            </return>
        </ns2:queryTCRMResponse>
    </soap:Body>
</soap:Envelope>"""

        with self.assertRaises(TRMServiceError):
            self.conversor._extraer_trm_de_respuesta(respuesta_error)

    def test_extraer_trm_valor_invalido(self):
        """Test: error cuando el valor de TRM no es numerico"""
        respuesta_valor_invalido = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <ns2:queryTCRMResponse xmlns:ns2="http://action.trm.services.generic.action.superfinanciera.nexura.sc.com.co/">
            <return>
                <id>123</id>
                <unit>COP</unit>
                <value>not-a-number</value>
                <success>true</success>
            </return>
        </ns2:queryTCRMResponse>
    </soap:Body>
</soap:Envelope>"""

        with self.assertRaises(TRMServiceError):
            self.conversor._extraer_trm_de_respuesta(respuesta_valor_invalido)

    # ========== TESTS DE OBTENCION DE TRM (MOCKED) ==========

    @patch('Conversor.conversor_trm.requests.Session.post')
    def test_obtener_trm_exitoso(self, mock_post):
        """Test: obtener TRM exitosamente"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.respuesta_soap_valida
        mock_post.return_value = mock_response

        resultado = self.conversor.obtener_trm()

        self.assertEqual(resultado['value'], 3468.78)
        self.assertEqual(resultado['unit'], 'COP')
        self.assertTrue(mock_post.called)

    @patch('Conversor.conversor_trm.requests.Session.post')
    def test_obtener_trm_con_fecha(self, mock_post):
        """Test: obtener TRM con fecha especifica"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.respuesta_soap_valida
        mock_post.return_value = mock_response

        resultado = self.conversor.obtener_trm("2020-03-06")

        self.assertEqual(resultado['value'], 3468.78)
        self.assertTrue(mock_post.called)

        # Verificar que se paso la fecha en el request
        call_args = mock_post.call_args
        request_data = call_args[1]['data'].decode('utf-8')
        self.assertIn('2020-03-06', request_data)

    @patch('Conversor.conversor_trm.requests.Session.post')
    def test_obtener_trm_valor_solo(self, mock_post):
        """Test: obtener solo el valor de la TRM"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.respuesta_soap_valida
        mock_post.return_value = mock_response

        valor = self.conversor.obtener_trm_valor()

        self.assertEqual(valor, 3468.78)
        self.assertIsInstance(valor, float)

    # ========== TESTS DE MANEJO DE ERRORES HTTP ==========

    @patch('Conversor.conversor_trm.requests.Session.post')
    def test_obtener_trm_timeout(self, mock_post):
        """Test: manejo de timeout en la peticion"""
        mock_post.side_effect = requests.exceptions.Timeout()

        with self.assertRaises(TRMServiceError) as context:
            self.conversor.obtener_trm()

        self.assertIn('Timeout', str(context.exception))

    @patch('Conversor.conversor_trm.requests.Session.post')
    def test_obtener_trm_ssl_error(self, mock_post):
        """Test: manejo de error SSL"""
        mock_post.side_effect = requests.exceptions.SSLError("Certificate error")

        with self.assertRaises(TRMServiceError) as context:
            self.conversor.obtener_trm()

        self.assertIn('SSL', str(context.exception))

    @patch('Conversor.conversor_trm.requests.Session.post')
    def test_obtener_trm_connection_error(self, mock_post):
        """Test: manejo de error de conexion"""
        mock_post.side_effect = requests.exceptions.ConnectionError("No connection")

        with self.assertRaises(TRMServiceError) as context:
            self.conversor.obtener_trm()

        self.assertIn('conexion', str(context.exception))

    @patch('Conversor.conversor_trm.requests.Session.post')
    def test_obtener_trm_http_error(self, mock_post):
        """Test: manejo de error HTTP"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        with self.assertRaises(TRMServiceError) as context:
            self.conversor.obtener_trm()

        self.assertIn('HTTP', str(context.exception))

    # ========== TESTS DE CONVERSION DE MONEDA ==========

    @patch('Conversor.conversor_trm.requests.Session.post')
    def test_convertir_usd_a_cop(self, mock_post):
        """Test: convertir USD a COP"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.respuesta_soap_valida
        mock_post.return_value = mock_response

        # Convertir 100 USD a COP (TRM = 3468.78)
        monto_cop = self.conversor.convertir_usd_a_cop(100.0)

        self.assertEqual(monto_cop, 346878.0)

    @patch('Conversor.conversor_trm.requests.Session.post')
    def test_convertir_cop_a_usd(self, mock_post):
        """Test: convertir COP a USD"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.respuesta_soap_valida
        mock_post.return_value = mock_response

        # Convertir 3468780 COP a USD (TRM = 3468.78)
        monto_usd = self.conversor.convertir_cop_a_usd(3468780.0)

        self.assertAlmostEqual(monto_usd, 1000.0, places=2)

    def test_convertir_usd_negativo(self):
        """Test: error al convertir monto negativo USD"""
        with self.assertRaises(TRMValidationError):
            self.conversor.convertir_usd_a_cop(-100.0)

    def test_convertir_cop_negativo(self):
        """Test: error al convertir monto negativo COP"""
        with self.assertRaises(TRMValidationError):
            self.conversor.convertir_cop_a_usd(-100.0)

    @patch('Conversor.conversor_trm.requests.Session.post')
    def test_convertir_cero(self, mock_post):
        """Test: convertir monto cero"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.respuesta_soap_valida
        mock_post.return_value = mock_response

        self.assertEqual(self.conversor.convertir_usd_a_cop(0.0), 0.0)
        self.assertEqual(self.conversor.convertir_cop_a_usd(0.0), 0.0)

    # ========== TESTS DE CONTEXT MANAGER ==========

    @patch('Conversor.conversor_trm.requests.Session.post')
    def test_context_manager(self, mock_post):
        """Test: uso como context manager"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = self.respuesta_soap_valida
        mock_post.return_value = mock_response

        with ConversorTRM() as conversor:
            valor = conversor.obtener_trm_valor()
            self.assertEqual(valor, 3468.78)

        # Verificar que la sesion se cerro
        # (esto es dificil de testear directamente, pero verificamos que no falle)

    # ========== TESTS DE CONFIGURACION ==========

    def test_timeout_personalizado(self):
        """Test: configurar timeout personalizado"""
        conversor = ConversorTRM(timeout=60)
        self.assertEqual(conversor.timeout, 60)
        conversor.cerrar_sesion()

    def test_headers_correctos(self):
        """Test: verificar headers de la sesion"""
        self.assertEqual(
            self.conversor.session.headers['Content-Type'],
            'text/xml; charset=utf-8'
        )


class TestConversorTRMIntegracion(unittest.TestCase):
    """
    Tests de integracion con el servicio real
    NOTA: Estos tests requieren conexion a internet y pueden fallar si el servicio esta caido
    """

    @unittest.skip("Test de integracion - solo ejecutar manualmente")
    def test_obtener_trm_real_actual(self):
        """Test de integracion: obtener TRM actual del servicio real"""
        with ConversorTRM(timeout=30) as conversor:
            resultado = conversor.obtener_trm()

            self.assertIn('value', resultado)
            self.assertIsInstance(resultado['value'], float)
            self.assertGreater(resultado['value'], 0)
            self.assertEqual(resultado['unit'], 'COP')
            self.assertEqual(resultado['success'], 'true')

            print(f"TRM actual: {resultado['value']}")

    @unittest.skip("Test de integracion - solo ejecutar manualmente")
    def test_obtener_trm_real_historica(self):
        """Test de integracion: obtener TRM historica del servicio real"""
        with ConversorTRM(timeout=30) as conversor:
            # Fecha conocida
            resultado = conversor.obtener_trm("2020-03-06")

            self.assertIn('value', resultado)
            self.assertIsInstance(resultado['value'], float)
            self.assertGreater(resultado['value'], 0)
            self.assertEqual(resultado['unit'], 'COP')

            print(f"TRM 2020-03-06: {resultado['value']}")

    @unittest.skip("Test de integracion - solo ejecutar manualmente")
    def test_conversion_real(self):
        """Test de integracion: conversion de moneda con TRM real"""
        with ConversorTRM(timeout=30) as conversor:
            # Convertir 100 USD a COP
            monto_cop = conversor.convertir_usd_a_cop(100.0)
            self.assertGreater(monto_cop, 0)

            # Convertir de vuelta a USD
            monto_usd = conversor.convertir_cop_a_usd(monto_cop)
            self.assertAlmostEqual(monto_usd, 100.0, places=2)

            print(f"100 USD = {monto_cop} COP")


if __name__ == '__main__':
    unittest.main()
