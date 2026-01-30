"""
PREPARACION DE TAREAS DE ANALISIS PARALELO - MODULO DE NEGOCIO
================================================================

Modulo responsable de preparar tareas async para analisis paralelo de impuestos
con Google Gemini AI siguiendo principios SOLID.

ARQUITECTURA SOLID:
- SRP: 4 clases con responsabilidad unica cada una
- DIP: Todas las dependencias inyectadas por constructor
- OCP: Extensible para nuevos impuestos sin modificar codigo existente
- ISP: Interfaces claras y especificas
- Testabilidad: Diseño que facilita testing unitario

Autor: Miguel Angel Jaramillo Durango
"""

import logging
import traceback
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Coroutine, Tuple

from fastapi import UploadFile

# Importar clasificadores especializados
from Clasificador import ProcesadorGemini
from Clasificador.clasificador_retefuente import ClasificadorRetefuente
from Clasificador.clasificador_tp import ClasificadorTasaProdeporte
from Clasificador.clasificador_estampillas_g import ClasificadorEstampillasGenerales
from Clasificador.clasificador_iva import ClasificadorIva
from Clasificador.clasificador_obra_uni import ClasificadorObraUni
from Clasificador.clasificador_ica import ClasificadorICA
from Clasificador.clasificador_timbre import ClasificadorTimbre

# Importar Database Manager para DIP
from database import DatabaseManager

logger = logging.getLogger(__name__)


# =================================
# DATACLASSES
# =================================


@dataclass
class TareaAnalisis:
    """
    Representa una tarea de analisis para ejecutar en paralelo.

    Encapsula un analisis de impuesto como una tarea async que sera
    ejecutada en paralelo con otras tareas. Reemplaza el uso de tuplas
    (nombre, coroutine) por una estructura mas explicita y type-safe.

    Attributes:
        nombre: Identificador del impuesto a analizar.
                Ejemplos: "retefuente", "iva_reteiva", "ica", "timbre"
        coroutine: Coroutine async que ejecuta el analisis con Gemini.
                   Retorna Dict con resultado del analisis.

    Example:
        >>> async def analizar_iva():
        ...     return {"aplica": True, "valor": 19000}
        >>> tarea = TareaAnalisis(nombre="iva_reteiva", coroutine=analizar_iva())
        >>> print(tarea.nombre)
        iva_reteiva
        >>> resultado = await tarea.coroutine
        >>> print(resultado["valor"])
        19000

    Notes:
        - Type-safe: typing completo para prevenir errores
        - Mas legible que tuplas: atributos con nombres claros
        - Compatible con dataclass: facilita testing y serialization
    """

    nombre: str
    coroutine: Coroutine


@dataclass
class ResultadoPreparacionTareas:
    """
    Encapsula resultado completo de preparacion de tareas de analisis.

    Contiene todas las tareas async preparadas, cache de archivos, y
    metadatos del procesamiento. Soporta desempaquetado con __iter__()
    para compatibilidad con codigo legacy.

    Attributes:
        tareas_analisis: Lista de tareas async preparadas para ejecutar.
                        Cada tarea representa un analisis de impuesto.
        cache_archivos: Cache de Files API de Google Gemini.
                       Evita re-upload de archivos en workers paralelos.
                       Formato: {nombre_archivo: FileUploadResult}
        total_tareas: Numero total de tareas creadas (len de tareas_analisis).
        impuestos_preparados: Lista de nombres de impuestos preparados.
                             Ejemplo: ["retefuente", "iva_reteiva", "ica"]

    Methods:
        __iter__: Permite desempaquetado: tareas, cache = resultado

    Example:
        >>> resultado = ResultadoPreparacionTareas(
        ...     tareas_analisis=[tarea1, tarea2],
        ...     cache_archivos={"factura.pdf": file_ref},
        ...     total_tareas=2,
        ...     impuestos_preparados=["retefuente", "iva"]
        ... )
        >>> print(resultado.total_tareas)
        2
        >>> tareas, cache = resultado  # Desempaquetado
        >>> print(len(tareas))
        2

    Notes:
        - Soporta acceso por atributo: resultado.tareas_analisis
        - Soporta desempaquetado: tareas, cache = resultado
        - Compatible con dataclass para facilitar testing
        - Incluye metadatos utiles para logging y debugging
    """

    tareas_analisis: List[TareaAnalisis]
    cache_archivos: Dict[str, Any]
    total_tareas: int
    impuestos_preparados: List[str]

    def __iter__(self):
        """
        Permite desempaquetado del dataclass para compatibilidad con codigo legacy.

        Returns:
            Iterator con tupla (tareas_analisis, cache_archivos).

        Example:
            >>> resultado = await preparar_tareas_analisis(...)
            >>> tareas, cache = resultado  # Desempaquetado automatico
            >>> print(len(tareas))
            5
        """
        return iter((self.tareas_analisis, self.cache_archivos))


# =================================
# CLASE 1: INSTANCIADOR DE CLASIFICADORES
# =================================


