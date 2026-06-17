"""
Suite de tests para app.validar_iva_reteiva.

Tests unitarios y de integracion para ValidadorIVAReteIVA con cobertura completa
de edge cases y validacion de principios SOLID.

Autor: Sistema Preliquidador
Version: 1.0
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.validar_iva_reteiva import ValidadorIVAReteIVA, validar_iva_reteiva


# ============================================================================
# TESTS UNITARIOS - MÉTODOS INDIVIDUALES
# ============================================================================

class TestValidadorIVAReteIVAInit(unittest.TestCase):
    """Tests para __init__ (constructor con inyeccion de dependencias)."""

    def test_init_sin_dependencias(self):
        """Test: Constructor sin inyectar liquidador (lazy initialization)."""
        validador = ValidadorIVAReteIVA()

        self.assertIsNone(validador.liquidador_iva)
        self.assertIsNotNone(validador.logger)

    def test_init_con_liquidador_inyectado(self):
        """Test: Constructor con liquidador inyectado (DIP)."""
        mock_liquidador = Mock()
        validador = ValidadorIVAReteIVA(liquidador_iva=mock_liquidador)

        self.assertEqual(validador.liquidador_iva, mock_liquidador)
        self.assertIsNotNone(validador.logger)

    def test_init_verifica_tipo_logger(self):
        """Test: Logger es instancia correcta."""
        validador = ValidadorIVAReteIVA()

        self.assertEqual(validador.logger.name, 'app.validar_iva_reteiva')

    def test_init_liquidador_none_explicitamente(self):
        """Test: Edge case - liquidador None explicitamente."""
        validador = ValidadorIVAReteIVA(liquidador_iva=None)

        self.assertIsNone(validador.liquidador_iva)


class TestDebeProcesarIVAReteIVA(unittest.TestCase):
    """Tests para _debe_procesar_iva_reteiva."""

    def setUp(self):
        self.validador = ValidadorIVAReteIVA()

    def test_debe_procesar_con_datos_y_flag(self):
        """Test: Debe procesar cuando hay datos y aplica_iva es True."""
        resultados = {"iva_reteiva": {"valor": 1000}}

        resultado = self.validador._debe_procesar_iva_reteiva(resultados, True)

        self.assertTrue(resultado)

    def test_no_debe_procesar_sin_datos(self):
        """Test: No debe procesar si no hay datos en resultados_analisis."""
        resultados = {}

        resultado = self.validador._debe_procesar_iva_reteiva(resultados, True)

        self.assertFalse(resultado)

    def test_no_debe_procesar_sin_flag(self):
        """Test: No debe procesar si aplica_iva es False."""
        resultados = {"iva_reteiva": {"valor": 1000}}

        resultado = self.validador._debe_procesar_iva_reteiva(resultados, False)

        self.assertFalse(resultado)

    def test_edge_case_datos_con_flag_false(self):
        """Test: Edge case - tiene datos pero aplica_iva en False."""
        resultados = {"iva_reteiva": {"valor": 5000}}

        resultado = self.validador._debe_procesar_iva_reteiva(resultados, False)

        self.assertFalse(resultado)


class TestManejarCasoEspecial(unittest.TestCase):
    """Tests para _manejar_caso_especial."""

    def setUp(self):
        self.validador = ValidadorIVAReteIVA()

    @patch('app.validar_iva_reteiva.crear_resultado_recurso_extranjero_iva')
    @patch('app.validar_iva_reteiva.logging.getLogger')
    def test_manejar_recurso_extranjero(self, mock_logger, mock_crear_resultado):
        """Test: Maneja caso especial de recurso extranjero."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        mock_crear_resultado.return_value = {
            "iva_reteiva": {
                "aplica": False,
                "estado": "recurso_fuente_extranjera",
                "valor_iva_identificado": 0.0,
                "valor_reteiva": 0.0
            }
        }

        resultado = self.validador._manejar_caso_especial(True, True)

        self.assertIsNotNone(resultado)
        self.assertIn("aplica", resultado)
        self.assertEqual(resultado["aplica"], False)
        self.assertEqual(resultado["estado"], "recurso_fuente_extranjera")
        mock_logger_instance.info.assert_called()

    def test_no_aplica_sin_flags(self):
        """Test: Retorna None cuando ningún flag está activo."""
        resultado = self.validador._manejar_caso_especial(False, False)

        self.assertIsNone(resultado)

    def test_no_aplica_solo_con_aplica_iva(self):
        """Test: Retorna None cuando solo aplica_iva es True."""
        resultado = self.validador._manejar_caso_especial(True, False)

        self.assertIsNone(resultado)

    def test_no_aplica_solo_con_recurso_extranjero(self):
        """Test: Retorna None cuando solo es_recurso_extranjero es True."""
        resultado = self.validador._manejar_caso_especial(False, True)

        self.assertIsNone(resultado)


