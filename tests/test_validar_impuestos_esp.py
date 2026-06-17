"""
Suite de tests para app.validar_impuestos_esp.

Tests unitarios y de integracion para ValidadorImpuestosEspeciales con cobertura completa
de edge cases y validacion de principios SOLID.

Autor: Sistema Preliquidador
Version: 1.0
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
from app.validar_impuestos_esp import ValidadorImpuestosEspeciales, validar_impuestos_especiales


# ============================================================================
# TESTS UNITARIOS - MÉTODOS INDIVIDUALES
# ============================================================================

class TestValidadorImpuestosEspecialesInit(unittest.TestCase):
    """Tests para __init__ (constructor con inyeccion de dependencias)."""

    def test_init_sin_dependencias(self):
        """Test: Constructor sin inyectar liquidador (lazy initialization)."""
        validador = ValidadorImpuestosEspeciales()

        self.assertIsNone(validador.liquidador_estampilla)
        self.assertIsNotNone(validador.logger)

    def test_init_con_liquidador_inyectado(self):
        """Test: Constructor con liquidador inyectado (DIP)."""
        mock_liquidador = Mock()
        validador = ValidadorImpuestosEspeciales(liquidador_estampilla=mock_liquidador)

        self.assertEqual(validador.liquidador_estampilla, mock_liquidador)
        self.assertIsNotNone(validador.logger)

    def test_init_verifica_tipo_logger(self):
        """Test: Logger es instancia correcta."""
        validador = ValidadorImpuestosEspeciales()

        self.assertEqual(validador.logger.name, 'app.validar_impuestos_esp')

    def test_init_liquidador_none_explicitamente(self):
        """Test: Edge case - liquidador None explicitamente."""
        validador = ValidadorImpuestosEspeciales(liquidador_estampilla=None)

        self.assertIsNone(validador.liquidador_estampilla)


class TestDebeProcesarImpuestosEspeciales(unittest.TestCase):
    """Tests para _debe_procesar_impuestos_especiales."""

    def setUp(self):
        self.validador = ValidadorImpuestosEspeciales()

    def test_debe_procesar_con_estampilla(self):
        """Test: Debe procesar cuando hay datos y aplica estampilla."""
        resultados = {"impuestos_especiales": {"valor": 1000}}

        resultado = self.validador._debe_procesar_impuestos_especiales(
            resultados, True, False
        )

        self.assertTrue(resultado)

    def test_debe_procesar_con_obra_publica(self):
        """Test: Debe procesar cuando hay datos y aplica obra publica."""
        resultados = {"impuestos_especiales": {"valor": 1000}}

        resultado = self.validador._debe_procesar_impuestos_especiales(
            resultados, False, True
        )

        self.assertTrue(resultado)

    def test_debe_procesar_con_ambos(self):
        """Test: Debe procesar cuando aplican ambos impuestos."""
        resultados = {"impuestos_especiales": {"valor": 1000}}

        resultado = self.validador._debe_procesar_impuestos_especiales(
            resultados, True, True
        )

        self.assertTrue(resultado)

    def test_no_debe_procesar_sin_datos(self):
        """Test: No debe procesar si no hay datos en resultados_analisis."""
        resultados = {}

        resultado = self.validador._debe_procesar_impuestos_especiales(
            resultados, True, True
        )

        self.assertFalse(resultado)

    def test_no_debe_procesar_sin_flags(self):
        """Test: No debe procesar si ninguno de los flags esta activo."""
        resultados = {"impuestos_especiales": {"valor": 1000}}

        resultado = self.validador._debe_procesar_impuestos_especiales(
            resultados, False, False
        )

        self.assertFalse(resultado)

    def test_edge_case_datos_con_flag_false(self):
        """Test: Edge case - tiene datos pero flags en False."""
        resultados = {"impuestos_especiales": {"valor": 5000}}

        resultado = self.validador._debe_procesar_impuestos_especiales(
            resultados, False, False
        )

        self.assertFalse(resultado)


class TestProcesarLiquidacion(unittest.IsolatedAsyncioTestCase):
    """Tests para _procesar_liquidacion."""

    async def asyncSetUp(self):
        self.mock_liquidador = Mock()
        self.validador = ValidadorImpuestosEspeciales(
            liquidador_estampilla=self.mock_liquidador
        )

    async def test_procesar_liquidacion_exitosa(self):
        """Test: Procesamiento exitoso con liquidador inyectado."""
        resultados = {"impuestos_especiales": {"valor": 1000}}
        self.mock_liquidador.liquidar_integrado.return_value = {
            "estampilla_universidad": {"aplica": True, "valor_estampilla": 50000},
            "contribucion_obra_publica": {"aplica": True, "valor_contribucion": 25000}
        }

        with patch.object(self.validador, '_procesar_resultados', return_value={"test": "result"}) as mock_procesar:
            resultado = await self.validador._procesar_liquidacion(
                resultados, True, True, 123, "Negocio Test"
            )

            self.mock_liquidador.liquidar_integrado.assert_called_once()
            mock_procesar.assert_called_once()
            self.assertEqual(resultado, {"test": "result"})

    async def test_lazy_initialization_liquidador(self):
        """Test: Lazy initialization cuando no se inyecto liquidador."""
        validador_sin_liquidador = ValidadorImpuestosEspeciales()
        resultados = {"impuestos_especiales": {"valor": 1000}}

        with patch('app.validar_impuestos_esp.LiquidadorEstampilla') as MockLiquidador:
            mock_instance = Mock()
            mock_instance.liquidar_integrado.return_value = {
                "estampilla_universidad": {"aplica": True}
            }
            MockLiquidador.return_value = mock_instance

            with patch.object(validador_sin_liquidador, '_procesar_resultados', return_value={}):
                await validador_sin_liquidador._procesar_liquidacion(
                    resultados, True, False, 123, "Test"
                )

            MockLiquidador.assert_called_once()
            self.assertIsNotNone(validador_sin_liquidador.liquidador_estampilla)

    async def test_procesar_liquidacion_pasa_parametros_correctos(self):
        """Test: Verifica que se pasan los parametros correctos al liquidador."""
        resultados = {"impuestos_especiales": {"dato": "test"}}
        self.mock_liquidador.liquidar_integrado.return_value = {}

        with patch.object(self.validador, '_procesar_resultados', return_value={}):
            await self.validador._procesar_liquidacion(
                resultados, True, False, 999, "Mi Negocio"
            )

        args = self.mock_liquidador.liquidar_integrado.call_args[0]
        self.assertEqual(args[0], {"dato": "test"})  # analisis_especiales
        self.assertEqual(args[1], 999)  # codigo_del_negocio
        self.assertEqual(args[2], "Mi Negocio")  # nombre_negocio


class TestProcesarResultados(unittest.TestCase):
    """Tests para _procesar_resultados."""

    def setUp(self):
        self.validador = ValidadorImpuestosEspeciales()

    def test_procesar_ambos_impuestos(self):
        """Test: Procesa ambos impuestos cuando aplican."""
        resultado_completo = {
            "estampilla_universidad": {"aplica": True, "valor_estampilla": 50000},
            "contribucion_obra_publica": {"aplica": True, "valor_contribucion": 25000}
        }

        with patch.object(self.validador, '_log_estampilla'), \
             patch.object(self.validador, '_log_obra_publica'):
            resultado = self.validador._procesar_resultados(
                resultado_completo, True, True
            )

        self.assertIn("estampilla_universidad", resultado)
        self.assertIn("contribucion_obra_publica", resultado)
        self.assertEqual(resultado["estampilla_universidad"]["valor_estampilla"], 50000)
        self.assertEqual(resultado["contribucion_obra_publica"]["valor_contribucion"], 25000)

    def test_procesar_solo_estampilla(self):
        """Test: Procesa solo estampilla cuando solo aplica esta."""
        resultado_completo = {
            "estampilla_universidad": {"aplica": True, "valor_estampilla": 50000},
            "contribucion_obra_publica": {"aplica": False}
        }

        with patch.object(self.validador, '_log_estampilla'), \
             patch.object(self.validador, '_log_obra_publica'):
            resultado = self.validador._procesar_resultados(
                resultado_completo, True, False
            )

        self.assertIn("estampilla_universidad", resultado)
        self.assertNotIn("contribucion_obra_publica", resultado)

    def test_procesar_solo_obra_publica(self):
        """Test: Procesa solo obra publica cuando solo aplica esta."""
        resultado_completo = {
            "estampilla_universidad": {"aplica": False},
            "contribucion_obra_publica": {"aplica": True, "valor_contribucion": 25000}
        }

        with patch.object(self.validador, '_log_estampilla'), \
             patch.object(self.validador, '_log_obra_publica'):
            resultado = self.validador._procesar_resultados(
                resultado_completo, False, True
            )

        self.assertNotIn("estampilla_universidad", resultado)
        self.assertIn("contribucion_obra_publica", resultado)

    def test_procesar_sin_resultados_en_dict(self):
        """Test: Edge case - resultado_completo no tiene las claves esperadas."""
        resultado_completo = {"otro_campo": "valor"}

        with patch.object(self.validador, '_log_estampilla'), \
             patch.object(self.validador, '_log_obra_publica'):
            resultado = self.validador._procesar_resultados(
                resultado_completo, True, True
            )

        self.assertEqual(resultado, {})

    def test_procesar_llama_log_correcto(self):
        """Test: Verifica que se llamen los metodos de logging correctos."""
        resultado_completo = {
            "estampilla_universidad": {"valor_estampilla": 50000},
            "contribucion_obra_publica": {"valor_contribucion": 25000}
        }

        with patch.object(self.validador, '_log_estampilla') as mock_log_est, \
             patch.object(self.validador, '_log_obra_publica') as mock_log_obra:
            self.validador._procesar_resultados(resultado_completo, True, True)

            mock_log_est.assert_called_once_with({"valor_estampilla": 50000})
            mock_log_obra.assert_called_once_with({"valor_contribucion": 25000})


class TestLogEstampilla(unittest.TestCase):
    """Tests para _log_estampilla."""

    def setUp(self):
        self.validador = ValidadorImpuestosEspeciales()

    @patch('app.validar_impuestos_esp.logging.getLogger')
    def test_log_estampilla_con_valor(self, mock_logger):
        """Test: Logging de estampilla con valor positivo."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        resultado_estampilla = {"valor_estampilla": 50000.0}

        self.validador._log_estampilla(resultado_estampilla)

        mock_logger_instance.info.assert_called_once()
        call_args = mock_logger_instance.info.call_args[0][0]
        self.assertIn("Estampilla liquidada", call_args)
        self.assertIn("50,000.00", call_args)

    @patch('app.validar_impuestos_esp.logging.getLogger')
    def test_log_estampilla_valor_cero(self, mock_logger):
        """Test: Logging de estampilla con valor cero."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        resultado_estampilla = {"valor_estampilla": 0}

        self.validador._log_estampilla(resultado_estampilla)

        mock_logger_instance.info.assert_called_once()
        call_args = mock_logger_instance.info.call_args[0][0]
        self.assertIn("0.00", call_args)

    @patch('app.validar_impuestos_esp.logging.getLogger')
    def test_log_estampilla_sin_valor(self, mock_logger):
        """Test: Edge case - resultado sin clave 'valor_estampilla'."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        resultado_estampilla = {}

        self.validador._log_estampilla(resultado_estampilla)

        mock_logger_instance.info.assert_called_once()
        call_args = mock_logger_instance.info.call_args[0][0]
        self.assertIn("0.00", call_args)


