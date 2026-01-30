"""
EJECUCION DE TAREAS DE ANALISIS EN PARALELO - MODULO DE NEGOCIO
================================================================

Modulo responsable de ejecutar tareas async de analisis de impuestos en paralelo
con control de concurrencia y manejo de errores robusto.

ARQUITECTURA:
- 4 clases con responsabilidad unica cada una
- Inyeccion de dependencias por constructor
- Extensible para nuevos tipos de ejecucion
- Diseño que facilita testing unitario

Autor: Miguel Angel Jaramillo Durango
"""

import logging
import traceback
import asyncio
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

# Importar TareaAnalisis desde modulo de preparacion
from app.preparacion_tareas_analisis import TareaAnalisis

logger = logging.getLogger(__name__)


# =================================
# DATACLASSES
# =================================


@dataclass
class ResultadoEjecucion:
    """
    Encapsula resultado de ejecucion de una tarea individual.

    Attributes:
        nombre_impuesto: Identificador del impuesto analizado.
                        Ejemplos: "retefuente", "iva_reteiva", "ica"
        resultado: Dict con resultado del analisis o excepcion.
                  Estructura varia segun el impuesto analizado.
        tiempo_ejecucion: Tiempo en segundos que tomo la ejecucion.
        exitoso: Flag booleano indicando si la ejecucion fue exitosa.
        error: Mensaje de error si hubo fallo (None si exitoso).

    Example:
        >>> resultado = ResultadoEjecucion(
        ...     nombre_impuesto="retefuente",
        ...     resultado={"aplica": True, "valor": 100000},
        ...     tiempo_ejecucion=2.5,
        ...     exitoso=True,
        ...     error=None
        ... )
        >>> print(resultado.exitoso)
        True
        >>> print(resultado.tiempo_ejecucion)
        2.5

    Notes:
        - Type-safe: typing completo para prevenir errores
        - Compatible con dataclass para facilitar testing
        - Permite encapsular tanto exitos como errores
    """

    nombre_impuesto: str
    resultado: Any
    tiempo_ejecucion: float
    exitoso: bool
    error: Optional[str] = None


@dataclass
class ResultadoEjecucionParalela:
    """
    Encapsula resultado completo de ejecucion paralela de multiples tareas.

    Contiene todos los resultados individuales agregados, metricas de ejecucion
    y estado general del procesamiento paralelo.

    Attributes:
        resultados_analisis: Dict mapeando nombre_impuesto -> resultado.
                            Ejemplo: {"retefuente": {...}, "iva": {...}}
        total_tareas: Numero total de tareas ejecutadas.
        tareas_exitosas: Numero de tareas completadas exitosamente.
        tareas_fallidas: Numero de tareas que fallaron.
        tiempo_total: Tiempo total de ejecucion en segundos.
        impuestos_procesados: Lista de nombres de impuestos procesados.
                             Ejemplo: ["retefuente", "iva_reteiva", "ica"]

    Example:
        >>> resultado = ResultadoEjecucionParalela(
        ...     resultados_analisis={"retefuente": {...}, "iva": {...}},
        ...     total_tareas=3,
        ...     tareas_exitosas=2,
        ...     tareas_fallidas=1,
        ...     tiempo_total=5.2,
        ...     impuestos_procesados=["retefuente", "iva", "ica"]
        ... )
        >>> print(f"{resultado.tareas_exitosas}/{resultado.total_tareas} exitosas")
        2/3 exitosas

    Notes:
        - Incluye metricas utiles para logging y debugging
        - Compatible con dataclass para facilitar testing
        - Formato compatible con guardar_archivo_json de config.py
    """

    resultados_analisis: Dict[str, Any]
    total_tareas: int
    tareas_exitosas: int
    tareas_fallidas: int
    tiempo_total: float
    impuestos_procesados: List[str]


# =================================
# CLASE 1: EJECUTOR DE TAREA INDIVIDUAL
# =================================


