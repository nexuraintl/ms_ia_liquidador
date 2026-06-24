"""
Tests para el modulo app/validar_ica.py.

Cubre el validador de ICA (Impuesto de Industria y Comercio) con tests unitarios,
de integracion y edge cases.

Estructura de tests:
- TestValidadorICAInit: Constructor y dependencias
- TestDebeProcesarICA: Logica de decision para procesar
- TestProcesarLiquidacion: Procesamiento completo
- TestEjecutarLiquidacion: Ejecucion del liquidador
- TestLogResultado: Logging de resultados
- TestManejarError: Manejo de errores
- TestValidarOrquestador: Flujo completo de validacion
- TestValidarICAWrapper: Funcion wrapper
- TestEdgeCasesCompletos: Casos extremos

Autor: Sistema Preliquidador
Version: 1.0
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

# Modulo a testear
from app.validar_ica import ValidadorICA, validar_ica


# =============================================================================
# TESTS UNITARIOS
# =============================================================================


class TestValidadorICAInit(unittest.TestCase):
    """Tests para el constructor de ValidadorICA."""

    def test_init_con_todas_dependencias(self):
        """Inicializa correctamente con todas las dependencias."""
        mock_db_manager = Mock()
        mock_liquidador = Mock()

        validador = ValidadorICA(
            estructura_contable=123,
            db_manager=mock_db_manager,
            liquidador_ica=mock_liquidador
        )

        self.assertEqual(validador.estructura_contable, 123)
        self.assertIs(validador.db_manager, mock_db_manager)
        self.assertIs(validador.liquidador_ica, mock_liquidador)

    def test_init_sin_liquidador_ica(self):
        """Inicializa sin liquidador (lazy initialization)."""
        mock_db_manager = Mock()

        validador = ValidadorICA(
            estructura_contable=456,
            db_manager=mock_db_manager
        )

        self.assertEqual(validador.estructura_contable, 456)
        self.assertIs(validador.db_manager, mock_db_manager)
        self.assertIsNone(validador.liquidador_ica)

    def test_init_verifica_tipo_logger(self):
        """Verifica que el logger sea una instancia correcta."""
        import logging
        mock_db_manager = Mock()

        validador = ValidadorICA(
            estructura_contable=789,
            db_manager=mock_db_manager
        )

        self.assertIsInstance(validador.logger, logging.Logger)


# =============================================================================


class TestDebeProcesarICA(unittest.TestCase):
    """Tests para el metodo _debe_procesar_ica."""

    def setUp(self):
        """Configuracion inicial para cada test."""
        self.validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock()
        )

    def test_debe_procesar_con_datos_y_aplica_true(self):
        """Debe procesar cuando hay datos de ICA y aplica_ica es True."""
        resultados = {"ica": {"municipios": ["Bogota"]}}
        aplica_ica = True

        resultado = self.validador._debe_procesar_ica(resultados, aplica_ica)

        self.assertTrue(resultado)

    def test_no_debe_procesar_sin_datos(self):
        """No debe procesar si no hay datos de ICA."""
        resultados = {}
        aplica_ica = True

        resultado = self.validador._debe_procesar_ica(resultados, aplica_ica)

        self.assertFalse(resultado)

    def test_no_debe_procesar_con_aplica_false(self):
        """No debe procesar si aplica_ica es False."""
        resultados = {"ica": {"municipios": ["Bogota"]}}
        aplica_ica = False

        resultado = self.validador._debe_procesar_ica(resultados, aplica_ica)

        self.assertFalse(resultado)

    def test_debe_procesar_con_otros_campos(self):
        """Debe procesar incluso si hay otros campos presentes."""
        resultados = {
            "ica": {"municipios": ["Medellin"]},
            "retefuente": {},
            "iva": {}
        }
        aplica_ica = True

        resultado = self.validador._debe_procesar_ica(resultados, aplica_ica)

        self.assertTrue(resultado)


# =============================================================================


class TestEjecutarLiquidacion(unittest.TestCase):
    """Tests para el metodo _ejecutar_liquidacion."""

    def test_ejecutar_con_liquidador_inyectado(self):
        """Usa liquidador inyectado si esta disponible."""
        mock_liquidador = Mock()
        mock_liquidador.liquidar_ica.return_value = {
            "estado": "liquidada",
            "valor_total_ica": 100000
        }

        validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock(),
            liquidador_ica=mock_liquidador
        )

        analisis_ica = {"municipios": ["Bogota"]}
        resultado = validador._ejecutar_liquidacion(analisis_ica, "COP")

        mock_liquidador.liquidar_ica.assert_called_once_with(
            analisis_ica,
            123,
            tipoMoneda="COP"
        )
        self.assertEqual(resultado["estado"], "liquidada")
        self.assertEqual(resultado["valor_total_ica"], 100000)

    @patch('app.validar_ica.LiquidadorICA')
    def test_ejecutar_con_lazy_initialization(self, MockLiquidadorICA):
        """Crea liquidador si no fue inyectado (lazy initialization)."""
        mock_db_manager = Mock()
        mock_liquidador_instance = Mock()
        mock_liquidador_instance.liquidar_ica.return_value = {
            "estado": "liquidada",
            "valor_total_ica": 50000
        }
        MockLiquidadorICA.return_value = mock_liquidador_instance

        validador = ValidadorICA(
            estructura_contable=456,
            db_manager=mock_db_manager
        )

        analisis_ica = {"municipios": ["Cali"]}
        resultado = validador._ejecutar_liquidacion(analisis_ica, "COP")

        MockLiquidadorICA.assert_called_once_with(database_manager=mock_db_manager)
        self.assertIs(validador.liquidador_ica, mock_liquidador_instance)
        self.assertEqual(resultado["estado"], "liquidada")


# =============================================================================


class TestLogResultado(unittest.TestCase):
    """Tests para el metodo _log_resultado."""

    def setUp(self):
        """Configuracion inicial para cada test."""
        self.validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock()
        )

    def test_log_resultado_con_datos_completos(self):
        """Loguea correctamente con todos los datos."""
        resultado_ica = {
            "estado": "liquidada",
            "valor_total_ica": 150000.50
        }

        with patch.object(self.validador.logger, 'info') as mock_info:
            self.validador._log_resultado(resultado_ica)

            self.assertEqual(mock_info.call_count, 2)
            mock_info.assert_any_call(" ICA - Estado: liquidada")
            mock_info.assert_any_call(" ICA - Valor total: $150,000.50")

    def test_log_resultado_sin_estado(self):
        """Loguea con estado por defecto si no existe."""
        resultado_ica = {"valor_total_ica": 100000}

        with patch.object(self.validador.logger, 'info') as mock_info:
            self.validador._log_resultado(resultado_ica)

            mock_info.assert_any_call(" ICA - Estado: Desconocido")

    def test_log_resultado_sin_valor(self):
        """Loguea con valor 0 si no existe."""
        resultado_ica = {"estado": "procesada"}

        with patch.object(self.validador.logger, 'info') as mock_info:
            self.validador._log_resultado(resultado_ica)

            mock_info.assert_any_call(" ICA - Valor total: $0.00")


# =============================================================================


class TestManejarError(unittest.TestCase):
    """Tests para el metodo _manejar_error."""

    def setUp(self):
        """Configuracion inicial para cada test."""
        self.validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock()
        )

    def test_manejar_error_estructura_correcta(self):
        """Manejo de error retorna estructura correcta."""
        excepcion = Exception("Error de prueba")

        resultado = self.validador._manejar_error(excepcion)

        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["estado"], "preliquidacion_sin_finalizar")
        self.assertEqual(resultado["error"], "Error de prueba")
        self.assertIn("Error en liquidación ICA: Error de prueba", resultado["observaciones"])

    def test_manejar_error_loguea_mensaje(self):
        """Manejo de error loguea el mensaje correcto."""
        excepcion = Exception("Error critico")

        with patch.object(self.validador.logger, 'error') as mock_error:
            self.validador._manejar_error(excepcion)

            self.assertEqual(mock_error.call_count, 2)
            mock_error.assert_any_call(" Error liquidando ICA: Error critico")


# =============================================================================


class TestProcesarLiquidacion(unittest.IsolatedAsyncioTestCase):
    """Tests para el metodo _procesar_liquidacion."""

    def setUp(self):
        """Configuracion inicial para cada test."""
        self.mock_liquidador = Mock()
        self.validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock(),
            liquidador_ica=self.mock_liquidador
        )

    async def test_procesar_liquidacion_exitosa(self):
        """Procesamiento exitoso de liquidacion."""
        self.mock_liquidador.liquidar_ica.return_value = {
            "estado": "liquidada",
            "valor_total_ica": 200000
        }

        resultados = {"ica": {"municipios": ["Bogota", "Medellin"]}}

        with patch.object(self.validador.logger, 'info'):
            resultado = await self.validador._procesar_liquidacion(resultados, "COP")

        self.assertEqual(resultado["estado"], "liquidada")
        self.assertEqual(resultado["valor_total_ica"], 200000)

    async def test_procesar_liquidacion_loguea_inicio(self):
        """Loguea inicio de procesamiento."""
        self.mock_liquidador.liquidar_ica.return_value = {"estado": "ok"}
        resultados = {"ica": {"municipios": ["Cali"]}}

        with patch.object(self.validador.logger, 'info') as mock_info:
            await self.validador._procesar_liquidacion(resultados, "COP")

            calls = [str(call) for call in mock_info.call_args_list]
            self.assertTrue(any("Liquidando ICA" in str(call) for call in calls))


# =============================================================================
# TESTS DE INTEGRACION
# =============================================================================


class TestValidarOrquestador(unittest.IsolatedAsyncioTestCase):
    """Tests para el metodo validar (orquestador principal)."""

    async def test_validar_flujo_completo_exitoso(self):
        """Flujo completo exitoso con ICA."""
        mock_liquidador = Mock()
        mock_liquidador.liquidar_ica.return_value = {
            "estado": "liquidada",
            "valor_total_ica": 300000,
            "municipios_aplicados": ["Bogota"]
        }

        validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock(),
            liquidador_ica=mock_liquidador
        )

        resultados = {"ica": {"municipios": ["Bogota"], "base_gravable": 10000000}}
        aplica_ica = True

        with patch.object(validador.logger, 'info'):
            resultado = await validador.validar(resultados, aplica_ica, "COP")

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["estado"], "liquidada")
        self.assertEqual(resultado["valor_total_ica"], 300000)

    async def test_validar_sin_datos_retorna_none(self):
        """Retorna None cuando no hay datos de ICA."""
        validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock()
        )

        resultados = {}
        aplica_ica = True

        resultado = await validador.validar(resultados, aplica_ica, "COP")

        self.assertIsNone(resultado)

    async def test_validar_con_aplica_false_retorna_none(self):
        """Retorna None cuando aplica_ica es False."""
        validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock()
        )

        resultados = {"ica": {"municipios": ["Bogota"]}}
        aplica_ica = False

        resultado = await validador.validar(resultados, aplica_ica, "COP")

        self.assertIsNone(resultado)

    async def test_validar_maneja_excepcion(self):
        """Maneja excepcion durante procesamiento."""
        mock_liquidador = Mock()
        mock_liquidador.liquidar_ica.side_effect = Exception("Error de liquidacion")

        validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock(),
            liquidador_ica=mock_liquidador
        )

        resultados = {"ica": {"municipios": ["Bogota"]}}
        aplica_ica = True

        with patch.object(validador.logger, 'error'):
            resultado = await validador.validar(resultados, aplica_ica, "COP")

        self.assertIsNotNone(resultado)
        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["estado"], "preliquidacion_sin_finalizar")
        self.assertIn("error", resultado)


# =============================================================================
# TESTS WRAPPER FUNCTION
# =============================================================================


class TestValidarICAWrapper(unittest.IsolatedAsyncioTestCase):
    """Tests para la funcion wrapper validar_ica."""

    @patch('app.validar_ica.ValidadorICA')
    async def test_wrapper_instancia_validador_y_delega(self, MockValidadorICA):
        """Wrapper instancia ValidadorICA y delega correctamente."""
        mock_validador_instance = AsyncMock()
        mock_validador_instance.validar.return_value = {
            "estado": "liquidada",
            "valor_total_ica": 100000
        }
        MockValidadorICA.return_value = mock_validador_instance

        mock_db_manager = Mock()
        resultados = {"ica": {"municipios": ["Bogota"]}}

        resultado = await validar_ica(
            resultados_analisis=resultados,
            aplica_ica=True,
            estructura_contable=123,
            db_manager=mock_db_manager,
            tipoMoneda="COP"
        )

        MockValidadorICA.assert_called_once_with(
            estructura_contable=123,
            db_manager=mock_db_manager
        )
        mock_validador_instance.validar.assert_called_once_with(
            resultados_analisis=resultados,
            aplica_ica=True,
            tipoMoneda="COP"
        )
        self.assertEqual(resultado["estado"], "liquidada")

    @patch('app.validar_ica.ValidadorICA')
    async def test_wrapper_retorna_none_cuando_validador_retorna_none(self, MockValidadorICA):
        """Wrapper retorna None correctamente."""
        mock_validador_instance = AsyncMock()
        mock_validador_instance.validar.return_value = None
        MockValidadorICA.return_value = mock_validador_instance

        resultado = await validar_ica(
            resultados_analisis={},
            aplica_ica=False,
            estructura_contable=123,
            db_manager=Mock(),
            tipoMoneda="COP"
        )

        self.assertIsNone(resultado)


# =============================================================================
# TESTS DE EDGE CASES
# =============================================================================


class TestEdgeCasesCompletos(unittest.IsolatedAsyncioTestCase):
    """Tests para casos extremos y situaciones inusuales."""

    async def test_edge_resultados_analisis_none(self):
        """Maneja resultados_analisis como None."""
        validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock()
        )

        with self.assertRaises(TypeError):
            await validador.validar(None, True, "COP")

    async def test_edge_resultados_analisis_vacio(self):
        """Maneja resultados_analisis vacio."""
        validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock()
        )

        resultado = await validador.validar({}, True, "COP")

        self.assertIsNone(resultado)

    async def test_edge_ica_vacio(self):
        """Maneja ICA presente pero vacio."""
        mock_liquidador = Mock()
        mock_liquidador.liquidar_ica.return_value = {
            "estado": "sin_municipios",
            "valor_total_ica": 0
        }

        validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock(),
            liquidador_ica=mock_liquidador
        )

        resultados = {"ica": {}}

        with patch.object(validador.logger, 'info'):
            resultado = await validador.validar(resultados, True, "COP")

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["estado"], "sin_municipios")

    async def test_edge_liquidador_retorna_dict_sin_estado(self):
        """Maneja liquidador que retorna dict sin campo estado."""
        mock_liquidador = Mock()
        mock_liquidador.liquidar_ica.return_value = {
            "valor_total_ica": 50000
        }

        validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock(),
            liquidador_ica=mock_liquidador
        )

        resultados = {"ica": {"municipios": ["Bogota"]}}

        with patch.object(validador.logger, 'info') as mock_info:
            resultado = await validador.validar(resultados, True, "COP")

        self.assertIsNotNone(resultado)
        calls_str = [str(call) for call in mock_info.call_args_list]
        self.assertTrue(any("Desconocido" in call for call in calls_str))

    async def test_edge_liquidador_retorna_dict_sin_valor(self):
        """Maneja liquidador que retorna dict sin campo valor_total_ica."""
        mock_liquidador = Mock()
        mock_liquidador.liquidar_ica.return_value = {
            "estado": "liquidada"
        }

        validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock(),
            liquidador_ica=mock_liquidador
        )

        resultados = {"ica": {"municipios": ["Medellin"]}}

        with patch.object(validador.logger, 'info') as mock_info:
            resultado = await validador.validar(resultados, True, "COP")

        self.assertIsNotNone(resultado)
        calls_str = [str(call) for call in mock_info.call_args_list]
        self.assertTrue(any("$0.00" in call for call in calls_str))

    async def test_edge_moneda_diferente(self):
        """Maneja tipo de moneda diferente (USD)."""
        mock_liquidador = Mock()
        mock_liquidador.liquidar_ica.return_value = {
            "estado": "liquidada",
            "valor_total_ica": 100
        }

        validador = ValidadorICA(
            estructura_contable=123,
            db_manager=Mock(),
            liquidador_ica=mock_liquidador
        )

        resultados = {"ica": {"municipios": ["Bogota"]}}

        with patch.object(validador.logger, 'info'):
            resultado = await validador.validar(resultados, True, "USD")

        mock_liquidador.liquidar_ica.assert_called_once()
        call_kwargs = mock_liquidador.liquidar_ica.call_args[1]
        self.assertEqual(call_kwargs["tipoMoneda"], "USD")


# =============================================================================
# TESTS: validar_estructura_actividades — campo razonamiento (informativo)
# =============================================================================


class TestValidarEstructuraActividadesRazonamiento(unittest.TestCase):
    """
    Tests unitarios para validar que el campo 'razonamiento' en
    validar_estructura_actividades se maneja de forma informativa (no bloqueante).
    """

    def _actividad_base(self, extra: dict = None) -> dict:
        base = {
            "actividades_facturadas": ["Servicios de consultoria"],
            "actividades_relacionadas": [
                {
                    "nombre_act_rel": "Servicios de consultoria en informatica",
                    "codigo_actividad": 620100,
                    "codigo_ubicacion": 1,
                    "razonamiento": "Candidatos: (a) 620100 SERVICIOS. Elegido (a) Criterio 1.",
                }
            ],
            "valor_factura_sin_iva": 1000000.0,
            "autorretenedor_ica": False,
        }
        if extra:
            base["actividades_relacionadas"][0].update(extra)
        return base

    def test_estructura_valida_con_razonamiento(self):
        from prompts.prompt_ica import validar_estructura_actividades
        data = self._actividad_base()
        self.assertTrue(validar_estructura_actividades(data))

    def test_estructura_valida_sin_razonamiento_loguea_warning(self):
        from prompts.prompt_ica import validar_estructura_actividades
        data = self._actividad_base()
        del data["actividades_relacionadas"][0]["razonamiento"]
        import logging
        with self.assertLogs("prompts.prompt_ica", level=logging.WARNING) as cm:
            resultado = validar_estructura_actividades(data)
        self.assertTrue(resultado)
        self.assertTrue(any("razonamiento" in msg for msg in cm.output))

    def test_estructura_valida_con_razonamiento_no_string_loguea_warning(self):
        from prompts.prompt_ica import validar_estructura_actividades
        data = self._actividad_base(extra={"razonamiento": 123})
        import logging
        with self.assertLogs("prompts.prompt_ica", level=logging.WARNING) as cm:
            resultado = validar_estructura_actividades(data)
        self.assertTrue(resultado)
        self.assertTrue(any("razonamiento" in msg for msg in cm.output))


# =============================================================================
# TESTS: validar_estructura_actividades — campo regimen_tributario (opcional)
# =============================================================================


class TestValidarEstructuraActividadesRegimen(unittest.TestCase):
    """
    El campo 'regimen_tributario' es opcional y no debe bloquear la validacion
    de estructura (retrocompatibilidad con respuestas previas de Gemini).
    """

    def _data_base(self) -> dict:
        return {
            "actividades_facturadas": ["Servicios de aseo"],
            "actividades_relacionadas": [
                {
                    "nombre_act_rel": "Limpieza general",
                    "codigo_actividad": 812000,
                    "codigo_ubicacion": 1,
                    "razonamiento": "Candidatos: (a) 812000 SERVICIOS. Elegido (a) Criterio 1.",
                }
            ],
            "valor_factura_sin_iva": 1000000.0,
            "autorretenedor_ica": False,
        }

    def test_estructura_valida_sin_regimen(self):
        from prompts.prompt_ica import validar_estructura_actividades
        # Sin la clave regimen_tributario: debe seguir siendo valida
        self.assertTrue(validar_estructura_actividades(self._data_base()))

    def test_estructura_valida_con_regimen_string(self):
        from prompts.prompt_ica import validar_estructura_actividades
        data = self._data_base()
        data["regimen_tributario"] = "SIMPLE"
        self.assertTrue(validar_estructura_actividades(data))

    def test_estructura_valida_con_regimen_null(self):
        from prompts.prompt_ica import validar_estructura_actividades
        data = self._data_base()
        data["regimen_tributario"] = None
        self.assertTrue(validar_estructura_actividades(data))

    def test_regimen_tipo_invalido_loguea_warning_y_no_bloquea(self):
        from prompts.prompt_ica import validar_estructura_actividades
        data = self._data_base()
        data["regimen_tributario"] = 123
        import logging
        with self.assertLogs("prompts.prompt_ica", level=logging.WARNING) as cm:
            resultado = validar_estructura_actividades(data)
        self.assertTrue(resultado)
        self.assertTrue(any("regimen_tributario" in msg for msg in cm.output))


# =============================================================================
# TESTS: LiquidadorICA — corte por Regimen Simple (SIMPLE) -> no_aplica_impuesto
# =============================================================================


class TestLiquidadorICARegimenSimple(unittest.TestCase):
    """
    Verifica que el liquidador deje ICA en 'no_aplica_impuesto' cuando el
    proveedor pertenece al Regimen Simple de Tributacion (SIMPLE), con una
    observacion que explica por que no aplico ICA.
    """

    def _analisis_validado(self, regimen=None, autorretenedor=False) -> Dict[str, Any]:
        return {
            "aplica": True,
            "estado": "Validado - Listo para liquidación",
            "actividades_facturadas": ["Servicios de aseo y cafeteria"],
            "actividades_relacionadas": [
                {
                    "nombre_act_rel": "Limpieza general",
                    "codigo_actividad": 812000,
                    "codigo_ubicacion": 1,
                }
            ],
            "valor_factura_sin_iva": 3000000.0,
            "ubicaciones_identificadas": [
                {
                    "codigo_ubicacion": 1,
                    "nombre_ubicacion": "BOGOTA",
                    "porcentaje_ejecucion": 100.0,
                }
            ],
            "autorretenedor_ica": autorretenedor,
            "regimen_tributario": regimen,
            "observaciones": [],
        }

    def test_regimen_simple_no_aplica_impuesto(self):
        from Liquidador.liquidador_ica import LiquidadorICA
        liquidador = LiquidadorICA(database_manager=Mock())

        resultado = liquidador.liquidar_ica(
            self._analisis_validado(regimen="SIMPLE"),
            estructura_contable=123,
            tipoMoneda="COP",
        )

        self.assertEqual(resultado["estado"], "no_aplica_impuesto")
        self.assertEqual(resultado["valor_total_ica"], 0.0)
        self.assertEqual(resultado["regimen_tributario"], "SIMPLE")
        self.assertTrue(
            any("Simple" in obs or "SIMPLE" in obs for obs in resultado["observaciones"]),
            "La observacion debe explicar que no aplica por Regimen Simple",
        )

    def test_regimen_simple_case_insensitive(self):
        from Liquidador.liquidador_ica import LiquidadorICA
        liquidador = LiquidadorICA(database_manager=Mock())

        resultado = liquidador.liquidar_ica(
            self._analisis_validado(regimen="simple"),
            estructura_contable=123,
            tipoMoneda="COP",
        )

        self.assertEqual(resultado["estado"], "no_aplica_impuesto")

    def test_regimen_ordinario_no_corta_por_simple(self):
        """Control: con regimen ORDINARIO el corte por SIMPLE no se dispara y se liquida normal."""
        from Liquidador.liquidador_ica import LiquidadorICA
        liquidador = LiquidadorICA(database_manager=Mock())

        actividad_liquidada = {
            "nombre_act_rel": "Limpieza general",
            "codigo_actividad": 812000,
            "codigo_ubicacion": 1,
            "nombre_ubicacion": "BOGOTA",
            "base_gravable_ubicacion": 3000000.0,
            "tarifa": 0.0069,
            "porc_ubicacion": 100.0,
            "valor_ica": 20700.0,
            "observaciones": [],
        }

        with patch.object(liquidador, "_liquidar_actividad_facturada", return_value=actividad_liquidada):
            resultado = liquidador.liquidar_ica(
                self._analisis_validado(regimen="ORDINARIO"),
                estructura_contable=123,
                tipoMoneda="COP",
            )

        self.assertEqual(resultado["estado"], "preliquidado")
        self.assertEqual(resultado["valor_total_ica"], 20700.0)
        self.assertEqual(resultado["regimen_tributario"], "ORDINARIO")


# =============================================================================
# EJECUTAR TESTS
# =============================================================================


if __name__ == "__main__":
    unittest.main(verbosity=2)