class TestPrepararClasificacionInicial(unittest.TestCase):
    """Tests para _preparar_clasificacion_inicial."""

    def setUp(self):
        self.validador = ValidadorIVAReteIVA()

    def test_preparar_con_facturacion_extranjera(self):
        """Test: Prepara clasificacion con facturacion extranjera."""
        resultado = self.validador._preparar_clasificacion_inicial(True)

        self.assertEqual(resultado, {"es_facturacion_extranjera": True})

    def test_preparar_sin_facturacion_extranjera(self):
        """Test: Prepara clasificacion sin facturacion extranjera."""
        resultado = self.validador._preparar_clasificacion_inicial(False)

        self.assertEqual(resultado, {"es_facturacion_extranjera": False})


class TestEjecutarLiquidacion(unittest.TestCase):
    """Tests para _ejecutar_liquidacion."""

    def setUp(self):
        self.mock_liquidador = Mock()
        self.validador = ValidadorIVAReteIVA(liquidador_iva=self.mock_liquidador)

    def test_ejecutar_liquidacion_llama_metodo_correcto(self):
        """Test: Ejecuta liquidacion llamando al método correcto del liquidador."""
        analisis_gemini = {"iva": 1000, "reteiva": 100}
        clasificacion = {"es_facturacion_extranjera": False}
        self.mock_liquidador.liquidar_iva_completo.return_value = {
            "iva_reteiva": {"valor_iva_identificado": 1000}
        }

        resultado = self.validador._ejecutar_liquidacion(
            analisis_gemini,
            clasificacion,
            "900123456",
            "COP"
        )

        self.mock_liquidador.liquidar_iva_completo.assert_called_once_with(
            analisis_gemini=analisis_gemini,
            clasificacion_inicial=clasificacion,
            nit_administrativo="900123456",
            tipoMoneda="COP"
        )
        self.assertIn("iva_reteiva", resultado)

    def test_ejecutar_liquidacion_con_moneda_usd(self):
        """Test: Ejecuta liquidacion con moneda USD."""
        self.mock_liquidador.liquidar_iva_completo.return_value = {"iva_reteiva": {}}

        self.validador._ejecutar_liquidacion(
            {"iva": 1000},
            {"es_facturacion_extranjera": True},
            "900123456",
            "USD"
        )

        args = self.mock_liquidador.liquidar_iva_completo.call_args
        self.assertEqual(args.kwargs["tipoMoneda"], "USD")


