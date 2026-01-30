"""
Módulo de validación de negocios.
Proporciona clases para validar y configurar impuestos aplicables por negocio.
"""
import logging
from dataclasses import dataclass, astuple
from typing import Dict, Any, List, Optional
from fastapi.responses import JSONResponse
from fastapi import HTTPException

from utils.mockups import crear_respuesta_negocio_no_parametrizado
from config import (
    obtener_nits_disponibles,
    validar_nit_administrativo,
    nit_aplica_iva_reteiva,
    nit_aplica_ICA,
    nit_aplica_tasa_prodeporte,
    nit_aplica_timbre,
    detectar_impuestos_aplicables_por_codigo,
)

logger = logging.getLogger(__name__)


@dataclass
class ResultadoValidacion:
    """
    Resultado de la validación de negocio e impuestos aplicables.
    Puede desempaquetarse como tupla para compatibilidad con código existente.
    """
    impuestos_a_procesar: List[str]
    aplica_retencion: bool
    aplica_estampilla: bool
    aplica_obra_publica: bool
    aplica_iva: bool
    aplica_ica: bool
    aplica_timbre: bool
    aplica_tasa_prodeporte: bool
    nombre_negocio: str
    nit_administrativo: str
    deteccion_impuestos: Dict[str, Any]
    nombre_entidad: str

    def __iter__(self):
        """Permite desempaquetar como tupla: a, b, c = resultado"""
        return iter(astuple(self))