class InstanciadorClasificadores:
    """
    Instancia clasificadores especializados segun configuracion de impuestos.

    SOLID:
    - SRP: Unica responsabilidad es instanciar clasificadores
    - DIP: Recibe dependencias por constructor (clasificador, db_manager)
    - OCP: Facil agregar nuevos clasificadores sin modificar clase

    Attributes:
        clasificador: Instancia de ProcesadorGemini para inyectar en clasificadores.
        estructura_contable: ID de estructura contable para clasificadores que lo requieren.
        db_manager: Gestor de base de datos para clasificadores que consultan DB.

    Example:
        >>> instanciador = InstanciadorClasificadores(
        ...     clasificador=procesador_gemini,
        ...     estructura_contable=123,
        ...     db_manager=db_manager
        ... )
        >>> clasificadores = instanciador.instanciar_clasificadores(
        ...     aplica_retencion=True,
        ...     aplica_estampilla=False,
        ...     aplica_obra_publica=False,
        ...     aplica_iva=True,
        ...     aplica_tasa_prodeporte=False
        ... )
        >>> print(clasificadores.keys())
        dict_keys(['retefuente', 'iva', 'estampillas_generales'])
    """

    def __init__(
        self,
        clasificador: ProcesadorGemini,
        estructura_contable: int,
        db_manager: DatabaseManager
    ):
        """
        Inicializa el instanciador con dependencias necesarias.

        Args:
            clasificador: Instancia de ProcesadorGemini para inyectar.
            estructura_contable: ID de estructura contable.
            db_manager: Gestor de base de datos.
        """
        self.clasificador = clasificador
        self.estructura_contable = estructura_contable
        self.db_manager = db_manager

    def instanciar_clasificadores(
        self,
        aplica_retencion: bool,
        aplica_estampilla: bool,
        aplica_obra_publica: bool,
        aplica_iva: bool,
        aplica_tasa_prodeporte: bool
    ) -> Dict[str, Any]:
        """
        Instancia clasificadores segun flags booleanos de impuestos.

        Args:
            aplica_retencion: Si retencio en la fuente aplica.
            aplica_estampilla: Si estampilla universidad aplica.
            aplica_obra_publica: Si contribucion obra publica aplica.
            aplica_iva: Si IVA/ReteIVA aplica.
            aplica_tasa_prodeporte: Si Tasa Prodeporte aplica.

        Returns:
            Dict con clasificadores instanciados:
            {
                "retefuente": ClasificadorRetefuente,
                "obra_uni": ClasificadorObraUni,
                "iva": ClasificadorIva,
                "tasa_prodeporte": ClasificadorTasaProdeporte,
                "estampillas_generales": ClasificadorEstampillasGenerales
            }

            Nota: estampillas_generales SIEMPRE se instancia (sin condicion).

        Example:
            >>> clasificadores = instanciador.instanciar_clasificadores(
            ...     aplica_retencion=True,
            ...     aplica_estampilla=False,
            ...     aplica_obra_publica=False,
            ...     aplica_iva=False,
            ...     aplica_tasa_prodeporte=False
            ... )
            >>> assert "retefuente" in clasificadores
            >>> assert "estampillas_generales" in clasificadores  # SIEMPRE presente
            >>> assert "iva" not in clasificadores
        """
        clasificadores = {}

        # Retefuente (condicional)
        if aplica_retencion:
            clasificadores["retefuente"] = ClasificadorRetefuente(
                procesador_gemini=self.clasificador,
                estructura_contable=self.estructura_contable,
                db_manager=self.db_manager
            )

        # Estampilla Universidad + Obra Publica (condicional, analisis integrado)
        if aplica_estampilla or aplica_obra_publica:
            clasificadores["obra_uni"] = ClasificadorObraUni(
                procesador_gemini=self.clasificador
            )

        # IVA/ReteIVA (condicional)
        if aplica_iva:
            clasificadores["iva"] = ClasificadorIva(
                procesador_gemini=self.clasificador
            )

        # Tasa Prodeporte (condicional)
        if aplica_tasa_prodeporte:
            clasificadores["tasa_prodeporte"] = ClasificadorTasaProdeporte(
                procesador_gemini=self.clasificador
            )

        # Estampillas Generales (SIEMPRE - sin condicion)
        # Identifica 6 estampillas generales: Procultura, Bienestar, etc.
        clasificadores["estampillas_generales"] = ClasificadorEstampillasGenerales(
            procesador_gemini=self.clasificador
        )

        return clasificadores


# =================================
# CLASE 2: PREPARADOR DE CACHE DE ARCHIVOS
# =================================