class TestProcesarResultado(unittest.TestCase):
    """Tests para _procesar_resultado."""

    def setUp(self):
        self.validador = ValidadorIVAReteIVA()

    def test_procesar_resultado_extrae_iva_reteiva(self):
        """Test: Procesa resultado y extrae correctamente iva_reteiva."""
        resultado_completo = {
            "iva_reteiva": {
                "aplica": True,
                "valor_iva_identificado": 19000.0,
                "valor_reteiva": 2850.0
            }
        }

        with patch.object(self.validador, '_log_resultados'):
            resultado = self.validador._procesar_resultado(resultado_completo)

        self.assertEqual(resultado["valor_iva_identificado"], 19000.0)
        self.assertEqual(resultado["valor_reteiva"], 2850.0)

    def test_procesar_resultado_sin_clave_iva_reteiva(self):
        """Test: Edge case - resultado_completo sin clave 'iva_reteiva'."""
        resultado_completo = {"otro_campo": "valor"}

        with patch.object(self.validador, '_log_resultados'):
            resultado = self.validador._procesar_resultado(resultado_completo)

        self.assertEqual(resultado, {})

    def test_procesar_resultado_llama_log(self):
        """Test: Procesar resultado llama al método de logging."""
        resultado_completo = {"iva_reteiva": {"valor_iva_identificado": 1000}}

        with patch.object(self.validador, '_log_resultados') as mock_log:
            self.validador._procesar_resultado(resultado_completo)

            mock_log.assert_called_once_with({"valor_iva_identificado": 1000})


