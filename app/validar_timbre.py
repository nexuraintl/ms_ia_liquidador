"""
Modulo de validacion y liquidacion de Impuesto al Timbre.

Implementa validador para Impuesto al Timbre con doble analisis de Gemini.

Flujos implementados:
- Validacion de aplicabilidad segun observaciones de PGD
- Extraccion de datos del contrato con segunda llamada a Gemini
- Liquidacion del impuesto al timbre
- Consulta de tarifas en base de datos

Autor: Sistema Preliquidador
Version: 1.0 - Refactorizado con POO
"""

import logging
import traceback
from typing import Dict, Any, Optional

from Clasificador.clasificador_timbre import ClasificadorTimbre
from Liquidador.liquidador_timbre import LiquidadorTimbre


class ValidadorTimbre:
    """
    Validador de Impuesto al Timbre.

    Responsabilidad: Orquestar la validacion y liquidacion del Impuesto al Timbre
    con doble analisis de Gemini (observaciones + datos de contrato).

    Attributes:
        db_manager: Gestor de base de datos
        clasificador_gemini: Procesador Gemini para analisis
        liquidador_timbre: Liquidador de Timbre (inyectable)
        logger: Logger para registro de eventos
    """

    def __init__(
        self,
        db_manager: Any,
        clasificador_gemini: Any,
        liquidador_timbre: Optional[LiquidadorTimbre] = None
    ):
        """
        Inicializa el validador con inyeccion de dependencias.

        Args:
            db_manager: Gestor de base de datos
            clasificador_gemini: Procesador Gemini para analisis
            liquidador_timbre: Liquidador de Timbre (opcional, se crea si no se provee)
        """
        self.db_manager = db_manager
        self.clasificador_gemini = clasificador_gemini
        self.liquidador_timbre = liquidador_timbre
        self.logger = logging.getLogger(__name__)

    async def validar(
        self,
        resultados_analisis: Dict[str, Any],
        aplica_timbre: bool,
        nit_administrativo: str,
        codigo_del_negocio: int,
        proveedor: str,
        documentos_clasificados: Dict[str, Any],
        archivos_directos: list,
        cache_archivos: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Orquestador principal - valida y liquida Impuesto al Timbre.

        Coordina el flujo de validacion con doble analisis de Gemini:
        1. Verifica aplicabilidad segun observaciones
        2. Extrae datos del contrato (segunda llamada Gemini)
        3. Liquida el impuesto

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            aplica_timbre: Si aplica Timbre segun configuracion
            nit_administrativo: NIT administrativo
            codigo_del_negocio: Codigo del negocio
            proveedor: Nombre del proveedor
            documentos_clasificados: Documentos clasificados
            archivos_directos: Lista de archivos directos
            cache_archivos: Cache de archivos procesados

        Returns:
            Dict con estructura de timbre o None si no aplica
        """
        if not self._debe_procesar_timbre(resultados_analisis, aplica_timbre):
            return None

        try:
            return await self._procesar_liquidacion(
                resultados_analisis=resultados_analisis,
                nit_administrativo=nit_administrativo,
                codigo_del_negocio=codigo_del_negocio,
                proveedor=proveedor,
                documentos_clasificados=documentos_clasificados,
                archivos_directos=archivos_directos,
                cache_archivos=cache_archivos
            )

        except Exception as e:
            return self._manejar_error(e)

    def _debe_procesar_timbre(
        self,
        resultados_analisis: Dict[str, Any],
        aplica_timbre: bool
    ) -> bool:
        """
        Decide si hay datos para procesar Timbre.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            aplica_timbre: Si aplica Timbre segun configuracion

        Returns:
            True si debe procesar, False en caso contrario
        """
        return "timbre" in resultados_analisis and aplica_timbre

    async def _procesar_liquidacion(
        self,
        resultados_analisis: Dict[str, Any],
        nit_administrativo: str,
        codigo_del_negocio: int,
        proveedor: str,
        documentos_clasificados: Dict[str, Any],
        archivos_directos: list,
        cache_archivos: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Procesa la liquidacion de Timbre.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            nit_administrativo: NIT administrativo
            codigo_del_negocio: Codigo del negocio
            proveedor: Nombre del proveedor
            documentos_clasificados: Documentos clasificados
            archivos_directos: Lista de archivos directos
            cache_archivos: Cache de archivos procesados

        Returns:
            Dict con resultado de liquidacion
        """
        self.logger.info(" Liquidando Impuesto al Timbre...")

        # Obtener analisis de observaciones
        analisis_observaciones_timbre = resultados_analisis["timbre"]

        # Verificar aplicabilidad segun observaciones
        if not self._verifica_aplicabilidad_observaciones(analisis_observaciones_timbre):
            return self._crear_resultado_no_aplica_observaciones()

        # Extraer datos del contrato (segunda llamada Gemini)
        datos_contrato = await self._extraer_datos_contrato(
            documentos_clasificados=documentos_clasificados,
            archivos_directos=archivos_directos,
            cache_archivos=cache_archivos
        )

        # Ejecutar liquidacion
        resultado_timbre = self._ejecutar_liquidacion(
            nit_administrativo=nit_administrativo,
            codigo_del_negocio=codigo_del_negocio,
            proveedor=proveedor,
            analisis_observaciones=analisis_observaciones_timbre,
            datos_contrato=datos_contrato
        )

        # Convertir Pydantic a dict
        resultado_dict = resultado_timbre.dict()

        # Loguear resultado
        self._log_resultado(resultado_timbre)

        return resultado_dict

    def _verifica_aplicabilidad_observaciones(
        self,
        analisis_observaciones: Dict[str, Any]
    ) -> bool:
        """
        Verifica si aplica Timbre segun observaciones de PGD.

        Args:
            analisis_observaciones: Analisis de observaciones de Gemini

        Returns:
            True si aplica, False en caso contrario
        """
        return bool(analisis_observaciones.get("aplica_timbre", False))

    def _crear_resultado_no_aplica_observaciones(self) -> Dict[str, Any]:
        """
        Crea resultado cuando no aplica segun observaciones.

        Returns:
            Dict con estructura de no aplicacion
        """
        self.logger.info(" Timbre: No aplica según observaciones de PGD")

        return {
            "aplica": False,
            "estado": "no_aplica_impuesto",
            "valor": 0.0,
            "tarifa": 0.0,
            "tipo_cuantia": "",
            "base_gravable": 0.0,
            "ID_contrato": "",
            "observaciones": "No se identifico aplicacion del impuesto al timbre en observaciones"
        }

    async def _extraer_datos_contrato(
        self,
        documentos_clasificados: Dict[str, Any],
        archivos_directos: list,
        cache_archivos: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extrae datos del contrato con segunda llamada a Gemini.

        Args:
            documentos_clasificados: Documentos clasificados
            archivos_directos: Lista de archivos directos
            cache_archivos: Cache de archivos procesados

        Returns:
            Dict con datos del contrato extraidos
        """
        self.logger.info(" Timbre aplica - Extrayendo datos del contrato...")

        clasificador_timbre = ClasificadorTimbre(
            procesador_gemini=self.clasificador_gemini
        )

        return await clasificador_timbre.extraer_datos_contrato(
            documentos_clasificados=documentos_clasificados,
            archivos_directos=archivos_directos,
            cache_archivos=cache_archivos
        )

    def _ejecutar_liquidacion(
        self,
        nit_administrativo: str,
        codigo_del_negocio: int,
        proveedor: str,
        analisis_observaciones: Dict[str, Any],
        datos_contrato: Dict[str, Any]
    ) -> Any:
        """
        Ejecuta la liquidacion con el liquidador.

        Args:
            nit_administrativo: NIT administrativo
            codigo_del_negocio: Codigo del negocio
            proveedor: Nombre del proveedor
            analisis_observaciones: Analisis de observaciones de Gemini
            datos_contrato: Datos del contrato extraidos

        Returns:
            Resultado de liquidacion (modelo Pydantic)
        """
        # Lazy initialization si no se inyecto
        if self.liquidador_timbre is None:
            self.liquidador_timbre = LiquidadorTimbre(db_manager=self.db_manager)

        return self.liquidador_timbre.liquidar_timbre(
            nit_administrativo=nit_administrativo,
            codigo_negocio=str(codigo_del_negocio),
            nit_proveedor=proveedor,
            analisis_observaciones=analisis_observaciones,
            datos_contrato=datos_contrato
        )

    def _log_resultado(self, resultado_timbre: Any) -> None:
        """
        Maneja el logging del resultado de Timbre.

        Args:
            resultado_timbre: Resultado de liquidacion (modelo Pydantic)
        """
        if resultado_timbre.aplica:
            self.logger.info(
                f" Timbre liquidado: ${resultado_timbre.valor:,.2f} "
                f"(Tarifa: {resultado_timbre.tarifa*100}%)"
            )
        else:
            self.logger.info(f" Timbre: {resultado_timbre.estado}")

    def _manejar_error(self, e: Exception) -> Dict[str, Any]:
        """
        Maneja errores generales.

        Args:
            e: Excepcion capturada

        Returns:
            Dict con estructura de error
        """
        self.logger.error(f" Error liquidando Timbre: {e}")
        self.logger.error(traceback.format_exc())

        return {
            "aplica": False,
            "estado": "preliquidacion_sin_finalizar",
            "error": str(e),
            "observaciones": f"Error en liquidación Timbre: {str(e)}"
        }


async def validar_timbre(
    resultados_analisis: Dict[str, Any],
    aplica_timbre: bool,
    db_manager: Any,
    clasificador_gemini: Any,
    nit_administrativo: str,
    codigo_del_negocio: int,
    proveedor: str,
    documentos_clasificados: Dict[str, Any],
    archivos_directos: list,
    cache_archivos: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Wrapper function para mantener compatibilidad con main.py.

    Instancia ValidadorTimbre y delega la validacion.
    Esta funcion actua como punto de entrada publico.

    Args:
        resultados_analisis: Diccionario con analisis de Gemini
        aplica_timbre: Si aplica Timbre segun configuracion
        db_manager: Gestor de base de datos
        clasificador_gemini: Procesador Gemini para analisis
        nit_administrativo: NIT administrativo
        codigo_del_negocio: Codigo del negocio
        proveedor: Nombre del proveedor
        documentos_clasificados: Documentos clasificados
        archivos_directos: Lista de archivos directos
        cache_archivos: Cache de archivos procesados

    Returns:
        Dict con estructura para resultado_final["impuestos"]["timbre"]
        o None si no aplica
    """
    validador = ValidadorTimbre(
        db_manager=db_manager,
        clasificador_gemini=clasificador_gemini
    )

    return await validador.validar(
        resultados_analisis=resultados_analisis,
        aplica_timbre=aplica_timbre,
        nit_administrativo=nit_administrativo,
        codigo_del_negocio=codigo_del_negocio,
        proveedor=proveedor,
        documentos_clasificados=documentos_clasificados,
        archivos_directos=archivos_directos,
        cache_archivos=cache_archivos
    )