class PreparadorCacheArchivos:
    """
    Prepara cache de archivos de Google Gemini Files API para workers paralelos.

    SOLID:
    - SRP: Unica responsabilidad es preparar cache de archivos
    - DIP: Recibe ProcesadorGemini por constructor

    El cache evita re-upload de archivos cuando se ejecutan multiples workers
    en paralelo. Cada worker reutiliza las referencias de Files API.

    Attributes:
        clasificador: Instancia de ProcesadorGemini con metodo de preparacion.

    Example:
        >>> preparador = PreparadorCacheArchivos(clasificador=procesador_gemini)
        >>> cache = await preparador.preparar_cache(archivos_directos)
        >>> print(cache.keys())
        dict_keys(['factura.pdf', 'rut.pdf', 'contrato.pdf'])
    """

    def __init__(self, clasificador: ProcesadorGemini):
        """
        Inicializa el preparador con ProcesadorGemini.

        Args:
            clasificador: Instancia de ProcesadorGemini para preparar cache.
        """
        self.clasificador = clasificador

    async def preparar_cache(
        self,
        archivos_directos: List[UploadFile]
    ) -> Dict[str, Any]:
        """
        Prepara cache de Files API para evitar re-upload en workers paralelos.

        Args:
            archivos_directos: Lista de archivos UploadFile originales.

        Returns:
            Dict con cache de FileUploadResult por nombre de archivo.
            Formato: {nombre_archivo: FileUploadResult}

        Example:
            >>> archivos = [factura_upload, rut_upload]
            >>> cache = await preparador.preparar_cache(archivos)
            >>> print(len(cache))
            2

        Notes:
            - Llama a clasificador.preparar_archivos_para_workers_paralelos()
            - El cache se pasa a cada tarea async para reutilizar referencias
            - Evita timeout por re-upload de archivos grandes
        """
        logger.info(" Preparando cache para workers paralelos")
        cache_archivos = await self.clasificador.preparar_archivos_para_workers_paralelos(
            archivos_directos
        )
        logger.info(f"Cache preparado: {len(cache_archivos)} archivos")
        return cache_archivos


# =================================
# CLASE 3: PREPARADOR DE TAREAS DE ANALISIS
# =================================