class EjecutorTareaIndividual:
    """
    Ejecuta una tarea individual con medicion de tiempo y manejo de errores.

    Responsabilidades:
    - Ejecutar tarea asincrona
    - Medir tiempo de ejecucion
    - Capturar y registrar errores
    - Logging de inicio/fin de tarea

    Attributes:
        logger: Logger para registrar eventos de ejecucion.

    Example:
        >>> ejecutor = EjecutorTareaIndividual(logger=logger)
        >>> resultado = await ejecutor.ejecutar_tarea(
        ...     nombre_impuesto="retefuente",
        ...     tarea=tarea_async,
        ...     worker_id=1
        ... )
        >>> print(resultado.exitoso)
        True
    """

    def __init__(self, logger: logging.Logger):
        """
        Inicializa ejecutor con logger inyectado.

        Args:
            logger: Logger para registrar eventos de ejecucion.
        """
        self.logger = logger

    async def ejecutar_tarea(
        self,
        nombre_impuesto: str,
        tarea: Any,
        worker_id: int
    ) -> ResultadoEjecucion:
        """
        Ejecuta una tarea individual con logging y medicion de tiempo.

        Args:
            nombre_impuesto: Identificador del impuesto a analizar.
            tarea: Coroutine async a ejecutar.
            worker_id: ID del worker ejecutando la tarea (para logging).

        Returns:
            ResultadoEjecucion con resultado o error encapsulado.

        Example:
            >>> resultado = await ejecutor.ejecutar_tarea(
            ...     nombre_impuesto="iva_reteiva",
            ...     tarea=analizar_iva_async(),
            ...     worker_id=2
            ... )
            >>> if resultado.exitoso:
            ...     print(f"IVA analizado en {resultado.tiempo_ejecucion:.2f}s")

        Notes:
            - Captura TODAS las excepciones para evitar fallo del worker
            - Registra traceback completo en caso de error
            - Mide tiempo con datetime para precision
        """
        inicio = datetime.now()
        self.logger.info(f" Worker {worker_id}: Iniciando analisis de {nombre_impuesto}")

        try:
            resultado = await tarea
            tiempo_ejecucion = (datetime.now() - inicio).total_seconds()
            self.logger.info(
                f" Worker {worker_id}: {nombre_impuesto} completado en {tiempo_ejecucion:.2f}s"
            )

            return ResultadoEjecucion(
                nombre_impuesto=nombre_impuesto,
                resultado=resultado,
                tiempo_ejecucion=tiempo_ejecucion,
                exitoso=True,
                error=None
            )

        except Exception as e:
            tiempo_ejecucion = (datetime.now() - inicio).total_seconds()
            error_msg = str(e)
            self.logger.error(
                f" Worker {worker_id}: Error en {nombre_impuesto} tras {tiempo_ejecucion:.2f}s: {error_msg}"
            )
            self.logger.error(traceback.format_exc())

            return ResultadoEjecucion(
                nombre_impuesto=nombre_impuesto,
                resultado={"error": error_msg},
                tiempo_ejecucion=tiempo_ejecucion,
                exitoso=False,
                error=error_msg
            )


# =================================
# CLASE 2: CONTROLADOR DE CONCURRENCIA
# =================================


