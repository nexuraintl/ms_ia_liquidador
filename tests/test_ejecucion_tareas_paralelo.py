"""
Tests unitarios para modulo app.ejecucion_tareas_paralelo

Suite completa de tests para verificar funcionamiento de:
- Dataclasses: ResultadoEjecucion, ResultadoEjecucionParalela
- EjecutorTareaIndividual
- ControladorConcurrencia
- ProcesadorResultados
- CoordinadorEjecucionParalela
- Funcion fachada: ejecutar_tareas_paralelo

Autor: Miguel Angel Jaramillo Durango
"""

import unittest
import asyncio
import logging
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Importar modulo a testear
from app.ejecucion_tareas_paralelo import (
    ResultadoEjecucion,
    ResultadoEjecucionParalela,
    EjecutorTareaIndividual,
    ControladorConcurrencia,
    ProcesadorResultados,
    CoordinadorEjecucionParalela,
    ejecutar_tareas_paralelo
)

# Importar TareaAnalisis para crear mocks
from app.preparacion_tareas_analisis import TareaAnalisis


# =================================
# FIXTURES Y MOCKS
# =================================


async def tarea_mock_exitosa():
    """Mock de tarea que completa exitosamente."""
    await asyncio.sleep(0.01)  # Simular trabajo async
    return {"aplica": True, "valor": 1000}


async def tarea_mock_con_error():
    """Mock de tarea que lanza excepcion."""
    await asyncio.sleep(0.01)
    raise ValueError("Error simulado en tarea")


async def tarea_mock_lenta():
    """Mock de tarea que toma mas tiempo."""
    await asyncio.sleep(0.05)
    return {"aplica": True, "valor": 2000}


class MockPydanticModel:
    """Mock de modelo Pydantic con metodo dict()."""

    def __init__(self, data):
        self.data = data

    def dict(self):
        return self.data


# =================================
# TESTS DATACLASSES
# =================================


class TestResultadoEjecucion(unittest.TestCase):
    """Tests para dataclass ResultadoEjecucion."""

    def test_resultado_exitoso(self):
        """Verificar creacion de resultado exitoso."""
        resultado = ResultadoEjecucion(
            nombre_impuesto="retefuente",
            resultado={"aplica": True, "valor": 100000},
            tiempo_ejecucion=2.5,
            exitoso=True,
            error=None
        )

        self.assertEqual(resultado.nombre_impuesto, "retefuente")
        self.assertEqual(resultado.resultado["valor"], 100000)
        self.assertEqual(resultado.tiempo_ejecucion, 2.5)
        self.assertTrue(resultado.exitoso)
        self.assertIsNone(resultado.error)

    def test_resultado_con_error(self):
        """Verificar creacion de resultado con error."""
        resultado = ResultadoEjecucion(
            nombre_impuesto="iva_reteiva",
            resultado={"error": "Error de conexion"},
            tiempo_ejecucion=1.2,
            exitoso=False,
            error="Error de conexion"
        )

        self.assertEqual(resultado.nombre_impuesto, "iva_reteiva")
        self.assertFalse(resultado.exitoso)
        self.assertEqual(resultado.error, "Error de conexion")
        self.assertIn("error", resultado.resultado)


class TestResultadoEjecucionParalela(unittest.TestCase):
    """Tests para dataclass ResultadoEjecucionParalela."""

    def test_creacion_resultado_paralelo(self):
        """Verificar creacion de resultado paralelo."""
        resultado = ResultadoEjecucionParalela(
            resultados_analisis={
                "retefuente": {"aplica": True},
                "iva": {"aplica": False}
            },
            total_tareas=3,
            tareas_exitosas=2,
            tareas_fallidas=1,
            tiempo_total=5.2,
            impuestos_procesados=["retefuente", "iva", "ica"]
        )

        self.assertEqual(resultado.total_tareas, 3)
        self.assertEqual(resultado.tareas_exitosas, 2)
        self.assertEqual(resultado.tareas_fallidas, 1)
        self.assertEqual(resultado.tiempo_total, 5.2)
        self.assertEqual(len(resultado.impuestos_procesados), 3)

    def test_metricas_calculadas(self):
        """Verificar que metricas son correctas."""
        resultado = ResultadoEjecucionParalela(
            resultados_analisis={"imp1": {}, "imp2": {}},
            total_tareas=2,
            tareas_exitosas=2,
            tareas_fallidas=0,
            tiempo_total=3.0,
            impuestos_procesados=["imp1", "imp2"]
        )

        # Verificar que todas exitosas
        self.assertEqual(resultado.tareas_exitosas, resultado.total_tareas)
        self.assertEqual(resultado.tareas_fallidas, 0)