class PreparadorTareasAnalisis:
    """
    Crea tareas asincronas para analisis paralelo de impuestos con Gemini.

    SOLID:
    - SRP: Unica responsabilidad es crear tareas async
    - OCP: Facil agregar nuevas tareas sin modificar existentes
    - DIP: Recibe clasificadores y dependencias por constructor

    Attributes:
        clasificadores: Dict con clasificadores instanciados por InstanciadorClasificadores.
        clasificador_base: ProcesadorGemini base para metodos generales (consorcio).
        db_manager: DatabaseManager para clasificadores que requieren DB (ICA).

    Example:
        >>> preparador = PreparadorTareasAnalisis(
        ...     clasificadores=clasificadores_dict,
        ...     clasificador_base=procesador_gemini,
        ...     db_manager=db_manager
        ... )
        >>> tareas = await preparador.preparar_tareas(
        ...     documentos_clasificados=documentos,
        ...     cache_archivos=cache,
        ...     aplica_retencion=True,
        ...     # ... mas parametros
        ... )
        >>> print(len(tareas))
        5
    """

    def __init__(
        self,
        clasificadores: Dict[str, Any],
        clasificador_base: ProcesadorGemini,
        db_manager: DatabaseManager
    ):
        """
        Inicializa el preparador con clasificadores y dependencias.

        Args:
            clasificadores: Dict con clasificadores ya instanciados.
            clasificador_base: ProcesadorGemini para metodos generales.
            db_manager: DatabaseManager para clasificadores especiales.
        """
        self.clasificadores = clasificadores
        self.clasificador_base = clasificador_base
        self.db_manager = db_manager

    async def preparar_tareas(
        self,
        documentos_clasificados: Dict[str, Dict],
        cache_archivos: Dict[str, Any],
        aplica_retencion: bool,
        aplica_estampilla: bool,
        aplica_obra_publica: bool,
        aplica_iva: bool,
        aplica_ica: bool,
        aplica_timbre: bool,
        aplica_tasa_prodeporte: bool,
        es_consorcio: bool,
        es_recurso_extranjero: bool,
        es_facturacion_extranjera: bool,
        proveedor: str,
        nit_administrativo: str,
        estructura_contable: int,
        observaciones_tp: Optional[str]
    ) -> List[TareaAnalisis]:
        """
        Crea todas las tareas async segun configuracion de impuestos.

        Args:
            documentos_clasificados: Dict con documentos clasificados y textos.
            cache_archivos: Cache de Files API para workers paralelos.
            aplica_retencion: Si retencion en la fuente aplica.
            aplica_estampilla: Si estampilla universidad aplica.
            aplica_obra_publica: Si contribucion obra publica aplica.
            aplica_iva: Si IVA/ReteIVA aplica.
            aplica_ica: Si retencion ICA aplica.
            aplica_timbre: Si impuesto al timbre aplica.
            aplica_tasa_prodeporte: Si Tasa Prodeporte aplica.
            es_consorcio: Si la factura es de consorcio (afecta retefuente).
            es_recurso_extranjero: Si es recurso de fuente extranjera (skip retefuente e IVA).
            es_facturacion_extranjera: Si es facturacion extranjera vs nacional.
            proveedor: Nombre del proveedor que emite factura.
            nit_administrativo: NIT de la entidad administrativa.
            estructura_contable: ID de estructura contable.
            observaciones_tp: Observaciones de PGD para Tasa Prodeporte y Timbre.

        Returns:
            Lista de TareaAnalisis listas para ejecutar en paralelo.
            Minimo 1 tarea (estampillas_generales SIEMPRE), maximo 7 tareas.

        Example:
            >>> tareas = await preparador.preparar_tareas(
            ...     documentos_clasificados=documentos,
            ...     cache_archivos=cache,
            ...     aplica_retencion=True,
            ...     aplica_estampilla=False,
            ...     aplica_obra_publica=False,
            ...     aplica_iva=True,
            ...     aplica_ica=False,
            ...     aplica_timbre=False,
            ...     aplica_tasa_prodeporte=False,
            ...     es_consorcio=False,
            ...     es_recurso_extranjero=False,
            ...     es_facturacion_extranjera=False,
            ...     proveedor="Test SAS",
            ...     nit_administrativo="900123456",
            ...     estructura_contable=123,
            ...     observaciones_tp=""
            ... )
            >>> print(tareas[0].nombre)
            retefuente
            >>> print(tareas[-1].nombre)
            estampillas_generales  # Siempre presente

        Notes:
            - Las tareas se crean pero NO se ejecutan aqui
            - La ejecucion ocurre en main.py con asyncio.gather()
            - Cada tarea es un coroutine async listo para ejecutar
        """
        tareas = []

        # Tarea 1: Retefuente
        tarea = self._crear_tarea_retefuente(
            documentos_clasificados,
            cache_archivos,
            aplica_retencion,
            es_recurso_extranjero,
            es_consorcio,
            es_facturacion_extranjera,
            proveedor,
            nit_administrativo
        )
        if tarea:
            tareas.append(tarea)

        # Tarea 2: Impuestos Especiales (Estampilla + Obra Publica integrados)
        tarea = self._crear_tarea_impuestos_especiales(
            documentos_clasificados,
            cache_archivos,
            aplica_estampilla,
            aplica_obra_publica
        )
        if tarea:
            tareas.append(tarea)

        # Tarea 3: IVA/ReteIVA
        tarea = self._crear_tarea_iva(
            documentos_clasificados,
            cache_archivos,
            aplica_iva,
            es_recurso_extranjero,
            nit_administrativo
        )
        if tarea:
            tareas.append(tarea)

        # Tarea 4: Estampillas Generales (SIEMPRE se crea)
        tarea = self._crear_tarea_estampillas_generales(
            documentos_clasificados,
            cache_archivos
        )
        tareas.append(tarea)

        # Tarea 5: Tasa Prodeporte
        tarea = self._crear_tarea_tasa_prodeporte(
            documentos_clasificados,
            cache_archivos,
            aplica_tasa_prodeporte,
            observaciones_tp,
            nit_administrativo
        )
        if tarea:
            tareas.append(tarea)

        # Tarea 6: ICA (con wrapper async)
        tarea = await self._crear_tarea_ica(
            documentos_clasificados,
            cache_archivos,
            aplica_ica,
            nit_administrativo,
            estructura_contable
        )
        if tarea:
            tareas.append(tarea)

        # Tarea 7: Timbre (con wrapper async)
        tarea = await self._crear_tarea_timbre(
            aplica_timbre,
            observaciones_tp,
            nit_administrativo
        )
        if tarea:
            tareas.append(tarea)

        logger.info(f" Tareas preparadas: {len(tareas)} analisis")
        return tareas

    def _crear_tarea_retefuente(
        self,
        documentos_clasificados: Dict[str, Dict],
        cache_archivos: Dict[str, Any],
        aplica_retencion: bool,
        es_recurso_extranjero: bool,
        es_consorcio: bool,
        es_facturacion_extranjera: bool,
        proveedor: str,
        nit_administrativo: str
    ) -> Optional[TareaAnalisis]:
        """
        Crea tarea de analisis de retencion en la fuente.

        Args:
            documentos_clasificados: Documentos con textos extraidos.
            cache_archivos: Cache de Files API.
            aplica_retencion: Si retencion aplica.
            es_recurso_extranjero: Si es recurso extranjero (skip).
            es_consorcio: Si es consorcio (usa metodo diferente).
            es_facturacion_extranjera: Si es facturacion extranjera.
            proveedor: Nombre del proveedor.
            nit_administrativo: NIT administrativo.

        Returns:
            TareaAnalisis si aplica retencion, None si no aplica o es recurso extranjero.

        Notes:
            - Si es consorcio: usa clasificador_base.analizar_consorcio()
            - Si no es consorcio: usa clasificadores["retefuente"].analizar_factura()
            - Si es recurso extranjero: retorna None (se maneja en liquidacion)
        """
        if aplica_retencion and not es_recurso_extranjero:
            if es_consorcio:
                coroutine = self.clasificador_base.analizar_consorcio(
                    documentos_clasificados,
                    es_facturacion_extranjera,
                    None,
                    cache_archivos,
                    proveedor=proveedor
                )
            else:
                coroutine = self.clasificadores["retefuente"].analizar_factura(
                    documentos_clasificados,
                    es_facturacion_extranjera,
                    None,
                    cache_archivos,
                    proveedor=proveedor
                )
            return TareaAnalisis(nombre="retefuente", coroutine=coroutine)

        elif aplica_retencion and es_recurso_extranjero:
            logger.info(" Retefuente: No se procesara - Recurso extranjero detectado")

        return None

    def _crear_tarea_impuestos_especiales(
        self,
        documentos_clasificados: Dict[str, Dict],
        cache_archivos: Dict[str, Any],
        aplica_estampilla: bool,
        aplica_obra_publica: bool
    ) -> Optional[TareaAnalisis]:
        """
        Crea tarea de analisis de estampilla universidad + obra publica.

        Args:
            documentos_clasificados: Documentos con textos extraidos.
            cache_archivos: Cache de Files API.
            aplica_estampilla: Si estampilla universidad aplica.
            aplica_obra_publica: Si contribucion obra publica aplica.

        Returns:
            TareaAnalisis si alguno de los dos aplica, None si ninguno aplica.

        Notes:
            - Analisis integrado: ambos impuestos en UNA llamada a Gemini
            - El liquidador luego separa los resultados en dos estructuras
        """
        if aplica_estampilla or aplica_obra_publica:
            coroutine = self.clasificadores["obra_uni"].analizar_estampilla(
                documentos_clasificados,
                None,
                cache_archivos
            )
            return TareaAnalisis(nombre="impuestos_especiales", coroutine=coroutine)
        return None

    def _crear_tarea_iva(
        self,
        documentos_clasificados: Dict[str, Dict],
        cache_archivos: Dict[str, Any],
        aplica_iva: bool,
        es_recurso_extranjero: bool,
        nit_administrativo: str
    ) -> Optional[TareaAnalisis]:
        """
        Crea tarea de analisis de IVA/ReteIVA.

        Args:
            documentos_clasificados: Documentos con textos extraidos.
            cache_archivos: Cache de Files API.
            aplica_iva: Si IVA/ReteIVA aplica.
            es_recurso_extranjero: Si es recurso extranjero (skip).
            nit_administrativo: NIT administrativo.

        Returns:
            TareaAnalisis si aplica IVA, None si no aplica o es recurso extranjero.

        Notes:
            - Si es recurso extranjero: retorna None (se maneja en liquidacion)
        """
        if aplica_iva and not es_recurso_extranjero:
            coroutine = self.clasificadores["iva"].analizar_iva(
                documentos_clasificados,
                None,
                cache_archivos
            )
            return TareaAnalisis(nombre="iva_reteiva", coroutine=coroutine)

        elif aplica_iva and es_recurso_extranjero:
            logger.info(" IVA/ReteIVA: No se procesara - Recurso extranjero detectado")

        return None

    def _crear_tarea_estampillas_generales(
        self,
        documentos_clasificados: Dict[str, Dict],
        cache_archivos: Dict[str, Any]
    ) -> TareaAnalisis:
        """
        Crea tarea de analisis de estampillas generales (SIEMPRE se ejecuta).

        Args:
            documentos_clasificados: Documentos con textos extraidos.
            cache_archivos: Cache de Files API.

        Returns:
            TareaAnalisis (nunca None - siempre se crea).

        Notes:
            - NO tiene condicion: se ejecuta para TODOS los NITs
            - Identifica 6 estampillas generales: Procultura, Bienestar, etc.
        """
        coroutine = self.clasificadores["estampillas_generales"].analizar_estampillas_generales(
            documentos_clasificados,
            None,
            cache_archivos
        )
        return TareaAnalisis(nombre="estampillas_generales", coroutine=coroutine)

    def _crear_tarea_tasa_prodeporte(
        self,
        documentos_clasificados: Dict[str, Dict],
        cache_archivos: Dict[str, Any],
        aplica_tasa_prodeporte: bool,
        observaciones_tp: Optional[str],
        nit_administrativo: str
    ) -> Optional[TareaAnalisis]:
        """
        Crea tarea de analisis de Tasa Prodeporte.

        Args:
            documentos_clasificados: Documentos con textos extraidos.
            cache_archivos: Cache de Files API.
            aplica_tasa_prodeporte: Si Tasa Prodeporte aplica.
            observaciones_tp: Observaciones de PGD (campo especifico de Tasa Prodeporte).
            nit_administrativo: NIT administrativo.

        Returns:
            TareaAnalisis si aplica, None si no aplica.

        Notes:
            - Solo aplica para PATRIMONIO AUTONOMO FONTUR (NIT 900649119)
            - Requiere observaciones_tp para analisis
        """
        if aplica_tasa_prodeporte:
            coroutine = self.clasificadores["tasa_prodeporte"].analizar_tasa_prodeporte(
                documentos_clasificados,
                None,
                cache_archivos,
                observaciones_tp
            )
            logger.info(f"Tasa Prodeporte: Analisis activado para NIT {nit_administrativo}")
            return TareaAnalisis(nombre="tasa_prodeporte", coroutine=coroutine)
        return None

    async def _crear_tarea_ica(
        self,
        documentos_clasificados: Dict[str, Dict],
        cache_archivos: Dict[str, Any],
        aplica_ica: bool,
        nit_administrativo: str,
        estructura_contable: int
    ) -> Optional[TareaAnalisis]:
        """
        Crea tarea de analisis de ICA con wrapper async.

        Args:
            documentos_clasificados: Documentos con textos extraidos.
            cache_archivos: Cache de Files API.
            aplica_ica: Si ICA aplica.
            nit_administrativo: NIT administrativo.
            estructura_contable: ID de estructura contable.

        Returns:
            TareaAnalisis si aplica, None si no aplica.

        Notes:
            - Usa wrapper async (_crear_wrapper_ica) por instanciacion interna
            - Manejo de errores integrado en el wrapper
        """
        if aplica_ica:
            coroutine = self._crear_wrapper_ica(
                documentos_clasificados,
                cache_archivos,
                nit_administrativo,
                estructura_contable
            )
            logger.info(f"ICA: Analisis activado para NIT {nit_administrativo}")
            return TareaAnalisis(nombre="ica", coroutine=coroutine)
        return None

    async def _crear_tarea_timbre(
        self,
        aplica_timbre: bool,
        observaciones_tp: Optional[str],
        nit_administrativo: str
    ) -> Optional[TareaAnalisis]:
        """
        Crea tarea de analisis de Timbre con wrapper async.

        Args:
            aplica_timbre: Si impuesto al timbre aplica.
            observaciones_tp: Observaciones de PGD para analizar.
            nit_administrativo: NIT administrativo.

        Returns:
            TareaAnalisis si aplica, None si no aplica.

        Notes:
            - Usa wrapper async (_crear_wrapper_timbre) por instanciacion interna
            - Primera de DOS llamadas a Gemini (segunda en liquidacion)
            - Analiza observaciones de PGD para determinar si aplica
        """
        if aplica_timbre:
            coroutine = self._crear_wrapper_timbre(observaciones_tp)
            logger.info(f"Timbre: Analisis activado para NIT {nit_administrativo}")
            return TareaAnalisis(nombre="timbre", coroutine=coroutine)
        return None

    async def _crear_wrapper_ica(
        self,
        documentos_clasificados: Dict[str, Dict],
        cache_archivos: Dict[str, Any],
        nit_administrativo: str,
        estructura_contable: int
    ):
        """
        Wrapper async para ICA con manejo de errores integrado.

        ICA requiere instanciacion interna del ClasificadorICA (no se instancia
        en InstanciadorClasificadores) y manejo de excepciones especifico.

        Args:
            documentos_clasificados: Documentos con textos extraidos.
            cache_archivos: Cache de Files API.
            nit_administrativo: NIT administrativo para consultas DB.
            estructura_contable: ID de estructura contable.

        Returns:
            Dict con resultado del analisis ICA o estructura de error.

        Example:
            >>> resultado = await wrapper_ica(...)
            >>> if resultado["aplica"]:
            ...     print(f"ICA: ${resultado['valor_total_ica']}")
        """
        try:
            clasificador_ica = ClasificadorICA(
                database_manager=self.db_manager,
                procesador_gemini=self.clasificador_base
            )
            return await clasificador_ica.analizar_ica(
                nit_administrativo=nit_administrativo,
                textos_documentos=documentos_clasificados,
                estructura_contable=estructura_contable,
                cache_archivos=cache_archivos
            )
        except Exception as e:
            logger.error(f"Error en analisis ICA: {e}")
            logger.error(traceback.format_exc())
            return {
                "aplica": False,
                "estado": "preliquidacion_sin_finalizar",
                "observaciones": [f"Error en analisis ICA: {str(e)}"]
            }

    async def _crear_wrapper_timbre(self, observaciones_tp: Optional[str]):
        """
        Wrapper async para Timbre con manejo de errores integrado.

        Timbre requiere instanciacion interna del ClasificadorTimbre (no se instancia
        en InstanciadorClasificadores) y manejo de excepciones especifico.

        Args:
            observaciones_tp: Observaciones de PGD para analizar.

        Returns:
            Dict con resultado del analisis de observaciones o estructura de error.

        Notes:
            - Primera de DOS llamadas a Gemini para Timbre
            - Segunda llamada (extraer datos contrato) ocurre en liquidacion
        """
        try:
            clasificador_timbre = ClasificadorTimbre(
                procesador_gemini=self.clasificador_base
            )
            return await clasificador_timbre.analizar_observaciones_timbre(
                observaciones=observaciones_tp or ""
            )
        except Exception as e:
            logger.error(f"Error en analisis Timbre (observaciones): {e}")
            logger.error(traceback.format_exc())
            return {
                "aplica_timbre": False,
                "base_gravable_obs": 0.0,
                "observaciones_analisis": f"Error en analisis Timbre: {str(e)}"
            }