class TestLogObraPublica(unittest.TestCase):
    """Tests para _log_obra_publica."""

    def setUp(self):
        self.validador = ValidadorImpuestosEspeciales()

    @patch('app.validar_impuestos_esp.logging.getLogger')
    def test_log_obra_publica_con_valor(self, mock_logger):
        """Test: Logging de obra publica con valor positivo."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        resultado_obra = {"valor_contribucion": 25000.0}

        self.validador._log_obra_publica(resultado_obra)

        mock_logger_instance.info.assert_called_once()
        call_args = mock_logger_instance.info.call_args[0][0]
        self.assertIn("Obra pública liquidada", call_args)
        self.assertIn("25,000.00", call_args)

    @patch('app.validar_impuestos_esp.logging.getLogger')
    def test_log_obra_publica_valor_cero(self, mock_logger):
        """Test: Logging de obra publica con valor cero."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        resultado_obra = {"valor_contribucion": 0}

        self.validador._log_obra_publica(resultado_obra)

        mock_logger_instance.info.assert_called_once()
        call_args = mock_logger_instance.info.call_args[0][0]
        self.assertIn("0.00", call_args)

    @patch('app.validar_impuestos_esp.logging.getLogger')
    def test_log_obra_publica_sin_valor(self, mock_logger):
        """Test: Edge case - resultado sin clave 'valor_contribucion'."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        resultado_obra = {}

        self.validador._log_obra_publica(resultado_obra)

        mock_logger_instance.info.assert_called_once()
        call_args = mock_logger_instance.info.call_args[0][0]
        self.assertIn("0.00", call_args)


class TestManejarError(unittest.TestCase):
    """Tests para _manejar_error."""

    def setUp(self):
        self.validador = ValidadorImpuestosEspeciales()

    @patch('app.validar_impuestos_esp.logging.getLogger')
    def test_manejar_error_ambos_impuestos(self, mock_logger):
        """Test: Manejo de error cuando aplican ambos impuestos."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        excepcion = Exception("Error de prueba")

        resultado = self.validador._manejar_error(excepcion, True, True)

        self.assertIn("estampilla_universidad", resultado)
        self.assertIn("contribucion_obra_publica", resultado)
        self.assertEqual(resultado["estampilla_universidad"]["error"], "Error de prueba")
        self.assertEqual(resultado["estampilla_universidad"]["aplica"], False)
        self.assertEqual(resultado["contribucion_obra_publica"]["error"], "Error de prueba")
        self.assertEqual(resultado["contribucion_obra_publica"]["aplica"], False)
        mock_logger_instance.error.assert_called_once()

    @patch('app.validar_impuestos_esp.logging.getLogger')
    def test_manejar_error_solo_estampilla(self, mock_logger):
        """Test: Manejo de error solo para estampilla."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        excepcion = Exception("Error test")

        resultado = self.validador._manejar_error(excepcion, True, False)

        self.assertIn("estampilla_universidad", resultado)
        self.assertNotIn("contribucion_obra_publica", resultado)

    @patch('app.validar_impuestos_esp.logging.getLogger')
    def test_manejar_error_solo_obra_publica(self, mock_logger):
        """Test: Manejo de error solo para obra publica."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        excepcion = Exception("Error test")

        resultado = self.validador._manejar_error(excepcion, False, True)

        self.assertNotIn("estampilla_universidad", resultado)
        self.assertIn("contribucion_obra_publica", resultado)

    @patch('app.validar_impuestos_esp.logging.getLogger')
    def test_manejar_error_ninguno(self, mock_logger):
        """Test: Edge case - error pero ninguno de los flags activos."""
        mock_logger_instance = Mock()
        mock_logger.return_value = mock_logger_instance
        self.validador.logger = mock_logger_instance

        excepcion = Exception("Error test")

        resultado = self.validador._manejar_error(excepcion, False, False)

        self.assertEqual(resultado, {})
        mock_logger_instance.error.assert_called_once()


