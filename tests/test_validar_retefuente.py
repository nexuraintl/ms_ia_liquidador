"""
Suite de tests para app.validar_retefuente.

Tests unitarios y de integracion para ValidadorRetefuente con cobertura completa
de edge cases y validacion de principios SOLID.

Autor: Sistema Preliquidador
Version: 1.0
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.validar_retefuente import ValidadorRetefuente, validar_retencion_en_la_fuente


class TestValidadorRetefuenteInit(unittest.TestCase):
    """Tests para inicializacion de ValidadorRetefuente."""

    def test_init_con_dependencias_inyectadas(self):
        """Test: Constructor con liquidadores inyectados."""
        mock_consorcio = Mock()
        mock_retencion = Mock()
        mock_db = Mock()

        validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=mock_db,
            liquidador_consorcios=mock_consorcio,
            liquidador_retencion=mock_retencion
        )

        self.assertEqual(validador.estructura_contable, 1)
        self.assertEqual(validador.db_manager, mock_db)
        self.assertEqual(validador.liquidador_consorcios, mock_consorcio)
        self.assertEqual(validador.liquidador_retencion, mock_retencion)
        self.assertIsNotNone(validador.logger)

    def test_init_sin_dependencias_lazy_initialization(self):
        """Test: Constructor sin liquidadores (lazy initialization)."""
        mock_db = Mock()

        validador = ValidadorRetefuente(
            estructura_contable=2,
            db_manager=mock_db
        )

        self.assertEqual(validador.estructura_contable, 2)
        self.assertIsNone(validador.liquidador_consorcios)
        self.assertIsNone(validador.liquidador_retencion)

    def test_init_estructura_contable_cero(self):
        """Test: Edge case - estructura_contable = 0."""
        validador = ValidadorRetefuente(
            estructura_contable=0,
            db_manager=Mock()
        )
        self.assertEqual(validador.estructura_contable, 0)

    def test_init_db_manager_none(self):
        """Test: Edge case - db_manager None (puede causar problemas downstream)."""
        validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=None
        )
        self.assertIsNone(validador.db_manager)


class TestDebeProcesarRetefuente(unittest.TestCase):
    """Tests para _debe_procesar_retefuente."""

    def setUp(self):
        self.validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock()
        )

    def test_debe_procesar_true_casos_validos(self):
        """Test: Debe procesar cuando hay datos y aplica retencion."""
        casos_validos = [
            ({"retefuente": {"valor": 1000}}, True),
            ({"retefuente": {}, "otros": {}}, True),
            ({"retefuente": None}, True),  # Aunque sea None, la key existe
        ]

        for resultados, aplica in casos_validos:
            with self.subTest(resultados=resultados, aplica=aplica):
                resultado = self.validador._debe_procesar_retefuente(resultados, aplica)
                self.assertTrue(resultado)

    def test_debe_procesar_false_casos_invalidos(self):
        """Test: No debe procesar cuando faltan datos o no aplica."""
        casos_invalidos = [
            ({}, True),  # Sin key retefuente
            ({"otros": {}}, True),  # Sin key retefuente
            ({"retefuente": {"valor": 1000}}, False),  # No aplica retencion
            ({}, False),  # Sin key y no aplica
            (None, True),  # Edge: resultados_analisis None
        ]

        for resultados, aplica in casos_invalidos:
            with self.subTest(resultados=resultados, aplica=aplica):
                if resultados is None:
                    with self.assertRaises(TypeError):
                        self.validador._debe_procesar_retefuente(resultados, aplica)
                else:
                    resultado = self.validador._debe_procesar_retefuente(resultados, aplica)
                    self.assertFalse(resultado)


class TestManejarCasoEspecial(unittest.TestCase):
    """Tests para _manejar_caso_especial (recurso extranjero)."""

    def setUp(self):
        self.validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock()
        )

    @patch('app.validar_retefuente.crear_resultado_recurso_extranjero_retefuente')
    def test_manejar_recurso_extranjero(self, mock_crear):
        """Test: Manejo correcto de recurso extranjero."""
        mock_resultado = Mock()
        mock_resultado.aplica = False
        mock_resultado.estado = "recurso_fuente_extranjera"
        mock_resultado.valor_factura_sin_iva = 0.0
        mock_resultado.valor_retencion = 0.0
        mock_resultado.valor_base_retencion = 0.0
        mock_resultado.conceptos_aplicados = []
        mock_resultado.mensajes_error = ["Recurso de fuente extranjera"]

        mock_crear.return_value = mock_resultado

        resultado = self.validador._manejar_caso_especial(
            aplica_retencion=True,
            es_recurso_extranjero=True
        )

        self.assertIsNotNone(resultado)
        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["estado"], "recurso_fuente_extranjera")
        self.assertEqual(resultado["valor_retencion"], 0.0)
        mock_crear.assert_called_once()

    def test_no_aplica_retencion_no_es_recurso(self):
        """Test: No aplica retencion y no es recurso extranjero."""
        resultado = self.validador._manejar_caso_especial(
            aplica_retencion=False,
            es_recurso_extranjero=False
        )
        self.assertIsNone(resultado)

    def test_aplica_pero_no_es_recurso(self):
        """Test: Aplica retencion pero no es recurso extranjero."""
        resultado = self.validador._manejar_caso_especial(
            aplica_retencion=True,
            es_recurso_extranjero=False
        )
        self.assertIsNone(resultado)

    def test_no_aplica_pero_es_recurso(self):
        """Test: No aplica retencion pero es recurso extranjero."""
        resultado = self.validador._manejar_caso_especial(
            aplica_retencion=False,
            es_recurso_extranjero=True
        )
        self.assertIsNone(resultado)


class TestProcesarConsorcio(unittest.IsolatedAsyncioTestCase):
    """Tests para _procesar_consorcio."""

    async def asyncSetUp(self):
        self.mock_liquidador_consorcio = AsyncMock()
        self.validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock(),
            liquidador_consorcios=self.mock_liquidador_consorcio
        )

    @patch('app.validar_retefuente.convertir_consorcio_a_dict')
    @patch('app.validar_retefuente.CONCEPTOS_RETEFUENTE', {"0101": {"concepto": "Test"}})
    async def test_procesar_consorcio_exitoso(self, mock_convertir):
        """Test: Procesamiento exitoso de consorcio."""
        mock_resultado = Mock()
        self.mock_liquidador_consorcio.liquidar_consorcio.return_value = mock_resultado

        mock_dict = {
            "retefuente": {
                "valor_retencion": 50000,
                "consorciados": []
            }
        }
        mock_convertir.return_value = mock_dict

        resultados_analisis = {"retefuente": {"consorcio": "Test"}}
        archivos = [Mock()]
        cache = {"file1": b"data"}

        resultado = await self.validador._procesar_consorcio(
            resultados_analisis,
            archivos,
            cache
        )

        self.assertEqual(resultado["valor_retencion"], 50000)
        self.mock_liquidador_consorcio.liquidar_consorcio.assert_called_once()

    async def test_procesar_consorcio_lazy_init(self):
        """Test: Lazy initialization de liquidador_consorcios."""
        validador_sin_liquidador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock()
        )

        self.assertIsNone(validador_sin_liquidador.liquidador_consorcios)

        with patch('app.validar_retefuente.LiquidadorConsorcios') as MockLiquidador:
            mock_instance = AsyncMock()
            MockLiquidador.return_value = mock_instance
            mock_instance.liquidar_consorcio.return_value = Mock()

            with patch('app.validar_retefuente.convertir_consorcio_a_dict') as mock_convertir:
                mock_convertir.return_value = {"retefuente": {"valor_retencion": 0}}

                await validador_sin_liquidador._procesar_consorcio(
                    {"retefuente": {}},
                    [],
                    {}
                )

                MockLiquidador.assert_called_once()
                self.assertIsNotNone(validador_sin_liquidador.liquidador_consorcios)

    async def test_procesar_consorcio_error_liquidacion(self):
        """Test: Error durante liquidacion de consorcio."""
        self.mock_liquidador_consorcio.liquidar_consorcio.side_effect = Exception("Error de liquidacion")

        with self.assertRaises(Exception) as context:
            await self.validador._procesar_consorcio(
                {"retefuente": {}},
                [],
                {}
            )

        self.assertIn("Error de liquidacion", str(context.exception))

    async def test_procesar_consorcio_datos_vacios(self):
        """Test: Edge case - datos vacios."""
        mock_resultado = Mock()
        self.mock_liquidador_consorcio.liquidar_consorcio.return_value = mock_resultado

        with patch('app.validar_retefuente.convertir_consorcio_a_dict') as mock_convertir:
            mock_convertir.return_value = {"retefuente": {}}

            resultado = await self.validador._procesar_consorcio(
                {"retefuente": {}},
                [],
                {}
            )

            self.assertIsInstance(resultado, dict)


class TestPrepararAnalisisData(unittest.TestCase):
    """Tests para _preparar_analisis_data."""

    def setUp(self):
        self.validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock()
        )

    def test_preparar_con_objeto_pydantic(self):
        """Test: Preparar data con objeto Pydantic que tiene .dict()."""
        mock_analisis = Mock()
        mock_analisis.dict.return_value = {"valor": 1000}

        resultado = self.validador._preparar_analisis_data(
            mock_analisis,
            False,
            "900123456"
        )

        self.assertEqual(resultado["nit_administrativo"], "900123456")
        self.assertEqual(resultado["tipo_analisis"], "retefuente_paralelo")
        self.assertEqual(resultado["es_facturacion_exterior"], False)
        self.assertEqual(resultado["analisis"], {"valor": 1000})
        self.assertIn("timestamp", resultado)
        mock_analisis.dict.assert_called_once()

    def test_preparar_con_dict_directo(self):
        """Test: Preparar data con dict directo (sin .dict())."""
        analisis_dict = {"valor": 2000, "concepto": "Test"}

        resultado = self.validador._preparar_analisis_data(
            analisis_dict,
            True,
            "800999888"
        )

        self.assertEqual(resultado["analisis"], analisis_dict)
        self.assertEqual(resultado["es_facturacion_exterior"], True)
        self.assertEqual(resultado["nit_administrativo"], "800999888")

    def test_preparar_edge_nit_vacio(self):
        """Test: Edge case - NIT vacio."""
        resultado = self.validador._preparar_analisis_data(
            {},
            False,
            ""
        )

        self.assertEqual(resultado["nit_administrativo"], "")

    def test_preparar_edge_analisis_none(self):
        """Test: Edge case - analisis None."""
        resultado = self.validador._preparar_analisis_data(
            None,
            False,
            "900123456"
        )

        self.assertIsNone(resultado["analisis"])


class TestEjecutarLiquidacionNormal(unittest.IsolatedAsyncioTestCase):
    """Tests para _ejecutar_liquidacion_normal."""

    async def asyncSetUp(self):
        self.mock_liquidador = Mock()
        self.mock_liquidador.liquidar_retefuente_seguro = Mock(return_value={"aplica": True})
        self.validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock(),
            liquidador_retencion=self.mock_liquidador
        )

    async def test_ejecutar_liquidacion_exitosa(self):
        """Test: Ejecucion exitosa de liquidacion."""
        analisis_data = {
            "timestamp": "2024-01-01",
            "analisis": {"valor": 1000}
        }

        resultado = await self.validador._ejecutar_liquidacion_normal(
            analisis_data,
            "900123456",
            "COP"
        )

        self.assertEqual(resultado["aplica"], True)
        self.mock_liquidador.liquidar_retefuente_seguro.assert_called_once_with(
            analisis_data,
            "900123456",
            tipoMoneda="COP"
        )

    async def test_ejecutar_liquidacion_lazy_init(self):
        """Test: Lazy initialization de liquidador_retencion."""
        validador_sin_liquidador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock()
        )

        with patch('app.validar_retefuente.LiquidadorRetencion') as MockLiquidador:
            mock_instance = Mock()
            mock_instance.liquidar_retefuente_seguro.return_value = {"aplica": False}
            MockLiquidador.return_value = mock_instance

            resultado = await validador_sin_liquidador._ejecutar_liquidacion_normal(
                {},
                "900123456",
                "USD"
            )

            MockLiquidador.assert_called_once()
            self.assertIsNotNone(validador_sin_liquidador.liquidador_retencion)

    async def test_ejecutar_liquidacion_moneda_usd(self):
        """Test: Liquidacion con moneda USD."""
        resultado = await self.validador._ejecutar_liquidacion_normal(
            {"analisis": {}},
            "900123456",
            "USD"
        )

        llamada_args = self.mock_liquidador.liquidar_retefuente_seguro.call_args
        self.assertEqual(llamada_args.kwargs["tipoMoneda"], "USD")


class TestCrearResultadoError(unittest.TestCase):
    """Tests para _crear_resultado_error."""

    def setUp(self):
        self.validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock()
        )

    def test_crear_resultado_error_mensaje_normal(self):
        """Test: Crear resultado de error con mensaje normal."""
        resultado_dict = {"error": "Error de conexion"}

        resultado = self.validador._crear_resultado_error(resultado_dict)

        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["estado"], "preliquidacion_sin_finalizar")
        self.assertEqual(resultado["valor_retencion"], 0.0)
        self.assertEqual(resultado["valor_factura_sin_iva"], 0.0)
        self.assertEqual(resultado["valor_base"], 0.0)
        self.assertEqual(resultado["conceptos_aplicados"], [])
        self.assertIn("Error de conexion", resultado["observaciones"])

    def test_crear_resultado_error_sin_mensaje(self):
        """Test: Edge case - error sin mensaje."""
        resultado_dict = {}

        resultado = self.validador._crear_resultado_error(resultado_dict)

        self.assertIsNone(resultado["observaciones"][0])

    def test_crear_resultado_error_mensaje_vacio(self):
        """Test: Edge case - mensaje vacio."""
        resultado_dict = {"error": ""}

        resultado = self.validador._crear_resultado_error(resultado_dict)

        self.assertEqual(resultado["observaciones"], [""])


class TestCrearResultadoExitoso(unittest.TestCase):
    """Tests para _crear_resultado_exitoso."""

    def setUp(self):
        self.validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock()
        )

    def test_crear_resultado_exitoso_completo(self):
        """Test: Crear resultado exitoso con todos los campos."""
        resultado_dict = {
            "aplica": True,
            "estado": "preliquidado",
            "valor_factura_sin_iva": 1000000.0,
            "valor_retencion": 40000.0,
            "base_gravable": 1000000.0,
            "conceptos_aplicados": [{"concepto": "Servicios"}],
            "observaciones": ["OK"]
        }

        resultado = self.validador._crear_resultado_exitoso(resultado_dict)

        self.assertTrue(resultado["aplica"])
        self.assertEqual(resultado["estado"], "preliquidado")
        self.assertEqual(resultado["valor_factura_sin_iva"], 1000000.0)
        self.assertEqual(resultado["valor_retencion"], 40000.0)
        self.assertEqual(resultado["valor_base"], 1000000.0)
        self.assertEqual(len(resultado["conceptos_aplicados"]), 1)
        self.assertEqual(resultado["observaciones"], ["OK"])

    def test_crear_resultado_exitoso_valores_default(self):
        """Test: Crear resultado con valores por defecto."""
        resultado_dict = {}

        resultado = self.validador._crear_resultado_exitoso(resultado_dict)

        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["estado"], "preliquidacion_sin_finalizar")
        self.assertEqual(resultado["valor_retencion"], 0.0)
        self.assertEqual(resultado["valor_factura_sin_iva"], 0.0)
        self.assertEqual(resultado["valor_base"], 0.0)
        self.assertEqual(resultado["conceptos_aplicados"], [])
        self.assertEqual(resultado["observaciones"], [])

    def test_crear_resultado_exitoso_valores_none(self):
        """Test: Edge case - campos con valor None."""
        resultado_dict = {
            "aplica": None,
            "valor_retencion": None,
            "conceptos_aplicados": None
        }

        resultado = self.validador._crear_resultado_exitoso(resultado_dict)

        # dict.get() retorna None si el valor existe pero es None
        # No aplica el default en este caso
        self.assertIsNone(resultado["aplica"])
        self.assertIsNone(resultado["valor_retencion"])
        self.assertIsNone(resultado["conceptos_aplicados"])

    def test_crear_resultado_valores_negativos(self):
        """Test: Edge case - valores negativos (no deberian pasar validaciones upstream)."""
        resultado_dict = {
            "valor_retencion": -1000.0,
            "valor_factura_sin_iva": -5000.0
        }

        resultado = self.validador._crear_resultado_exitoso(resultado_dict)

        # El metodo no valida, solo copia
        self.assertEqual(resultado["valor_retencion"], -1000.0)
        self.assertEqual(resultado["valor_factura_sin_iva"], -5000.0)


class TestProcesarResultadoNormal(unittest.TestCase):
    """Tests para _procesar_resultado_normal."""

    def setUp(self):
        self.validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock()
        )

    def test_procesar_resultado_con_error(self):
        """Test: Procesar resultado que contiene error."""
        resultado_dict = {"error": "Timeout en liquidador"}

        resultado = self.validador._procesar_resultado_normal(
            resultado_dict,
            False
        )

        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["estado"], "preliquidacion_sin_finalizar")
        self.assertIn("Timeout en liquidador", resultado["observaciones"])

    def test_procesar_resultado_exitoso_sin_pais(self):
        """Test: Procesar resultado exitoso sin facturacion extranjera."""
        resultado_dict = {
            "aplica": True,
            "valor_retencion": 50000.0,
            "base_gravable": 1000000.0
        }

        resultado = self.validador._procesar_resultado_normal(
            resultado_dict,
            False
        )

        self.assertTrue(resultado["aplica"])
        self.assertNotIn("pais_proveedor", resultado)

    def test_procesar_resultado_exitoso_con_pais(self):
        """Test: Procesar resultado con facturacion extranjera y pais."""
        resultado_dict = {
            "aplica": True,
            "valor_retencion": 100000.0,
            "pais_proveedor": "Estados Unidos"
        }

        resultado = self.validador._procesar_resultado_normal(
            resultado_dict,
            True
        )

        self.assertEqual(resultado["pais_proveedor"], "Estados Unidos")

    def test_procesar_facturacion_extranjera_sin_pais(self):
        """Test: Edge case - es_facturacion_extranjera pero sin pais_proveedor."""
        resultado_dict = {
            "aplica": True,
            "valor_retencion": 100000.0
        }

        resultado = self.validador._procesar_resultado_normal(
            resultado_dict,
            True  # Facturacion extranjera pero dict no tiene pais
        )

        self.assertNotIn("pais_proveedor", resultado)


class TestLogResultado(unittest.TestCase):
    """Tests para _log_resultado."""

    def setUp(self):
        self.validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock()
        )

    def test_log_resultado_con_retencion_positiva(self):
        """Test: Log con valor_retencion > 0."""
        with self.assertLogs(self.validador.logger, level='INFO') as cm:
            self.validador._log_resultado({"valor_retencion": 50000.0})

            self.assertTrue(any("$50,000.00" in message for message in cm.output))

    def test_log_resultado_sin_retencion(self):
        """Test: Log con valor_retencion = 0."""
        with self.assertLogs(self.validador.logger, level='INFO') as cm:
            self.validador._log_resultado({
                "valor_retencion": 0.0,
                "estado": "no_aplica"
            })

            self.assertTrue(any("Estado: no_aplica" in message for message in cm.output))

    def test_log_resultado_sin_estado(self):
        """Test: Edge case - sin campo estado."""
        with self.assertLogs(self.validador.logger, level='INFO') as cm:
            self.validador._log_resultado({"valor_retencion": 0.0})

            # Debe usar default "preliquidado"
            self.assertTrue(any("preliquidado" in message for message in cm.output))


class TestManejarError(unittest.TestCase):
    """Tests para _manejar_error."""

    def setUp(self):
        self.validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock()
        )

    def test_manejar_error_excepcion_normal(self):
        """Test: Manejar excepcion normal."""
        error = Exception("Error de prueba")

        with self.assertLogs(self.validador.logger, level='ERROR'):
            resultado = self.validador._manejar_error(error)

        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["error"], "Error de prueba")

    def test_manejar_error_excepcion_sin_mensaje(self):
        """Test: Edge case - excepcion sin mensaje."""
        error = Exception()

        resultado = self.validador._manejar_error(error)

        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["error"], "")

    def test_manejar_error_tipo_error(self):
        """Test: Manejar TypeError."""
        error = TypeError("Tipo incorrecto")

        resultado = self.validador._manejar_error(error)

        self.assertIn("Tipo incorrecto", resultado["error"])


class TestValidarOrquestador(unittest.IsolatedAsyncioTestCase):
    """Tests de integracion para validar() - orquestador principal."""

    async def asyncSetUp(self):
        self.mock_liquidador_retencion = Mock()
        self.mock_liquidador_retencion.liquidar_retefuente_seguro = Mock(
            return_value={"aplica": True, "valor_retencion": 40000.0}
        )

        self.validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock(),
            liquidador_retencion=self.mock_liquidador_retencion
        )

    async def test_validar_caso_normal_exitoso(self):
        """Test: Flujo completo caso normal exitoso."""
        with patch('app.validar_retefuente.guardar_archivo_json'):
            resultado = await self.validador.validar(
                resultados_analisis={"retefuente": {"valor": 1000000}},
                aplica_retencion=True,
                es_consorcio=False,
                es_recurso_extranjero=False,
                es_facturacion_extranjera=False,
                nit_administrativo="900123456",
                tipoMoneda="COP",
                archivos_directos=[],
                cache_archivos={}
            )

        self.assertIsNotNone(resultado)
        self.assertTrue(resultado["aplica"])

    async def test_validar_no_debe_procesar(self):
        """Test: No debe procesar - sin datos de retefuente."""
        resultado = await self.validador.validar(
            resultados_analisis={},
            aplica_retencion=True,
            es_consorcio=False,
            es_recurso_extranjero=False,
            es_facturacion_extranjera=False,
            nit_administrativo="900123456",
            tipoMoneda="COP",
            archivos_directos=[],
            cache_archivos={}
        )

        self.assertIsNone(resultado)

    @patch('app.validar_retefuente.crear_resultado_recurso_extranjero_retefuente')
    async def test_validar_recurso_extranjero(self, mock_crear):
        """Test: Flujo recurso extranjero."""
        mock_resultado = Mock()
        mock_resultado.aplica = False
        mock_resultado.estado = "recurso_fuente_extranjera"
        mock_resultado.valor_retencion = 0.0
        mock_resultado.valor_factura_sin_iva = 0.0
        mock_resultado.valor_base_retencion = 0.0
        mock_resultado.conceptos_aplicados = []
        mock_resultado.mensajes_error = []

        mock_crear.return_value = mock_resultado

        resultado = await self.validador.validar(
            resultados_analisis={},
            aplica_retencion=True,
            es_consorcio=False,
            es_recurso_extranjero=True,
            es_facturacion_extranjera=False,
            nit_administrativo="900123456",
            tipoMoneda="COP",
            archivos_directos=[],
            cache_archivos={}
        )

        self.assertIsNotNone(resultado)
        self.assertFalse(resultado["aplica"])
        self.assertEqual(resultado["estado"], "recurso_fuente_extranjera")

    async def test_validar_excepcion_durante_procesamiento(self):
        """Test: Manejo de excepcion durante procesamiento."""
        self.mock_liquidador_retencion.liquidar_retefuente_seguro.side_effect = Exception("Error critico")

        with patch('app.validar_retefuente.guardar_archivo_json'):
            resultado = await self.validador.validar(
                resultados_analisis={"retefuente": {}},
                aplica_retencion=True,
                es_consorcio=False,
                es_recurso_extranjero=False,
                es_facturacion_extranjera=False,
                nit_administrativo="900123456",
                tipoMoneda="COP",
                archivos_directos=[],
                cache_archivos={}
            )

        self.assertIsNotNone(resultado)
        self.assertFalse(resultado["aplica"])
        self.assertIn("error", resultado)


class TestValidarRetencionEnLaFuenteWrapper(unittest.IsolatedAsyncioTestCase):
    """Tests para funcion wrapper validar_retencion_en_la_fuente."""

    async def test_wrapper_instancia_validador(self):
        """Test: Wrapper instancia ValidadorRetefuente correctamente."""
        with patch('app.validar_retefuente.ValidadorRetefuente') as MockValidador:
            mock_instance = AsyncMock()
            mock_instance.validar.return_value = {"aplica": True}
            MockValidador.return_value = mock_instance

            resultado = await validar_retencion_en_la_fuente(
                resultados_analisis={},
                aplica_retencion=True,
                es_consorcio=False,
                es_recurso_extranjero=False,
                es_facturacion_extranjera=False,
                estructura_contable=1,
                db_manager=Mock(),
                nit_administrativo="900123456",
                tipoMoneda="COP",
                archivos_directos=[],
                cache_archivos={}
            )

            MockValidador.assert_called_once_with(
                estructura_contable=1,
                db_manager=unittest.mock.ANY
            )
            mock_instance.validar.assert_called_once()
            self.assertEqual(resultado["aplica"], True)

    async def test_wrapper_delega_parametros_correctamente(self):
        """Test: Wrapper delega todos los parametros correctamente."""
        with patch('app.validar_retefuente.ValidadorRetefuente') as MockValidador:
            mock_instance = AsyncMock()
            mock_instance.validar.return_value = None
            MockValidador.return_value = mock_instance

            await validar_retencion_en_la_fuente(
                resultados_analisis={"test": "data"},
                aplica_retencion=True,
                es_consorcio=True,
                es_recurso_extranjero=False,
                es_facturacion_extranjera=True,
                estructura_contable=5,
                db_manager=Mock(),
                nit_administrativo="800999888",
                tipoMoneda="USD",
                archivos_directos=["file1"],
                cache_archivos={"key": "value"}
            )

            llamada_validar = mock_instance.validar.call_args
            self.assertEqual(llamada_validar.kwargs["nit_administrativo"], "800999888")
            self.assertEqual(llamada_validar.kwargs["tipoMoneda"], "USD")
            self.assertTrue(llamada_validar.kwargs["es_consorcio"])
            self.assertTrue(llamada_validar.kwargs["es_facturacion_extranjera"])


class TestEdgeCasesCompletos(unittest.IsolatedAsyncioTestCase):
    """Tests para edge cases completos y combinaciones extremas."""

    async def asyncSetUp(self):
        self.validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock()
        )

    async def test_todas_flags_false(self):
        """Test: Todas las flags en False."""
        resultado = await self.validador.validar(
            resultados_analisis={},
            aplica_retencion=False,
            es_consorcio=False,
            es_recurso_extranjero=False,
            es_facturacion_extranjera=False,
            nit_administrativo="",
            tipoMoneda="COP",
            archivos_directos=[],
            cache_archivos={}
        )

        self.assertIsNone(resultado)

    async def test_todas_flags_true_excepto_datos(self):
        """Test: Todas flags True pero sin datos de retefuente."""
        resultado = await self.validador.validar(
            resultados_analisis={},
            aplica_retencion=True,
            es_consorcio=True,
            es_recurso_extranjero=True,
            es_facturacion_extranjera=True,
            nit_administrativo="900123456",
            tipoMoneda="COP",
            archivos_directos=[],
            cache_archivos={}
        )

        # Debe manejar caso especial de recurso extranjero
        self.assertIsNotNone(resultado)

    async def test_valores_monetarios_extremos(self):
        """Test: Valores monetarios extremos."""
        mock_liquidador = Mock()
        mock_liquidador.liquidar_retefuente_seguro = Mock(return_value={
            "aplica": True,
            "valor_retencion": 999999999.99,
            "valor_factura_sin_iva": 9999999999.99,
            "base_gravable": 9999999999.99,
            "conceptos_aplicados": [],
            "observaciones": []
        })

        validador = ValidadorRetefuente(
            estructura_contable=1,
            db_manager=Mock(),
            liquidador_retencion=mock_liquidador
        )

        with patch('app.validar_retefuente.guardar_archivo_json'):
            resultado = await validador.validar(
                resultados_analisis={"retefuente": {"valor": 9999999999.99}},
                aplica_retencion=True,
                es_consorcio=False,
                es_recurso_extranjero=False,
                es_facturacion_extranjera=False,
                nit_administrativo="900123456",
                tipoMoneda="COP",
                archivos_directos=[],
                cache_archivos={}
            )

        self.assertEqual(resultado["valor_retencion"], 999999999.99)

    def test_preparar_analisis_caracteres_especiales(self):
        """Test: Edge case - caracteres especiales en strings."""
        resultado = self.validador._preparar_analisis_data(
            {"concepto": "Servicios <script>alert('xss')</script>"},
            False,
            "900!@#$%^&*()"
        )

        # El metodo no sanitiza, solo pasa los datos
        self.assertEqual(resultado["nit_administrativo"], "900!@#$%^&*()")


def suite():
    """Crear suite de tests."""
    suite = unittest.TestSuite()

    # Tests unitarios
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestValidadorRetefuenteInit))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDebeProcesarRetefuente))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestManejarCasoEspecial))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestProcesarConsorcio))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPrepararAnalisisData))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestEjecutarLiquidacionNormal))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCrearResultadoError))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCrearResultadoExitoso))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestProcesarResultadoNormal))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestLogResultado))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestManejarError))

    # Tests de integracion
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestValidarOrquestador))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestValidarRetencionEnLaFuenteWrapper))

    # Tests de edge cases
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestEdgeCasesCompletos))

    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