class ControladorConcurrencia:
    """
    Controla concurrencia de ejecucion con semaforo.

    Responsabilidades:
    - Crear y gestionar semaforo asyncio
    - Limitar numero de workers simultaneos
    - Proporcionar contexto de ejecucion controlada

    Attributes:
        max_workers: Numero maximo de workers simultaneos permitidos.
        semaforo: Semaforo asyncio para control de concurrencia.

    Example:
        >>> controlador = ControladorConcurrencia(max_workers=4)
        >>> resultado = await controlador.ejecutar_con_semaforo(tarea_async)
    """

    def __init__(self, max_workers: int = 4):
        """
        Inicializa controlador con numero maximo de workers.

        Args:
            max_workers: Numero maximo de workers simultaneos.
                        Default: 4 (optimizado para llamadas a Gemini).
        """
        self.max_workers = max_workers
        self.semaforo = asyncio.Semaphore(max_workers)

    async def ejecutar_con_semaforo(self, tarea: Any) -> Any:
        """
        Ejecuta tarea dentro del contexto del semaforo.

        Garantiza que no se excedan max_workers simultaneos.
        Si max_workers tareas estan ejecutando, la nueva tarea espera.

        Args:
            tarea: Coroutine async a ejecutar con control de concurrencia.

        Returns:
            Resultado de la tarea ejecutada.

        Example:
            >>> async with controlador.semaforo:
            ...     resultado = await tarea_async()

        Notes:
            - El semaforo automaticamente libera al completar la tarea
            - Otras tareas en espera obtienen acceso en orden FIFO
        """
        async with self.semaforo:
            return await tarea


# =================================
# CLASE 3: PROCESADOR DE RESULTADOS
# =================================


class ProcesadorResultados:
    """
    Procesa y mapea resultados de ejecuciones paralelas.

    Responsabilidades:
    - Convertir resultados a diccionarios
    - Manejar diferentes tipos de resultados (dict, Pydantic, Exception)
    - Calcular metricas de ejecucion (exitosos, fallidos)

    Attributes:
        logger: Logger para registrar eventos de procesamiento.

    Example:
        >>> procesador = ProcesadorResultados(logger=logger)
        >>> resultado_final = procesador.agregar_resultados(resultados_lista)
        >>> print(f"Exitosas: {resultado_final.tareas_exitosas}")
    """

    def __init__(self, logger: logging.Logger):
        """
        Inicializa procesador con logger inyectado.

        Args:
            logger: Logger para registrar eventos de procesamiento.
        """
        self.logger = logger

    def procesar_resultado_individual(
        self,
        resultado_ejecucion: ResultadoEjecucion
    ) -> Dict[str, Any]:
        """
        Procesa resultado individual a formato de diccionario.

        Maneja conversiones de diferentes tipos:
        - Pydantic models: llama a .dict()
        - Dicts nativos: retorna directamente
        - Excepciones: encapsula en {"error": mensaje}

        Args:
            resultado_ejecucion: ResultadoEjecucion a procesar.

        Returns:
            Dict con resultado procesado.

        Example:
            >>> resultado_dict = procesador.procesar_resultado_individual(resultado)
            >>> if "error" in resultado_dict:
            ...     print(f"Error: {resultado_dict['error']}")

        Notes:
            - Maneja automaticamente conversion de Pydantic a dict
            - Preserva estructura de dict nativo
            - Garantiza siempre retornar dict (nunca None)
        """
        resultado = resultado_ejecucion.resultado

        # Caso 1: Resultado es un modelo Pydantic con metodo dict()
        if hasattr(resultado, 'dict'):
            return resultado.dict()

        # Caso 2: Resultado es dict nativo
        elif isinstance(resultado, dict):
            return resultado

        # Caso 3: Resultado es otro tipo (convertir a dict)
        else:
            self.logger.warning(
                f"Resultado de {resultado_ejecucion.nombre_impuesto} no es dict ni Pydantic: {type(resultado)}"
            )
            return {"resultado": str(resultado)}

    def agregar_resultados(
        self,
        resultados: List[ResultadoEjecucion]
    ) -> ResultadoEjecucionParalela:
        """
        Agrega multiples resultados y calcula metricas.

        Procesa lista de ResultadoEjecucion y genera:
        - Dict mapeando nombre_impuesto -> resultado
        - Metricas de ejecucion (exitosas, fallidas, tiempos)

        Args:
            resultados: Lista de ResultadoEjecucion a agregar.

        Returns:
            ResultadoEjecucionParalela con todos los resultados y stats.

        Example:
            >>> resultados = [resultado1, resultado2, resultado3]
            >>> agregado = procesador.agregar_resultados(resultados)
            >>> print(f"{agregado.tareas_exitosas}/{agregado.total_tareas} exitosas")
            2/3 exitosas

        Notes:
            - Calcula tiempo total como suma de tiempos individuales
            - Cuenta exitosas y fallidas automaticamente
            - Preserva todos los resultados (exitosos y fallidos)
        """
        resultados_analisis = {}
        tareas_exitosas = 0
        tareas_fallidas = 0
        tiempo_total = 0.0
        impuestos_procesados = []

        for resultado_ejecucion in resultados:
            # Procesar resultado individual
            resultado_dict = self.procesar_resultado_individual(resultado_ejecucion)
            resultados_analisis[resultado_ejecucion.nombre_impuesto] = resultado_dict

            # Actualizar metricas
            if resultado_ejecucion.exitoso:
                tareas_exitosas += 1
            else:
                tareas_fallidas += 1

            tiempo_total += resultado_ejecucion.tiempo_ejecucion
            impuestos_procesados.append(resultado_ejecucion.nombre_impuesto)

        return ResultadoEjecucionParalela(
            resultados_analisis=resultados_analisis,
            total_tareas=len(resultados),
            tareas_exitosas=tareas_exitosas,
            tareas_fallidas=tareas_fallidas,
            tiempo_total=tiempo_total,
            impuestos_procesados=impuestos_procesados
        )