# ============================================================================
# TESTS DE INTEGRACIÓN - ORQUESTADOR
# ============================================================================

class TestValidarOrquestador(unittest.IsolatedAsyncioTestCase):
    """Tests de integracion para el metodo validar (orquestador)."""

    async def asyncSetUp(self):
        self.mock_liquidador = Mock()
        self.validador = ValidadorImpuestosEspeciales(
            liquidador_estampilla=self.mock_liquidador
        )

    async def test_validar_flujo_completo_exitoso(self):
        """Test: Flujo completo exitoso con ambos impuestos."""
        resultados = {"impuestos_especiales": {"valor": 1000}}
        self.mock_liquidador.liquidar_integrado.return_value = {
            "estampilla_universidad": {"aplica": True, "valor_estampilla": 50000},
            "contribucion_obra_publica": {"aplica": True, "valor_contribucion": 25000}
        }

        with patch.object(self.validador, '_log_estampilla'), \
             patch.object(self.validador, '_log_obra_publica'):
            resultado = await self.validador.validar(
                resultados, True, True, 123, "Negocio Test"
            )

        self.assertIsNotNone(resultado)
        self.assertIn("estampilla_universidad", resultado)
        self.assertIn("contribucion_obra_publica", resultado)

    async def test_validar_sin_datos_retorna_none(self):
        """Test: Retorna None cuando no hay datos para procesar."""
        resultados = {}

        resultado = await self.validador.validar(
            resultados, True, True, 123, "Test"
        )

        self.assertIsNone(resultado)

    async def test_validar_sin_flags_retorna_none(self):
        """Test: Retorna None cuando ningun flag esta activo."""
        resultados = {"impuestos_especiales": {"valor": 1000}}

        resultado = await self.validador.validar(
            resultados, False, False, 123, "Test"
        )

        self.assertIsNone(resultado)

    async def test_validar_maneja_excepcion_del_liquidador(self):
        """Test: Maneja excepcion lanzada por el liquidador."""
        resultados = {"impuestos_especiales": {"valor": 1000}}
        self.mock_liquidador.liquidar_integrado.side_effect = Exception("Error de liquidacion")

        with patch.object(self.validador.logger, 'error'):
            resultado = await self.validador.validar(
                resultados, True, True, 123, "Test"
            )

        self.assertIsNotNone(resultado)
        self.assertIn("estampilla_universidad", resultado)
        self.assertIn("contribucion_obra_publica", resultado)
        self.assertEqual(resultado["estampilla_universidad"]["aplica"], False)
        self.assertEqual(resultado["contribucion_obra_publica"]["aplica"], False)