# =================================
# TESTS EJECUTOR TAREA INDIVIDUAL
# =================================


class TestEjecutorTareaIndividual(unittest.IsolatedAsyncioTestCase):
    """Tests para EjecutorTareaIndividual."""

    def setUp(self):
        """Setup ejecutado antes de cada test."""
        self.mock_logger = Mock(spec=logging.Logger)
        self.ejecutor = EjecutorTareaIndividual(logger=self.mock_logger)

    async def test_ejecutar_tarea_exitosa(self):
        """Verificar ejecucion exitosa de tarea."""
        tarea = tarea_mock_exitosa()

        resultado = await self.ejecutor.ejecutar_tarea(
            nombre_impuesto="retefuente",
            tarea=tarea,
            worker_id=1
        )

        # Verificar resultado exitoso
        self.assertTrue(resultado.exitoso)
        self.assertEqual(resultado.nombre_impuesto, "retefuente")
        self.assertEqual(resultado.resultado["valor"], 1000)
        self.assertIsNone(resultado.error)
        self.assertGreater(resultado.tiempo_ejecucion, 0)

        # Verificar logging
        self.mock_logger.info.assert_called()

    async def test_ejecutar_tarea_con_error(self):
        """Verificar manejo de error en ejecucion."""
        tarea = tarea_mock_con_error()

        resultado = await self.ejecutor.ejecutar_tarea(
            nombre_impuesto="iva_reteiva",
            tarea=tarea,
            worker_id=2
        )

        # Verificar resultado con error
        self.assertFalse(resultado.exitoso)
        self.assertEqual(resultado.nombre_impuesto, "iva_reteiva")
        self.assertIsNotNone(resultado.error)
        self.assertIn("Error simulado", resultado.error)
        self.assertGreater(resultado.tiempo_ejecucion, 0)

        # Verificar logging de error
        self.mock_logger.error.assert_called()

    async def test_medicion_tiempo(self):
        """Verificar medicion correcta de tiempo de ejecucion."""
        tarea = tarea_mock_lenta()

        resultado = await self.ejecutor.ejecutar_tarea(
            nombre_impuesto="ica",
            tarea=tarea,
            worker_id=3
        )

        # Verificar que tiempo sea razonable (>= 0.05s por el sleep)
        self.assertGreaterEqual(resultado.tiempo_ejecucion, 0.05)
        self.assertLess(resultado.tiempo_ejecucion, 1.0)  # No deberia tardar mas de 1s


# =================================
# TESTS CONTROLADOR CONCURRENCIA
# =================================


class TestControladorConcurrencia(unittest.IsolatedAsyncioTestCase):
    """Tests para ControladorConcurrencia."""

    async def test_inicializacion(self):
        """Verificar inicializacion correcta del controlador."""
        controlador = ControladorConcurrencia(max_workers=4)

        self.assertEqual(controlador.max_workers, 4)
        self.assertIsNotNone(controlador.semaforo)

    async def test_ejecutar_con_semaforo(self):
        """Verificar ejecucion con semaforo."""
        controlador = ControladorConcurrencia(max_workers=2)

        tarea = tarea_mock_exitosa()
        resultado = await controlador.ejecutar_con_semaforo(tarea)

        self.assertEqual(resultado["valor"], 1000)

    async def test_limite_workers(self):
        """Verificar que no se excede limite de workers simultaneos."""
        controlador = ControladorConcurrencia(max_workers=2)

        # Crear tareas que registren cuando empiezan
        tareas_activas = []

        async def tarea_que_registra():
            tareas_activas.append(1)
            max_activas = len(tareas_activas)
            await asyncio.sleep(0.05)
            tareas_activas.pop()
            return max_activas

        # Ejecutar 5 tareas (mas que el limite de 2 workers)
        tareas = [
            controlador.ejecutar_con_semaforo(tarea_que_registra())
            for _ in range(5)
        ]

        resultados = await asyncio.gather(*tareas)

        # Verificar que nunca hubo mas de 2 tareas simultaneas
        # Nota: Este test es aproximado por la naturaleza asincrona
        self.assertTrue(all(r <= 2 for r in resultados if r is not None))


# =================================
# TESTS PROCESADOR RESULTADOS
# =================================