# =================================
# CLASE 4: COORDINADOR DE EJECUCION PARALELA (FACHADA)
# =================================


class CoordinadorEjecucionParalela:
    """
    Coordina ejecucion paralela de multiples tareas con control de concurrencia.

    Coordina el flujo completo:
    1. Controlar concurrencia (ControladorConcurrencia)
    2. Ejecutar tareas individuales (EjecutorTareaIndividual)
    3. Procesar resultados (ProcesadorResultados)
    4. Retornar resultado estructurado (ResultadoEjecucionParalela)

    Attributes:
        max_workers: Numero maximo de workers simultaneos.
        logger: Logger para registrar eventos de coordinacion.
        controlador_concurrencia: Controlador de concurrencia con semaforo.
        ejecutor_tarea: Ejecutor de tareas individuales.
        procesador_resultados: Procesador de resultados agregados.

    Example:
        >>> coordinador = CoordinadorEjecucionParalela(max_workers=4)
        >>> resultado = await coordinador.ejecutar_tareas_paralelo(tareas)
        >>> print(f"Completadas: {resultado.tareas_exitosas}/{resultado.total_tareas}")
    """

    def __init__(
        self,
        max_workers: int = 4,
        logger: Optional[logging.Logger] = None
    ):
        """
        Inicializa coordinador con componentes especializados.

        Args:
            max_workers: Numero maximo de workers simultaneos. Default: 4.
            logger: Logger personalizado (si None, usa logger del modulo).
        """
        self.max_workers = max_workers
        self.logger = logger or globals()['logger']

        # Instanciar componentes especializados (inyeccion de dependencias)
        self.controlador_concurrencia = ControladorConcurrencia(max_workers)
        self.ejecutor_tarea = EjecutorTareaIndividual(self.logger)
        self.procesador_resultados = ProcesadorResultados(self.logger)

    async def ejecutar_tareas_paralelo(
        self,
        tareas_analisis: List[TareaAnalisis]
    ) -> ResultadoEjecucionParalela:
        """
        Ejecuta todas las tareas en paralelo con control de concurrencia.

        Flujo de ejecucion:
        1. Crear wrapper async para cada tarea con semaforo
        2. Ejecutar todas en paralelo con asyncio.gather
        3. Procesar resultados individuales
        4. Agregar metricas y retornar resultado estructurado

        Args:
            tareas_analisis: Lista de TareaAnalisis a ejecutar.

        Returns:
            ResultadoEjecucionParalela con resultados y metricas.

        Raises:
            Exception: Si falla la ejecucion paralela completa.

        Example:
            >>> tareas = [
            ...     TareaAnalisis(nombre="retefuente", coroutine=async_tarea1()),
            ...     TareaAnalisis(nombre="iva", coroutine=async_tarea2())
            ... ]
            >>> resultado = await coordinador.ejecutar_tareas_paralelo(tareas)
            >>> print(resultado.total_tareas)
            2

        Notes:
            - asyncio.gather garantiza ejecucion paralela real
            - Semaforo limita concurrencia a max_workers
            - Si una tarea falla, las demas continuan ejecutandose
        """
        self.logger.info(f" Ejecutando {len(tareas_analisis)} analisis con maximo {self.max_workers} workers...")

        # Crear wrapper async para cada tarea con control de concurrencia
        async def ejecutar_con_control(tarea_analisis: TareaAnalisis, worker_id: int):
            """Wrapper que combina control de concurrencia con ejecucion."""
            return await self.controlador_concurrencia.ejecutar_con_semaforo(
                self.ejecutor_tarea.ejecutar_tarea(
                    nombre_impuesto=tarea_analisis.nombre,
                    tarea=tarea_analisis.coroutine,
                    worker_id=worker_id
                )
            )

        # Ejecutar todas las tareas en paralelo
        inicio_total = datetime.now()

        tareas_con_control = [
            ejecutar_con_control(tarea, i + 1)
            for i, tarea in enumerate(tareas_analisis)
        ]

        # Esperar todos los resultados (return_exceptions=False porque ya manejamos errores)
        resultados_ejecucion = await asyncio.gather(*tareas_con_control)

        # Procesar y agregar resultados
        resultado_final = self.procesador_resultados.agregar_resultados(resultados_ejecucion)

        self.logger.info(
            f" Ejecucion completada: {resultado_final.tareas_exitosas}/{resultado_final.total_tareas} exitosas "
            f"en {resultado_final.tiempo_total:.2f}s"
        )

        return resultado_final