class ValidadorNegocio:
    """
    Valida negocios y determina impuestos aplicables.

    Responsabilidades:
    - Validar que el negocio esté parametrizado en BD
    - Validar NIT administrativo
    - Detectar impuestos aplicables según configuración
    - Construir lista de impuestos a procesar

    Example:
        >>> validador = ValidadorNegocio(business_service)
        >>> resultado = validador.validar(resultado_negocio, codigo_negocio)
        >>> if isinstance(resultado, JSONResponse):
        ...     return resultado  # Error
        >>> # Usar resultado exitoso
        >>> print(resultado.nit_administrativo)
    """

    def __init__(self, business_service: Any):
        """
        Inicializa el validador con el servicio de negocio.

        Args:
            business_service: Servicio para acceder a datos de negocio
        """
        self.business_service = business_service

    def validar(
        self,
        resultado_negocio: Dict[str, Any],
        codigo_negocio: Any
    ) -> ResultadoValidacion | JSONResponse:
        """
        Valida negocio y determina impuestos aplicables.

        Args:
            resultado_negocio: Resultado de obtener_datos_negocio()
            codigo_negocio: Código del negocio

        Returns:
            JSONResponse si hay error de validación
            ResultadoValidacion si validación exitosa

        Raises:
            HTTPException: Si NIT administrativo no es válido
        """
        # Extraer datos del negocio
        datos_negocio = self._extraer_datos_negocio(resultado_negocio)

        # Validar que el negocio esté parametrizado
        error_parametrizacion = self._validar_parametrizacion(datos_negocio, codigo_negocio)
        if error_parametrizacion:
            return error_parametrizacion

        # Extraer NIT y nombre
        nit_administrativo = str(datos_negocio['nit'])
        nombre_negocio = datos_negocio.get('negocio', 'Desconocido')

        logger.info(f" NIT administrativo obtenido de DB: {nit_administrativo}")

        # Validar NIT administrativo
        nombre_entidad, impuestos_aplicables = self._validar_nit_administrativo(nit_administrativo)

        # Detectar impuestos aplicables
        deteccion_impuestos = self._detectar_impuestos(
            codigo_negocio,
            nombre_negocio,
            nit_administrativo
        )

        # Determinar flags de impuestos
        flags_impuestos = self._determinar_flags_impuestos(
            nit_administrativo,
            impuestos_aplicables,
            deteccion_impuestos
        )

        # Construir lista de impuestos a procesar
        impuestos_a_procesar = self._construir_lista_impuestos(flags_impuestos)

        # Logging de resumen
        self._log_resumen(
            codigo_negocio,
            nombre_negocio,
            flags_impuestos,
            impuestos_a_procesar
        )

        return ResultadoValidacion(
            impuestos_a_procesar=impuestos_a_procesar,
            aplica_retencion=flags_impuestos['retencion'],
            aplica_estampilla=flags_impuestos['estampilla'],
            aplica_obra_publica=flags_impuestos['obra_publica'],
            aplica_iva=flags_impuestos['iva'],
            aplica_ica=flags_impuestos['ica'],
            aplica_timbre=flags_impuestos['timbre'],
            aplica_tasa_prodeporte=flags_impuestos['tasa_prodeporte'],
            nombre_negocio=nombre_negocio,
            nit_administrativo=nit_administrativo,
            deteccion_impuestos=deteccion_impuestos,
            nombre_entidad=nombre_entidad
        )

    def _extraer_datos_negocio(
        self,
        resultado_negocio: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extrae datos del negocio del resultado de BD"""
        return resultado_negocio.get('data') if resultado_negocio.get('success') else None

    def _validar_parametrizacion(
        self,
        datos_negocio: Optional[Dict[str, Any]],
        codigo_negocio: Any
    ) -> Optional[JSONResponse]:
        """
        Valida que el negocio esté parametrizado.

        Returns:
            JSONResponse si no está parametrizado, None si está OK
        """
        if not datos_negocio or 'nit' not in datos_negocio:
            logger.warning(f"Código de negocio {codigo_negocio} no parametrizado en base de datos")
            respuesta_mock = crear_respuesta_negocio_no_parametrizado(codigo_negocio)

            return JSONResponse(
                status_code=200,
                content=respuesta_mock
            )

        return None

    def _validar_nit_administrativo(
        self,
        nit_administrativo: str
    ) -> tuple[str, List[str]]:
        """
        Valida que el NIT administrativo sea válido.

        Returns:
            Tupla (nombre_entidad, impuestos_aplicables)

        Raises:
            HTTPException: Si NIT no es válido
        """
        es_valido, nombre_entidad, impuestos_aplicables = validar_nit_administrativo(nit_administrativo)

        if not es_valido:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "NIT administrativo no válido",
                    "nit_recibido": nit_administrativo,
                    "mensaje": "El NIT no está configurado en el sistema",
                    "nits_disponibles": list(obtener_nits_disponibles().keys())
                }
            )

        logger.info(f" NIT válido: {nombre_entidad}")
        logger.info(f"Impuestos configurados: {impuestos_aplicables}")

        return nombre_entidad, impuestos_aplicables

    def _detectar_impuestos(
        self,
        codigo_negocio: Any,
        nombre_negocio: str,
        nit_administrativo: str
    ) -> Dict[str, Any]:
        """Detecta impuestos aplicables usando código de negocio y NIT"""
        return detectar_impuestos_aplicables_por_codigo(
            codigo_negocio,
            nombre_negocio,
            nit_administrativo,
            self.business_service
        )

    def _determinar_flags_impuestos(
        self,
        nit_administrativo: str,
        impuestos_aplicables: List[str],
        deteccion_impuestos: Dict[str, Any]
    ) -> Dict[str, bool]:
        """
        Determina qué impuestos aplican basado en configuración.

        Returns:
            Diccionario con flags booleanos de cada impuesto
        """
        return {
            'retencion': "RETENCION_FUENTE" in impuestos_aplicables,
            'estampilla': deteccion_impuestos["aplica_estampilla_universidad"],
            'obra_publica': deteccion_impuestos["aplica_contribucion_obra_publica"],
            'iva': nit_aplica_iva_reteiva(nit_administrativo),
            'ica': nit_aplica_ICA(nit_administrativo),
            'tasa_prodeporte': nit_aplica_tasa_prodeporte(nit_administrativo),
            'timbre': nit_aplica_timbre(nit_administrativo)
        }

    def _construir_lista_impuestos(
        self,
        flags_impuestos: Dict[str, bool]
    ) -> List[str]:
        """
        Construye lista de impuestos a procesar basado en flags.

        Args:
            flags_impuestos: Diccionario con flags booleanos

        Returns:
            Lista de nombres de impuestos a procesar
        """
        mapeo_impuestos = {
            'retencion': 'RETENCION_FUENTE',
            'estampilla': 'ESTAMPILLA_UNIVERSIDAD',
            'obra_publica': 'CONTRIBUCION_OBRA_PUBLICA',
            'iva': 'IVA_RETEIVA',
            'ica': 'RETENCION_ICA',
            'timbre': 'IMPUESTO_TIMBRE'
        }

        return [
            nombre_impuesto
            for flag, nombre_impuesto in mapeo_impuestos.items()
            if flags_impuestos.get(flag, False)
        ]

    def _log_resumen(
        self,
        codigo_negocio: Any,
        nombre_negocio: str,
        flags_impuestos: Dict[str, bool],
        impuestos_a_procesar: List[str]
    ) -> None:
        """Registra resumen de la validación en logs"""
        logger.info(f" Código de negocio: {codigo_negocio} - {nombre_negocio}")
        logger.info(
            f" Aplica estampilla: {flags_impuestos['estampilla']}, "
            f"Aplica obra pública: {flags_impuestos['obra_publica']}, "
            f"Aplica ICA: {flags_impuestos['ica']}, "
            f"Aplica Timbre: {flags_impuestos['timbre']}, "
            f"Aplica tasa prodeporte: {flags_impuestos['tasa_prodeporte']}"
        )
        logger.info(" Estrategia: PROCESAMIENTO PARALELO (todos los NITs aplican múltiples impuestos)")
        logger.info(f" Impuestos a procesar: {impuestos_a_procesar}")


# Función de compatibilidad con código existente
def validar_negocio(
    resultado_negocio: Dict[str, Any],
    codigo_del_negocio: Any,
    business_service: Any
) -> ResultadoValidacion | JSONResponse:
    """
    Función wrapper para compatibilidad con código existente.

    Args:
        resultado_negocio: Resultado de obtener_datos_negocio()
        codigo_del_negocio: Código del negocio
        business_service: Servicio de BD

    Returns:
        JSONResponse si hay error, ResultadoValidacion si exitoso
    """
    validador = ValidadorNegocio(business_service)
    return validador.validar(resultado_negocio, codigo_del_negocio)