class TestProcesadorResultados(unittest.TestCase):
    """Tests para ProcesadorResultados."""

    def setUp(self):
        """Setup ejecutado antes de cada test."""
        self.mock_logger = Mock(spec=logging.Logger)
        self.procesador = ProcesadorResultados(logger=self.mock_logger)

    def test_procesar_resultado_dict(self):
        """Verificar procesamiento de resultado tipo dict."""
        resultado_ejecucion = ResultadoEjecucion(
            nombre_impuesto="retefuente",
            resultado={"aplica": True, "valor": 1000},
            tiempo_ejecucion=1.0,
            exitoso=True
        )

        resultado_dict = self.procesador.procesar_resultado_individual(resultado_ejecucion)

        self.assertIsInstance(resultado_dict, dict)
        self.assertEqual(resultado_dict["valor"], 1000)

    def test_procesar_resultado_pydantic(self):
        """Verificar procesamiento de resultado tipo Pydantic model."""
        mock_pydantic = MockPydanticModel({"aplica": True, "valor": 2000})

        resultado_ejecucion = ResultadoEjecucion(
            nombre_impuesto="iva",
            resultado=mock_pydantic,
            tiempo_ejecucion=1.5,
            exitoso=True
        )

        resultado_dict = self.procesador.procesar_resultado_individual(resultado_ejecucion)

        self.assertIsInstance(resultado_dict, dict)
        self.assertEqual(resultado_dict["valor"], 2000)

    def test_procesar_resultado_excepcion(self):
        """Verificar procesamiento de resultado con excepcion."""
        resultado_ejecucion = ResultadoEjecucion(
            nombre_impuesto="ica",
            resultado={"error": "Error de conexion"},
            tiempo_ejecucion=0.5,
            exitoso=False,
            error="Error de conexion"
        )

        resultado_dict = self.procesador.procesar_resultado_individual(resultado_ejecucion)

        self.assertIsInstance(resultado_dict, dict)
        self.assertIn("error", resultado_dict)

    def test_agregar_resultados_metricas(self):
        """Verificar calculo correcto de metricas agregadas."""
        resultados = [
            ResultadoEjecucion("retefuente", {"valor": 100}, 1.0, True),
            ResultadoEjecucion("iva", {"valor": 200}, 2.0, True),
            ResultadoEjecucion("ica", {"error": "fallo"}, 0.5, False, "fallo")
        ]

        resultado_agregado = self.procesador.agregar_resultados(resultados)

        # Verificar metricas
        self.assertEqual(resultado_agregado.total_tareas, 3)
        self.assertEqual(resultado_agregado.tareas_exitosas, 2)
        self.assertEqual(resultado_agregado.tareas_fallidas, 1)
        self.assertEqual(resultado_agregado.tiempo_total, 3.5)
        self.assertEqual(len(resultado_agregado.impuestos_procesados), 3)

        # Verificar resultados
        self.assertIn("retefuente", resultado_agregado.resultados_analisis)
        self.assertIn("iva", resultado_agregado.resultados_analisis)
        self.assertIn("ica", resultado_agregado.resultados_analisis)


# =================================
# TESTS COORDINADOR EJECUCION PARALELA
# =================================


