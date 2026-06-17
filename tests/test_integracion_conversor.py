"""
Test de integración del módulo Conversor con el Liquidador
SRP: Solo testea la integración del conversor con retefuente
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Agregar el directorio padre al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Liquidador.liquidador import LiquidadorRetencion
from Conversor import ConversorTRM
from Conversor.exceptions import TRMServiceError


class TestIntegracionConversor(unittest.TestCase):
    """Tests de integración del Conversor con el Liquidador"""

    def setUp(self):
        """Configuración inicial"""
        # Mock del db_manager
        self.mock_db_manager = Mock()
        self.mock_db_manager.obtener_conexion.return_value = Mock()

        self.liquidador = LiquidadorRetencion(
            estructura_contable=1,
            db_manager=self.mock_db_manager
        )

    def test_funcion_convertir_resultado_existe(self):
        """Test: verificar que la función de conversión existe"""
        self.assertTrue(hasattr(self.liquidador, '_convertir_resultado_usd_a_cop'))
        self.assertTrue(callable(getattr(self.liquidador, '_convertir_resultado_usd_a_cop')))

    def test_liquidar_factura_extranjera_acepta_tipoMoneda(self):
        """Test: verificar que liquidar_factura_extranjera_con_validaciones acepta tipoMoneda"""
        # Crear un análisis mínimo que falle en validación (para no hacer todo el flujo)
        analisis_minimo = {
            "pais_proveedor": "",  # Esto fallará en validación
            "conceptos_identificados": [],
            "valor_total": 0
        }

        # Llamar con tipoMoneda - debe aceptar el parámetro sin error
        try:
            resultado = self.liquidador.liquidar_factura_extranjera_con_validaciones(
                analisis_minimo,
                tipoMoneda="USD"
            )
            # Debería fallar por país vacío, no por parámetro tipoMoneda
            self.assertFalse(resultado.puede_liquidar)
        except TypeError as e:
            self.fail(f"No debería fallar por TypeError en tipoMoneda: {e}")

    def test_liquidar_retefuente_seguro_acepta_tipoMoneda(self):
        """Test: verificar que liquidar_retefuente_seguro acepta tipoMoneda"""
        # Análisis mínimo
        analisis_minimo = {
            "analisis": {
                "conceptos_identificados": [],
                "naturaleza_tercero": "persona_juridica"
            }
        }

        # Llamar con tipoMoneda
        try:
            resultado = self.liquidador.liquidar_retefuente_seguro(
                analisis_minimo,
                "900123456",
                tipoMoneda="USD"
            )
            # Verificar que no falla por el parámetro
            self.assertIsInstance(resultado, dict)
        except TypeError as e:
            self.fail(f"No debería fallar por TypeError en tipoMoneda: {e}")

    @patch('Liquidador.liquidador.ConversorTRM')
    def test_conversion_usd_llamada_cuando_tipoMoneda_es_USD(self, mock_conversor_class):
        """Test: verificar que se llama al conversor cuando tipoMoneda es USD"""
        # Mock del conversor
        mock_conversor = MagicMock()
        mock_conversor.__enter__.return_value = mock_conversor
        mock_conversor.__exit__.return_value = None
        mock_conversor.obtener_trm_valor.return_value = 3500.0
        mock_conversor_class.return_value = mock_conversor

        # Crear análisis completo que pase validaciones
        analisis_completo = {
            "pais_proveedor": "Estados Unidos",
            "conceptos_identificados": [
                {
                    "concepto_facturado": "Servicios técnicos",
                    "concepto": "Servicios técnicos",
                    "concepto_index": 0,
                    "base_gravable": 1000.0,  # 1000 USD
                    "naturaleza_tercero": "persona_juridica"
                }
            ],
            "valor_total": 1000.0,
            "observaciones": []
        }

        # Mock de db_manager para devolver concepto mapeado (v3.0 API)
        self.mock_db_manager.obtener_conceptos_extranjeros.return_value = {
            "success": True,
            "data": [
                {
                    "index": 0,
                    "nombre_concepto": "Servicios técnicos",
                    "tarifa_convenio": 10.0,
                    "tarifa_normal": 20.0,
                    "base_pesos": 0.0
                }
            ]
        }
        self.mock_db_manager.obtener_paises_con_convenio.return_value = {
            "success": True,
            "data": ["Estados Unidos", "Canada"]
        }

        # Ejecutar liquidación con USD
        resultado = self.liquidador.liquidar_factura_extranjera_con_validaciones(
            analisis_completo,
            tipoMoneda="USD"
        )

        # Verificar que se llamó al conversor
        self.assertTrue(mock_conversor.obtener_trm_valor.called)
        print(f"Valor retención (debería estar en COP): {resultado.valor_retencion}")

    def test_conversion_no_llamada_cuando_tipoMoneda_es_COP(self):
        """Test: verificar que NO se llama al conversor cuando tipoMoneda es COP"""
        with patch('Liquidador.liquidador.ConversorTRM') as mock_conversor_class:
            # Análisis mínimo que falla
            analisis_minimo = {
                "pais_proveedor": "",
                "conceptos_identificados": [],
                "valor_total": 0
            }

            # Ejecutar con COP
            resultado = self.liquidador.liquidar_factura_extranjera_con_validaciones(
                analisis_minimo,
                tipoMoneda="COP"
            )

            # Verificar que NO se llamó al conversor
            self.assertFalse(mock_conversor_class.called)

    @patch('Liquidador.liquidador.ConversorTRM')
    def test_manejo_error_TRM(self, mock_conversor_class):
        """Test: verificar manejo de errores cuando el servicio TRM falla"""
        # Mock del conversor que lanza error
        mock_conversor = MagicMock()
        mock_conversor.__enter__.return_value = mock_conversor
        mock_conversor.__exit__.return_value = None
        mock_conversor.obtener_trm_valor.side_effect = TRMServiceError("Servicio no disponible")
        mock_conversor_class.return_value = mock_conversor

        # Análisis completo
        analisis_completo = {
            "pais_proveedor": "Estados Unidos",
            "conceptos_identificados": [
                {
                    "concepto_facturado": "Servicios técnicos",
                    "concepto": "Servicios técnicos",
                    "concepto_index": 0,
                    "base_gravable": 1000.0,
                    "naturaleza_tercero": "persona_juridica"
                }
            ],
            "valor_total": 1000.0,
            "observaciones": []
        }

        # Mock de db_manager (v3.0 API)
        self.mock_db_manager.obtener_conceptos_extranjeros.return_value = {
            "success": True,
            "data": [
                {
                    "index": 0,
                    "nombre_concepto": "Servicios técnicos",
                    "tarifa_convenio": 10.0,
                    "tarifa_normal": 20.0,
                    "base_pesos": 0.0
                }
            ]
        }
        self.mock_db_manager.obtener_paises_con_convenio.return_value = {
            "success": True,
            "data": ["Estados Unidos"]
        }

        # Ejecutar - no debería fallar, sino agregar advertencia
        resultado = self.liquidador.liquidar_factura_extranjera_con_validaciones(
            analisis_completo,
            tipoMoneda="USD"
        )

        # Verificar que hay una advertencia sobre el error TRM
        mensajes = ' '.join(resultado.mensajes_error)
        self.assertIn("ADVERTENCIA", mensajes)
        self.assertIn("TRM", mensajes)


if __name__ == '__main__':
    unittest.main(verbosity=2)