# =================================
# FUNCION FACHADA (PUBLIC API)
# =================================


async def ejecutar_tareas_paralelo(
    tareas_analisis: List[TareaAnalisis],
    max_workers: int = 4
) -> ResultadoEjecucionParalela:
    """
    Funcion fachada para ejecutar tareas de analisis en paralelo.

    API publica del modulo. Simplifica invocacion desde main.py creando
    automaticamente el coordinador y delegando la operacion completa.

    Args:
        tareas_analisis: Lista de TareaAnalisis preparadas para ejecutar.
        max_workers: Numero maximo de workers simultaneos. Default: 4.

    Returns:
        ResultadoEjecucionParalela con:
            - resultados_analisis: Dict mapeando nombre_impuesto -> resultado
            - total_tareas: Numero de tareas ejecutadas
            - tareas_exitosas: Numero de tareas completadas exitosamente
            - tareas_fallidas: Numero de tareas que fallaron
            - tiempo_total: Tiempo total de ejecucion en segundos
            - impuestos_procesados: Lista de nombres de impuestos procesados

    Example:
        >>> from app.ejecucion_tareas_paralelo import ejecutar_tareas_paralelo
        >>> resultado = await ejecutar_tareas_paralelo(
        ...     tareas_analisis=tareas,
        ...     max_workers=4
        ... )
        >>> print(f"Completadas: {resultado.tareas_exitosas}/{resultado.total_tareas}")
        Completadas: 5/5
        >>> print(f"Tiempo total: {resultado.tiempo_total:.2f}s")
        Tiempo total: 12.34s

    Notes:
        - Crea instancia de CoordinadorEjecucionParalela internamente
        - Configuracion de max_workers optimizada para llamadas a Gemini
        - Compatible con TareaAnalisis de preparacion_tareas_analisis.py
        - Manejo robusto de errores: si una tarea falla, las demas continuan
    """
    coordinador = CoordinadorEjecucionParalela(
        max_workers=max_workers
    )

    return await coordinador.ejecutar_tareas_paralelo(tareas_analisis)