class TestCoordinadorEjecucionParalela(unittest.IsolatedAsyncioTestCase):
    """Tests para CoordinadorEjecucionParalela (integracion)."""

    async def test_ejecutar_multiples_tareas_exitosas(self):
        """Verificar ejecucion paralela de multiples tareas exitosas."""
        coordinador = CoordinadorEjecucionParalela(max_workers=4)

        tareas = [
            TareaAnalisis(nombre="retefuente", coroutine=tarea_mock_exitosa()),
            TareaAnalisis(nombre="iva", coroutine=tarea_mock_exitosa()),
            TareaAnalisis(nombre="ica", coroutine=tarea_mock_exitosa())
        ]

        resultado = await coordinador.ejecutar_tareas_paralelo(tareas)

        # Verificar metricas
        self.assertEqual(resultado.total_tareas, 3)
        self.assertEqual(resultado.tareas_exitosas, 3)
        self.assertEqual(resultado.tareas_fallidas, 0)

        # Verificar resultados
        self.assertEqual(len(resultado.resultados_analisis), 3)
        self.assertIn("retefuente", resultado.resultados_analisis)
        self.assertIn("iva", resultado.resultados_analisis)
        self.assertIn("ica", resultado.resultados_analisis)

    async def test_ejecutar_con_algunas_tareas_fallidas(self):
        """Verificar manejo correcto cuando algunas tareas fallan."""
        coordinador = CoordinadorEjecucionParalela(max_workers=4)

        tareas = [
            TareaAnalisis(nombre="retefuente", coroutine=tarea_mock_exitosa()),
            TareaAnalisis(nombre="iva", coroutine=tarea_mock_con_error()),
            TareaAnalisis(nombre="ica", coroutine=tarea_mock_exitosa())
        ]

        resultado = await coordinador.ejecutar_tareas_paralelo(tareas)

        # Verificar metricas
        self.assertEqual(resultado.total_tareas, 3)
        self.assertEqual(resultado.tareas_exitosas, 2)
        self.assertEqual(resultado.tareas_fallidas, 1)

        # Verificar que tareas exitosas tienen resultados correctos
        self.assertEqual(resultado.resultados_analisis["retefuente"]["valor"], 1000)
        self.assertEqual(resultado.resultados_analisis["ica"]["valor"], 1000)

        # Verificar que tarea fallida tiene error
        self.assertIn("error", resultado.resultados_analisis["iva"])

    async def test_ejecutar_todas_tareas_fallidas(self):
        """Verificar comportamiento cuando todas las tareas fallan."""
        coordinador = CoordinadorEjecucionParalela(max_workers=4)

        tareas = [
            TareaAnalisis(nombre="retefuente", coroutine=tarea_mock_con_error()),
            TareaAnalisis(nombre="iva", coroutine=tarea_mock_con_error())
        ]

        resultado = await coordinador.ejecutar_tareas_paralelo(tareas)

        # Verificar metricas
        self.assertEqual(resultado.total_tareas, 2)
        self.assertEqual(resultado.tareas_exitosas, 0)
        self.assertEqual(resultado.tareas_fallidas, 2)

        # Verificar que todas tienen error
        self.assertIn("error", resultado.resultados_analisis["retefuente"])
        self.assertIn("error", resultado.resultados_analisis["iva"])

    async def test_medicion_tiempo_total(self):
        """Verificar medicion de tiempo total."""
        coordinador = CoordinadorEjecucionParalela(max_workers=4)

        tareas = [
            TareaAnalisis(nombre="tarea1", coroutine=tarea_mock_exitosa()),
            TareaAnalisis(nombre="tarea2", coroutine=tarea_mock_exitosa())
        ]

        resultado = await coordinador.ejecutar_tareas_paralelo(tareas)

        # Verificar que tiempo total es razonable
        self.assertGreater(resultado.tiempo_total, 0)
        # Con 2 tareas de 0.01s cada una en paralelo, deberia ser ~ 0.02s
        self.assertLess(resultado.tiempo_total, 1.0)


# =================================
# TESTS FUNCION FACHADA
# =================================


class TestFuncionFachada(unittest.IsolatedAsyncioTestCase):
    """Tests para funcion fachada ejecutar_tareas_paralelo."""

    async def test_api_publica_basica(self):
        """Verificar que API publica funciona correctamente."""
        tareas = [
            TareaAnalisis(nombre="retefuente", coroutine=tarea_mock_exitosa()),
            TareaAnalisis(nombre="iva", coroutine=tarea_mock_exitosa())
        ]

        resultado = await ejecutar_tareas_paralelo(
            tareas_analisis=tareas,
            max_workers=4
        )

        # Verificar resultado
        self.assertIsInstance(resultado, ResultadoEjecucionParalela)
        self.assertEqual(resultado.total_tareas, 2)
        self.assertEqual(resultado.tareas_exitosas, 2)

    async def test_api_publica_con_max_workers_personalizado(self):
        """Verificar que max_workers se puede personalizar."""
        tareas = [
            TareaAnalisis(nombre="tarea1", coroutine=tarea_mock_exitosa()),
            TareaAnalisis(nombre="tarea2", coroutine=tarea_mock_exitosa()),
            TareaAnalisis(nombre="tarea3", coroutine=tarea_mock_exitosa())
        ]

        # Ejecutar con solo 1 worker
        resultado = await ejecutar_tareas_paralelo(
            tareas_analisis=tareas,
            max_workers=1
        )

        self.assertEqual(resultado.total_tareas, 3)
        self.assertEqual(resultado.tareas_exitosas, 3)

    async def test_api_publica_sin_tareas(self):
        """Verificar comportamiento cuando no hay tareas."""
        resultado = await ejecutar_tareas_paralelo(
            tareas_analisis=[],
            max_workers=4
        )

        # Verificar que resultado es valido con 0 tareas
        self.assertEqual(resultado.total_tareas, 0)
        self.assertEqual(resultado.tareas_exitosas, 0)
        self.assertEqual(resultado.tareas_fallidas, 0)


# =================================
# MAIN TEST RUNNER
# =================================


if __name__ == '__main__':
    unittest.main()