class TestLogResultados(unittest.TestCase):
    """Tests para _log_resultados."""

    def setUp(self):
        self.validador = ValidadorIVAReteIVA()

    @patch('app.validar_iva_reteiva.logging.getLogger')
    def test_log_resultados_con_valores(self, mock_logger):
        """Test: Logging con valores de IVA y ReteIVA."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        resultado = {
            "valor_iva_identificado": 19000.0,
            "valor_reteiva": 2850.0
        }

        self.validador._log_resultados(resultado)

        self.assertEqual(mock_logger_instance.info.call_count, 2)
        calls = [call[0][0] for call in mock_logger_instance.info.call_args_list]
        self.assertIn("IVA identificado", calls[0])
        self.assertIn("19,000.00", calls[0])
        self.assertIn("ReteIVA liquidada", calls[1])
        self.assertIn("2,850.00", calls[1])

    @patch('app.validar_iva_reteiva.logging.getLogger')
    def test_log_resultados_valores_cero(self, mock_logger):
        """Test: Logging con valores en cero."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        resultado = {
            "valor_iva_identificado": 0.0,
            "valor_reteiva": 0.0
        }

        self.validador._log_resultados(resultado)

        calls = [call[0][0] for call in mock_logger_instance.info.call_args_list]
        self.assertIn("0.00", calls[0])
        self.assertIn("0.00", calls[1])

    @patch('app.validar_iva_reteiva.logging.getLogger')
    def test_log_resultados_sin_claves(self, mock_logger):
        """Test: Edge case - resultado sin claves esperadas."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        resultado = {}

        self.validador._log_resultados(resultado)

        # Debe loguear valores por defecto (0.0)
        self.assertEqual(mock_logger_instance.info.call_count, 2)


class TestManejarError(unittest.TestCase):
    """Tests para _manejar_error."""

    def setUp(self):
        self.validador = ValidadorIVAReteIVA()

    @patch('app.validar_iva_reteiva.logging.getLogger')
    def test_manejar_error_estructura_correcta(self, mock_logger):
        """Test: Manejo de error retorna estructura correcta."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        excepcion = Exception("Error de prueba")

        resultado = self.validador._manejar_error(excepcion)

        self.assertEqual(resultado["error"], "Error de prueba")
        self.assertEqual(resultado["aplica"], False)
        mock_logger_instance.error.assert_called_once()

    @patch('app.validar_iva_reteiva.logging.getLogger')
    def test_manejar_error_loguea_mensaje(self, mock_logger):
        """Test: Manejo de error loguea el mensaje correcto."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        excepcion = Exception("Error técnico")

        self.validador._manejar_error(excepcion)

        call_args = mock_logger_instance.error.call_args[0][0]
        self.assertIn("Error liquidando IVA/ReteIVA", call_args)
        self.assertIn("Error técnico", call_args)


class TestProcesarLiquidacion(unittest.IsolatedAsyncioTestCase):
    """Tests para _procesar_liquidacion."""

    async def asyncSetUp(self):
        self.mock_liquidador = Mock()
        self.validador = ValidadorIVAReteIVA(liquidador_iva=self.mock_liquidador)

    async def test_procesar_liquidacion_exitosa(self):
        """Test: Procesamiento exitoso con liquidador inyectado."""
        resultados = {"iva_reteiva": {"iva": 19000}}
        self.mock_liquidador.liquidar_iva_completo.return_value = {
            "iva_reteiva": {
                "aplica": True,
                "valor_iva_identificado": 19000.0,
                "valor_reteiva": 2850.0
            }
        }

        with patch.object(self.validador, '_log_resultados'):
            resultado = await self.validador._procesar_liquidacion(
                resultados, False, "900123456", "COP"
            )

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["valor_iva_identificado"], 19000.0)
        self.mock_liquidador.liquidar_iva_completo.assert_called_once()

    async def test_lazy_initialization_liquidador(self):
        """Test: Lazy initialization cuando no se inyectó liquidador."""
        validador_sin_liquidador = ValidadorIVAReteIVA()
        resultados = {"iva_reteiva": {"iva": 1000}}

        with patch('app.validar_iva_reteiva.LiquidadorIVA') as MockLiquidador:
            mock_instance = Mock()
            mock_instance.liquidar_iva_completo.return_value = {"iva_reteiva": {}}
            MockLiquidador.return_value = mock_instance

            with patch.object(validador_sin_liquidador, '_log_resultados'):
                await validador_sin_liquidador._procesar_liquidacion(
                    resultados, False, "900123456", "COP"
                )

            MockLiquidador.assert_called_once()
            self.assertIsNotNone(validador_sin_liquidador.liquidador_iva)

    async def test_procesar_con_facturacion_extranjera(self):
        """Test: Procesa correctamente con facturacion extranjera."""
        resultados = {"iva_reteiva": {"iva": 1000}}
        self.mock_liquidador.liquidar_iva_completo.return_value = {"iva_reteiva": {}}

        with patch.object(self.validador, '_log_resultados'):
            await self.validador._procesar_liquidacion(
                resultados, True, "900123456", "USD"
            )

        # Verificar que se pasó es_facturacion_extranjera=True
        args = self.mock_liquidador.liquidar_iva_completo.call_args
        self.assertTrue(args.kwargs["clasificacion_inicial"]["es_facturacion_extranjera"])


# ============================================================================
# TESTS DE INTEGRACIÓN - ORQUESTADOR
# ============================================================================

class TestValidarOrquestador(unittest.IsolatedAsyncioTestCase):
    """Tests de integracion para el metodo validar (orquestador)."""

    async def asyncSetUp(self):
        self.mock_liquidador = Mock()
        self.validador = ValidadorIVAReteIVA(liquidador_iva=self.mock_liquidador)

    async def test_validar_flujo_completo_exitoso(self):
        """Test: Flujo completo exitoso con IVA y ReteIVA."""
        resultados = {"iva_reteiva": {"iva": 19000}}
        self.mock_liquidador.liquidar_iva_completo.return_value = {
            "iva_reteiva": {
                "aplica": True,
                "valor_iva_identificado": 19000.0,
                "valor_reteiva": 2850.0
            }
        }

        with patch.object(self.validador, '_log_resultados'):
            resultado = await self.validador.validar(
                resultados, True, False, False, "900123456", "COP"
            )

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["valor_iva_identificado"], 19000.0)

    async def test_validar_sin_datos_retorna_none(self):
        """Test: Retorna None cuando no hay datos para procesar."""
        resultados = {}

        resultado = await self.validador.validar(
            resultados, True, False, False, "900123456", "COP"
        )

        self.assertIsNone(resultado)

    async def test_validar_sin_flag_retorna_none(self):
        """Test: Retorna None cuando aplica_iva es False."""
        resultados = {"iva_reteiva": {"iva": 1000}}

        resultado = await self.validador.validar(
            resultados, False, False, False, "900123456", "COP"
        )

        self.assertIsNone(resultado)

    async def test_validar_maneja_excepcion_del_liquidador(self):
        """Test: Maneja excepción lanzada por el liquidador."""
        resultados = {"iva_reteiva": {"iva": 1000}}
        self.mock_liquidador.liquidar_iva_completo.side_effect = Exception("Error de liquidación")

        with patch.object(self.validador.logger, 'error'):
            resultado = await self.validador.validar(
                resultados, True, False, False, "900123456", "COP"
            )

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["aplica"], False)
        self.assertIn("Error de liquidación", resultado["error"])

    async def test_validar_recurso_extranjero(self):
        """Test: Maneja correctamente el caso de recurso extranjero."""
        resultados = {}

        with patch('app.validar_iva_reteiva.crear_resultado_recurso_extranjero_iva') as mock_crear:
            mock_crear.return_value = {
                "iva_reteiva": {
                    "aplica": False,
                    "estado": "recurso_fuente_extranjera"
                }
            }

            with patch.object(self.validador.logger, 'info'):
                resultado = await self.validador.validar(
                    resultados, True, True, False, "900123456", "COP"
                )

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["aplica"], False)
        self.assertEqual(resultado["estado"], "recurso_fuente_extranjera")


# ============================================================================
# TESTS WRAPPER FUNCTION
# ============================================================================

class TestValidarIVAReteIVAWrapper(unittest.IsolatedAsyncioTestCase):
    """Tests para la funcion wrapper validar_iva_reteiva."""

    async def test_wrapper_instancia_validador_y_delega(self):
        """Test: Wrapper instancia ValidadorIVAReteIVA y delega correctamente."""
        resultados = {"iva_reteiva": {"iva": 1000}}

        with patch('app.validar_iva_reteiva.ValidadorIVAReteIVA') as MockValidador:
            mock_instance = AsyncMock()
            mock_instance.validar = AsyncMock(return_value={"test": "result"})
            MockValidador.return_value = mock_instance

            resultado = await validar_iva_reteiva(
                resultados, True, False, False, "900123456", "COP"
            )

            MockValidador.assert_called_once()
            mock_instance.validar.assert_called_once_with(
                resultados_analisis=resultados,
                aplica_iva=True,
                es_recurso_extranjero=False,
                es_facturacion_extranjera=False,
                nit_administrativo="900123456",
                tipoMoneda="COP"
            )
            self.assertEqual(resultado, {"test": "result"})

    async def test_wrapper_retorna_none_cuando_validador_retorna_none(self):
        """Test: Wrapper retorna None cuando validador retorna None."""
        resultados = {}

        with patch('app.validar_iva_reteiva.ValidadorIVAReteIVA') as MockValidador:
            mock_instance = AsyncMock()
            mock_instance.validar = AsyncMock(return_value=None)
            MockValidador.return_value = mock_instance

            resultado = await validar_iva_reteiva(
                resultados, False, False, False, "900123456", "COP"
            )

            self.assertIsNone(resultado)


# ============================================================================
# TESTS DE EDGE CASES COMPLETOS
# ============================================================================

class TestEdgeCasesCompletos(unittest.IsolatedAsyncioTestCase):
    """Tests de edge cases complejos y situaciones extremas."""

    async def asyncSetUp(self):
        self.validador = ValidadorIVAReteIVA()

    async def test_edge_resultados_analisis_none(self):
        """Test: Edge case - resultados_analisis es None."""
        with self.assertRaises(TypeError):
            await self.validador.validar(None, True, False, False, "900123456", "COP")

    async def test_edge_resultados_analisis_vacio(self):
        """Test: Edge case - resultados_analisis dict vacío."""
        resultado = await self.validador.validar({}, True, False, False, "900123456", "COP")

        self.assertIsNone(resultado)

    async def test_edge_nit_vacio(self):
        """Test: Edge case - nit_administrativo es string vacío."""
        resultados = {"iva_reteiva": {"iva": 1000}}
        mock_liquidador = Mock()
        mock_liquidador.liquidar_iva_completo.return_value = {"iva_reteiva": {}}
        self.validador.liquidador_iva = mock_liquidador

        with patch.object(self.validador, '_log_resultados'):
            await self.validador.validar(
                resultados, True, False, False, "", "COP"
            )

        # Debe procesar normalmente con NIT vacío
        mock_liquidador.liquidar_iva_completo.assert_called_once()

    async def test_edge_tipo_moneda_invalida(self):
        """Test: Edge case - tipoMoneda con valor no estándar."""
        resultados = {"iva_reteiva": {"iva": 1000}}
        mock_liquidador = Mock()
        mock_liquidador.liquidar_iva_completo.return_value = {"iva_reteiva": {}}
        self.validador.liquidador_iva = mock_liquidador

        with patch.object(self.validador, '_log_resultados'):
            await self.validador.validar(
                resultados, True, False, False, "900123456", "EUR"
            )

        # Debe pasar tal cual (validación upstream)
        args = mock_liquidador.liquidar_iva_completo.call_args
        self.assertEqual(args.kwargs["tipoMoneda"], "EUR")

    async def test_edge_liquidador_retorna_estructura_incompleta(self):
        """Test: Edge case - liquidador retorna dict sin iva_reteiva."""
        resultados = {"iva_reteiva": {"iva": 1000}}
        mock_liquidador = Mock()
        mock_liquidador.liquidar_iva_completo.return_value = {
            "otro_campo": "valor inesperado"
        }
        self.validador.liquidador_iva = mock_liquidador

        with patch.object(self.validador, '_log_resultados'):
            resultado = await self.validador.validar(
                resultados, True, False, False, "900123456", "COP"
            )

        # Debe retornar dict vacío
        self.assertEqual(resultado, {})

    async def test_edge_valores_negativos(self):
        """Test: Edge case - liquidador retorna valores negativos."""
        resultados = {"iva_reteiva": {"iva": 1000}}
        mock_liquidador = Mock()
        mock_liquidador.liquidar_iva_completo.return_value = {
            "iva_reteiva": {
                "valor_iva_identificado": -19000.0,
                "valor_reteiva": -2850.0
            }
        }
        self.validador.liquidador_iva = mock_liquidador

        with patch.object(self.validador, '_log_resultados'):
            resultado = await self.validador.validar(
                resultados, True, False, False, "900123456", "COP"
            )

        # Debe procesar normalmente (validaciones upstream)
        self.assertEqual(resultado["valor_iva_identificado"], -19000.0)

    async def test_edge_ambos_flags_true(self):
        """Test: Edge case - aplica_iva y es_recurso_extranjero ambos True."""
        resultados = {}

        with patch('app.validar_iva_reteiva.crear_resultado_recurso_extranjero_iva') as mock_crear:
            mock_crear.return_value = {"iva_reteiva": {"aplica": False}}

            with patch.object(self.validador.logger, 'info'):
                resultado = await self.validador.validar(
                    resultados, True, True, False, "900123456", "COP"
                )

        # Debe manejar como recurso extranjero
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["aplica"], False)


# ============================================================================
# SUITE Y RUNNER
# ============================================================================

def suite():
    """Crear suite de tests."""
    suite = unittest.TestSuite()

    # Tests unitarios
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestValidadorIVAReteIVAInit))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDebeProcesarIVAReteIVA))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestManejarCasoEspecial))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPrepararClasificacionInicial))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestEjecutarLiquidacion))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestProcesarResultado))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestLogResultados))
    suite.addTests(unittest.TestLoader().loadTestCase(TestManejarError))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestProcesarLiquidacion))

    # Tests de integracion
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestValidarOrquestador))

    # Tests wrapper
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestValidarIVAReteIVAWrapper))

    # Tests edge cases
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestEdgeCasesCompletos))

    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