# ============================================================================
# TESTS WRAPPER FUNCTION
# ============================================================================

class TestValidarImpuestosEspecialesWrapper(unittest.IsolatedAsyncioTestCase):
    """Tests para la funcion wrapper validar_impuestos_especiales."""

    def setUp(self):
        self._uvt_patcher = patch.object(config, 'UVT_2025', 49799)
        self._uvt_patcher.start()

    def tearDown(self):
        self._uvt_patcher.stop()

    async def test_wrapper_instancia_validador_y_delega(self):
        """Test: Wrapper instancia ValidadorImpuestosEspeciales y delega correctamente."""
        resultados = {"impuestos_especiales": {"valor": 1000}}

        with patch('app.validar_impuestos_esp.ValidadorImpuestosEspeciales') as MockValidador:
            mock_instance = AsyncMock()
            mock_instance.validar = AsyncMock(return_value={"test": "result"})
            MockValidador.return_value = mock_instance

            resultado = await validar_impuestos_especiales(
                resultados, True, False, 123, "Negocio Test"
            )

            MockValidador.assert_called_once()
            mock_instance.validar.assert_called_once_with(
                resultados_analisis=resultados,
                aplica_estampilla=True,
                aplica_obra_publica=False,
                codigo_del_negocio=123,
                nombre_negocio="Negocio Test"
            )
            self.assertEqual(resultado, {"test": "result"})

    async def test_wrapper_retorna_none_cuando_validador_retorna_none(self):
        """Test: Wrapper retorna None cuando validador retorna None."""
        resultados = {}

        with patch('app.validar_impuestos_esp.ValidadorImpuestosEspeciales') as MockValidador:
            mock_instance = AsyncMock()
            mock_instance.validar = AsyncMock(return_value=None)
            MockValidador.return_value = mock_instance

            resultado = await validar_impuestos_especiales(
                resultados, False, False, 123, "Test"
            )

            self.assertIsNone(resultado)