# =================================
# CLASE 4: COORDINADOR DE PREPARACION DE TAREAS (FACHADA)
# =================================


class CoordinadorPreparacionTareas:
    """
    Coordina instanciacion, cache y preparacion de tareas de analisis.

    SOLID:
    - Facade Pattern: Simplifica uso de las 3 clases especializadas
    - SRP: Responsabilidad unica de coordinar preparacion completa
    - DIP: Recibe dependencias por constructor

    Coordina el flujo completo de preparacion:
    1. Instanciar clasificadores (InstanciadorClasificadores)
    2. Preparar cache de archivos (PreparadorCacheArchivos)
    3. Crear tareas async (PreparadorTareasAnalisis)
    4. Retornar resultado estructurado (ResultadoPreparacionTareas)

    Attributes:
        clasificador: ProcesadorGemini base para inyectar.
        estructura_contable: ID de estructura contable.
        db_manager: DatabaseManager para clasificadores que requieren DB.
        instanciador: Instancia de InstanciadorClasificadores.
        preparador_cache: Instancia de PreparadorCacheArchivos.

    Example:
        >>> coordinador = CoordinadorPreparacionTareas(
        ...     clasificador=procesador_gemini,
        ...     estructura_contable=123,
        ...     db_manager=db_manager
        ... )
        >>> resultado = await coordinador.preparar_tareas_analisis(
        ...     documentos_clasificados=documentos,
        ...     archivos_directos=archivos,
        ...     aplica_retencion=True,
        ...     # ... mas parametros
        ... )
        >>> print(resultado.total_tareas)
        5
    """

    def __init__(
        self,
        clasificador: ProcesadorGemini,
        estructura_contable: int,
        db_manager: DatabaseManager
    ):
        """
        Inicializa el coordinador con dependencias necesarias.

        Args:
            clasificador: ProcesadorGemini para inyectar en clasificadores.
            estructura_contable: ID de estructura contable.
            db_manager: DatabaseManager para clasificadores que requieren DB.
        """
        self.clasificador = clasificador
        self.estructura_contable = estructura_contable
        self.db_manager = db_manager

        # Instanciar componentes especializados (DIP)
        self.instanciador = InstanciadorClasificadores(
            clasificador, estructura_contable, db_manager
        )
        self.preparador_cache = PreparadorCacheArchivos(clasificador)

    async def preparar_tareas_analisis(
        self,
        documentos_clasificados: Dict[str, Dict],
        archivos_directos: List[UploadFile],
        aplica_retencion: bool,
        aplica_estampilla: bool,
        aplica_obra_publica: bool,
        aplica_iva: bool,
        aplica_ica: bool,
        aplica_timbre: bool,
        aplica_tasa_prodeporte: bool,
        es_consorcio: bool,
        es_recurso_extranjero: bool,
        es_facturacion_extranjera: bool,
        proveedor: str,
        nit_administrativo: str,
        observaciones_tp: Optional[str],
        impuestos_a_procesar: List[str]
    ) -> ResultadoPreparacionTareas:
        """
        Prepara todas las tareas de analisis paralelo.

        Coordina el flujo completo:
        1. Instanciacion de clasificadores segun flags
        2. Preparacion de cache de archivos
        3. Creacion de tareas async

        Args:
            documentos_clasificados: Documentos con textos extraidos.
            archivos_directos: Archivos UploadFile originales.
            aplica_retencion: Si retencion en la fuente aplica.
            aplica_estampilla: Si estampilla universidad aplica.
            aplica_obra_publica: Si contribucion obra publica aplica.
            aplica_iva: Si IVA/ReteIVA aplica.
            aplica_ica: Si retencion ICA aplica.
            aplica_timbre: Si impuesto al timbre aplica.
            aplica_tasa_prodeporte: Si Tasa Prodeporte aplica.
            es_consorcio: Si es consorcio (afecta retefuente).
            es_recurso_extranjero: Si es recurso extranjero (skip retefuente e IVA).
            es_facturacion_extranjera: Si es facturacion extranjera.
            proveedor: Nombre del proveedor.
            nit_administrativo: NIT administrativo.
            observaciones_tp: Observaciones de PGD.
            impuestos_a_procesar: Lista de nombres de impuestos a procesar.

        Returns:
            ResultadoPreparacionTareas con tareas y cache listos.

        Example:
            >>> resultado = await coordinador.preparar_tareas_analisis(
            ...     documentos_clasificados=documentos,
            ...     archivos_directos=archivos,
            ...     aplica_retencion=True,
            ...     aplica_estampilla=False,
            ...     aplica_obra_publica=False,
            ...     aplica_iva=True,
            ...     aplica_ica=False,
            ...     aplica_timbre=False,
            ...     aplica_tasa_prodeporte=False,
            ...     es_consorcio=False,
            ...     es_recurso_extranjero=False,
            ...     es_facturacion_extranjera=False,
            ...     proveedor="Test SAS",
            ...     nit_administrativo="900123456",
            ...     observaciones_tp="",
            ...     impuestos_a_procesar=["retefuente", "iva"]
            ... )
            >>> print(resultado.total_tareas)
            3  # retefuente + iva + estampillas_generales (SIEMPRE)
        """
        logger.info(f" Iniciando preparacion de tareas: {' + '.join(impuestos_a_procesar)}")

        # PASO 1: Instanciar clasificadores segun flags
        clasificadores = self.instanciador.instanciar_clasificadores(
            aplica_retencion=aplica_retencion,
            aplica_estampilla=aplica_estampilla,
            aplica_obra_publica=aplica_obra_publica,
            aplica_iva=aplica_iva,
            aplica_tasa_prodeporte=aplica_tasa_prodeporte
        )

        # PASO 2: Preparar cache de archivos
        cache_archivos = await self.preparador_cache.preparar_cache(archivos_directos)

        # PASO 3: Crear tareas async
        preparador_tareas = PreparadorTareasAnalisis(
            clasificadores=clasificadores,
            clasificador_base=self.clasificador,
            db_manager=self.db_manager
        )

        tareas = await preparador_tareas.preparar_tareas(
            documentos_clasificados=documentos_clasificados,
            cache_archivos=cache_archivos,
            aplica_retencion=aplica_retencion,
            aplica_estampilla=aplica_estampilla,
            aplica_obra_publica=aplica_obra_publica,
            aplica_iva=aplica_iva,
            aplica_ica=aplica_ica,
            aplica_timbre=aplica_timbre,
            aplica_tasa_prodeporte=aplica_tasa_prodeporte,
            es_consorcio=es_consorcio,
            es_recurso_extranjero=es_recurso_extranjero,
            es_facturacion_extranjera=es_facturacion_extranjera,
            proveedor=proveedor,
            nit_administrativo=nit_administrativo,
            estructura_contable=self.estructura_contable,
            observaciones_tp=observaciones_tp
        )

        # PASO 4: Retornar resultado estructurado
        resultado = ResultadoPreparacionTareas(
            tareas_analisis=tareas,
            cache_archivos=cache_archivos,
            total_tareas=len(tareas),
            impuestos_preparados=[tarea.nombre for tarea in tareas]
        )

        logger.info(f" Preparacion completada: {resultado.total_tareas} tareas listas")
        return resultado


# =================================
# FUNCION FACHADA (PUBLIC API)
# =================================


async def preparar_tareas_analisis(
    clasificador: ProcesadorGemini,
    estructura_contable: int,
    db_manager: DatabaseManager,
    documentos_clasificados: Dict[str, Dict],
    archivos_directos: List[UploadFile],
    aplica_retencion: bool,
    aplica_estampilla: bool,
    aplica_obra_publica: bool,
    aplica_iva: bool,
    aplica_ica: bool,
    aplica_timbre: bool,
    aplica_tasa_prodeporte: bool,
    es_consorcio: bool,
    es_recurso_extranjero: bool,
    es_facturacion_extranjera: bool,
    proveedor: str,
    nit_administrativo: str,
    observaciones_tp: Optional[str],
    impuestos_a_procesar: List[str]
) -> ResultadoPreparacionTareas:
    """
    Funcion fachada para preparar tareas de analisis paralelo.

    API publica del modulo. Simplifica invocacion desde main.py creando
    automaticamente el coordinador y delegando la operacion completa.

    Args:
        clasificador: ProcesadorGemini para inyectar en clasificadores.
        estructura_contable: ID de estructura contable.
        db_manager: DatabaseManager para clasificadores que requieren DB.
        documentos_clasificados: Documentos con textos extraidos.
        archivos_directos: Archivos UploadFile originales.
        aplica_retencion: Si retencion en la fuente aplica.
        aplica_estampilla: Si estampilla universidad aplica.
        aplica_obra_publica: Si contribucion obra publica aplica.
        aplica_iva: Si IVA/ReteIVA aplica.
        aplica_ica: Si retencion ICA aplica.
        aplica_timbre: Si impuesto al timbre aplica.
        aplica_tasa_prodeporte: Si Tasa Prodeporte aplica.
        es_consorcio: Si es consorcio (afecta retefuente).
        es_recurso_extranjero: Si es recurso extranjero (skip retefuente e IVA).
        es_facturacion_extranjera: Si es facturacion extranjera.
        proveedor: Nombre del proveedor.
        nit_administrativo: NIT administrativo.
        observaciones_tp: Observaciones de PGD.
        impuestos_a_procesar: Lista de nombres de impuestos a procesar.

    Returns:
        ResultadoPreparacionTareas con:
            - tareas_analisis: Lista de TareaAnalisis listas para ejecutar
            - cache_archivos: Cache de Files API
            - total_tareas: Numero de tareas creadas
            - impuestos_preparados: Lista de nombres de impuestos

    Example:
        >>> from app.preparacion_tareas_analisis import preparar_tareas_analisis
        >>> resultado = await preparar_tareas_analisis(
        ...     clasificador=procesador_gemini,
        ...     estructura_contable=123,
        ...     db_manager=db_manager,
        ...     documentos_clasificados=documentos,
        ...     archivos_directos=archivos,
        ...     aplica_retencion=True,
        ...     aplica_estampilla=False,
        ...     aplica_obra_publica=False,
        ...     aplica_iva=True,
        ...     aplica_ica=False,
        ...     aplica_timbre=False,
        ...     aplica_tasa_prodeporte=False,
        ...     es_consorcio=False,
        ...     es_recurso_extranjero=False,
        ...     es_facturacion_extranjera=False,
        ...     proveedor="Test SAS",
        ...     nit_administrativo="900123456",
        ...     observaciones_tp="",
        ...     impuestos_a_procesar=["retefuente", "iva"]
        ... )
        >>> print(resultado.total_tareas)
        3
        >>> tareas, cache = resultado  # Desempaquetado automatico
        >>> print(len(tareas))
        3

    Notes:
        - Crea instancia de CoordinadorPreparacionTareas internamente
        - Resultado soporta desempaquetado: tareas, cache = resultado
        - Compatible con codigo legacy de main.py
    """
    coordinador = CoordinadorPreparacionTareas(
        clasificador=clasificador,
        estructura_contable=estructura_contable,
        db_manager=db_manager
    )

    return await coordinador.preparar_tareas_analisis(
        documentos_clasificados=documentos_clasificados,
        archivos_directos=archivos_directos,
        aplica_retencion=aplica_retencion,
        aplica_estampilla=aplica_estampilla,
        aplica_obra_publica=aplica_obra_publica,
        aplica_iva=aplica_iva,
        aplica_ica=aplica_ica,
        aplica_timbre=aplica_timbre,
        aplica_tasa_prodeporte=aplica_tasa_prodeporte,
        es_consorcio=es_consorcio,
        es_recurso_extranjero=es_recurso_extranjero,
        es_facturacion_extranjera=es_facturacion_extranjera,
        proveedor=proveedor,
        nit_administrativo=nit_administrativo,
        observaciones_tp=observaciones_tp,
        impuestos_a_procesar=impuestos_a_procesar
    )