# ============================================================================
# TESTS DE EDGE CASES COMPLETOS
# ============================================================================

class TestEdgeCasesCompletos(unittest.IsolatedAsyncioTestCase):
    """Tests de edge cases complejos y situaciones extremas."""

    async def asyncSetUp(self):
        self.validador = ValidadorImpuestosEspeciales()

    async def test_edge_resultados_analisis_none(self):
        """Test: Edge case - resultados_analisis es None."""
        # Esto deberia causar error, pero el metodo no valida
        with self.assertRaises(TypeError):
            await self.validador.validar(None, True, True, 123, "Test")

    async def test_edge_resultados_analisis_vacio(self):
        """Test: Edge case - resultados_analisis dict vacio."""
        resultado = await self.validador.validar({}, True, True, 123, "Test")

        self.assertIsNone(resultado)

    async def test_edge_codigo_negocio_cero(self):
        """Test: Edge case - codigo_del_negocio es 0."""
        resultados = {"impuestos_especiales": {"valor": 1000}}
        mock_liquidador = Mock()
        mock_liquidador.liquidar_integrado.return_value = {
            "estampilla_universidad": {"aplica": True, "valor_estampilla": 0}
        }
        self.validador.liquidador_estampilla = mock_liquidador

        with patch.object(self.validador, '_log_estampilla'):
            resultado = await self.validador.validar(
                resultados, True, False, 0, "Test"
            )

        # Debe procesar normalmente incluso con codigo 0
        self.assertIsNotNone(resultado)

    async def test_edge_nombre_negocio_vacio(self):
        """Test: Edge case - nombre_negocio es string vacio."""
        resultados = {"impuestos_especiales": {"valor": 1000}}
        mock_liquidador = Mock()
        mock_liquidador.liquidar_integrado.return_value = {}
        self.validador.liquidador_estampilla = mock_liquidador

        resultado = await self.validador.validar(
            resultados, True, False, 123, ""
        )

        # Debe procesar normalmente incluso con nombre vacio
        mock_liquidador.liquidar_integrado.assert_called_once()

    async def test_edge_nombre_negocio_caracteres_especiales(self):
        """Test: Edge case - nombre_negocio con caracteres especiales."""
        resultados = {"impuestos_especiales": {"valor": 1000}}
        mock_liquidador = Mock()
        mock_liquidador.liquidar_integrado.return_value = {}
        self.validador.liquidador_estampilla = mock_liquidador

        nombre_especial = "Negocio <script>alert('xss')</script>"

        await self.validador.validar(
            resultados, False, True, 123, nombre_especial
        )

        # Verificar que se pasa tal cual (sin sanitizacion)
        args = mock_liquidador.liquidar_integrado.call_args[0]
        self.assertEqual(args[2], nombre_especial)

    async def test_edge_liquidador_retorna_estructura_incompleta(self):
        """Test: Edge case - liquidador retorna dict sin las claves esperadas."""
        resultados = {"impuestos_especiales": {"valor": 1000}}
        mock_liquidador = Mock()
        mock_liquidador.liquidar_integrado.return_value = {
            "otro_campo": "valor inesperado"
        }
        self.validador.liquidador_estampilla = mock_liquidador

        resultado = await self.validador.validar(
            resultados, True, True, 123, "Test"
        )

        # Debe retornar dict vacio porque no encuentra las claves esperadas
        self.assertEqual(resultado, {})

    async def test_edge_valores_negativos_en_liquidacion(self):
        """Test: Edge case - liquidador retorna valores negativos."""
        resultados = {"impuestos_especiales": {"valor": 1000}}
        mock_liquidador = Mock()
        mock_liquidador.liquidar_integrado.return_value = {
            "estampilla_universidad": {"aplica": True, "valor_estampilla": -50000},
            "contribucion_obra_publica": {"aplica": True, "valor_contribucion": -25000}
        }
        self.validador.liquidador_estampilla = mock_liquidador

        with patch.object(self.validador, '_log_estampilla'), \
             patch.object(self.validador, '_log_obra_publica'):
            resultado = await self.validador.validar(
                resultados, True, True, 123, "Test"
            )

        # Debe procesar normalmente (validaciones upstream deben prevenir negativos)
        self.assertEqual(resultado["estampilla_universidad"]["valor_estampilla"], -50000)
        self.assertEqual(resultado["contribucion_obra_publica"]["valor_contribucion"], -25000)


# ============================================================================
# SUITE Y RUNNER
# ============================================================================

def suite():
    """Crear suite de tests."""
    suite = unittest.TestSuite()

    # Tests unitarios
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestValidadorImpuestosEspecialesInit))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDebeProcesarImpuestosEspeciales))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestProcesarLiquidacion))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestProcesarResultados))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestLogEstampilla))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestLogObraPublica))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestManejarError))

    # Tests de integracion
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestValidarOrquestador))

    # Tests wrapper
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestValidarImpuestosEspecialesWrapper))

    # Tests edge cases
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestEdgeCasesCompletos))

    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
