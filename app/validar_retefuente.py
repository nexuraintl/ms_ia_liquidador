"""
Modulo de validacion y liquidacion de retencion en la fuente.

Implementa validador siguiendo principios SOLID:
- SRP: Cada metodo tiene una responsabilidad unica
- OCP: Extensible mediante herencia
- DIP: Inyeccion de dependencias para facilitar testing

Flujos implementados:
- Consorcios: Liquidacion por consorciado con validaciones manuales
- Normal: Liquidacion para persona natural/juridica
- Recurso extranjero: Estructura vacia sin liquidacion

Autor: Sistema Preliquidador
Version: 3.1 - Refactorizado con POO
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from Liquidador import LiquidadorRetencion
from Liquidador.liquidador_consorcios import (
    LiquidadorConsorcios,
    convertir_resultado_a_dict as convertir_consorcio_a_dict
)

from config import (
    CONCEPTOS_RETEFUENTE,
    guardar_archivo_json,
    crear_resultado_recurso_extranjero_retefuente
)


class ValidadorRetefuente:
    """
    Validador de retencion en la fuente siguiendo principios SOLID.

    Responsabilidad: Orquestar la validacion y liquidacion de retefuente
    segun el tipo de tercero (consorcio/normal/recurso extranjero).

    Attributes:
        estructura_contable: Codigo de estructura contable
        db_manager: Gestor de base de datos
        liquidador_consorcios: Liquidador de consorcios (inyectable)
        liquidador_retencion: Liquidador normal (inyectable)
        logger: Logger para registro de eventos
    """

    def __init__(
        self,
        estructura_contable: int,
        db_manager: Any,
        liquidador_consorcios: Optional[LiquidadorConsorcios] = None,
        liquidador_retencion: Optional[LiquidadorRetencion] = None
    ):
        """
        Inicializa el validador con inyeccion de dependencias.

        Args:
            estructura_contable: Codigo de estructura contable
            db_manager: Gestor de base de datos
            liquidador_consorcios: Liquidador de consorcios (opcional, se crea si no se provee)
            liquidador_retencion: Liquidador normal (opcional, se crea si no se provee)
        """
        self.estructura_contable = estructura_contable
        self.db_manager = db_manager
        self.liquidador_consorcios = liquidador_consorcios
        self.liquidador_retencion = liquidador_retencion
        self.logger = logging.getLogger(__name__)

    async def validar(
        self,
        resultados_analisis: dict,
        aplica_retencion: bool,
        es_consorcio: bool,
        es_recurso_extranjero: bool,
        es_facturacion_extranjera: bool,
        nit_administrativo: str,
        tipoMoneda: str,
        archivos_directos: list,
        cache_archivos: dict
    ) -> Optional[Dict[str, Any]]:
        """
        Orquestador principal - valida y liquida retencion en la fuente.

        SRP: Solo coordina el flujo, delega la logica especifica a metodos privados.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            aplica_retencion: Si el NIT aplica retencion
            es_consorcio: Si es consorcio
            es_recurso_extranjero: Si es recurso extranjero
            es_facturacion_extranjera: Si es facturacion del exterior
            nit_administrativo: NIT de la entidad
            tipoMoneda: Tipo de moneda
            archivos_directos: Archivos originales
            cache_archivos: Cache de archivos

        Returns:
            Dict con estructura de retefuente o None si no aplica
        """
        # Verificar si debe procesar
        if not self._debe_procesar_retefuente(resultados_analisis, aplica_retencion):
            return self._manejar_caso_especial(aplica_retencion, es_recurso_extranjero)

        # Procesar segun tipo
        try:
            if es_consorcio:
                return await self._procesar_consorcio(
                    resultados_analisis,
                    archivos_directos,
                    cache_archivos
                )
            else:
                return await self._procesar_normal(
                    resultados_analisis,
                    es_facturacion_extranjera,
                    nit_administrativo,
                    tipoMoneda
                )
        except Exception as e:
            return self._manejar_error(e)

    def _debe_procesar_retefuente(
        self,
        resultados_analisis: dict,
        aplica_retencion: bool
    ) -> bool:
        """
        SRP: Solo decide si hay datos para procesar retefuente.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            aplica_retencion: Si el NIT aplica retencion

        Returns:
            True si debe procesar, False en caso contrario
        """
        return "retefuente" in resultados_analisis and aplica_retencion

    def _manejar_caso_especial(
        self,
        aplica_retencion: bool,
        es_recurso_extranjero: bool
    ) -> Optional[Dict[str, Any]]:
        """
        SRP: Solo maneja el caso especial de recurso extranjero.

        Args:
            aplica_retencion: Si el NIT aplica retencion
            es_recurso_extranjero: Si es recurso extranjero

        Returns:
            Dict con estructura de recurso extranjero o None
        """
        if aplica_retencion and es_recurso_extranjero:
            self.logger.info(" Retefuente: Aplicando estructura de recurso extranjero")
            resultado = crear_resultado_recurso_extranjero_retefuente()

            resultado_dict = {
                "aplica": resultado.aplica,
                "estado": resultado.estado,
                "valor_factura_sin_iva": resultado.valor_factura_sin_iva,
                "valor_retencion": resultado.valor_retencion,
                "valor_base": resultado.valor_base_retencion,
                "conceptos_aplicados": resultado.conceptos_aplicados,
                "observaciones": resultado.mensajes_error,
            }
            self.logger.info(" Retefuente: No aplica (Recurso de fuente extranjera)")
            return resultado_dict

        return None

    async def _procesar_consorcio(
        self,
        resultados_analisis: dict,
        archivos_directos: list,
        cache_archivos: dict
    ) -> Dict[str, Any]:
        """
        SRP: Solo procesa liquidacion de consorcios.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            archivos_directos: Archivos originales
            cache_archivos: Cache de archivos

        Returns:
            Dict con resultado de liquidacion de consorcio
        """
        # Lazy initialization si no se inyecto
        if self.liquidador_consorcios is None:
            self.liquidador_consorcios = LiquidadorConsorcios(
                estructura_contable=self.estructura_contable,
                db_manager=self.db_manager
            )

        analisis_gemini = resultados_analisis["retefuente"]

        resultado = await self.liquidador_consorcios.liquidar_consorcio(
            analisis_gemini,
            CONCEPTOS_RETEFUENTE,
            archivos_directos,
            cache_archivos
        )

        resultado_dict = convertir_consorcio_a_dict(resultado)
        resultado_retefuente = resultado_dict["retefuente"]

        self.logger.info(
            f" Retefuente liquidada: ${resultado_retefuente.get('valor_retencion', 0):,.2f}"
        )

        return resultado_retefuente

    async def _procesar_normal(
        self,
        resultados_analisis: dict,
        es_facturacion_extranjera: bool,
        nit_administrativo: str,
        tipoMoneda: str
    ) -> Dict[str, Any]:
        """
        SRP: Solo procesa liquidacion normal (persona natural/juridica).

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            es_facturacion_extranjera: Si es facturacion del exterior
            nit_administrativo: NIT de la entidad
            tipoMoneda: Tipo de moneda

        Returns:
            Dict con resultado de liquidacion normal
        """
        analisis_factura = resultados_analisis["retefuente"]

        # Preparar datos para liquidacion
        analisis_data = self._preparar_analisis_data(
            analisis_factura,
            es_facturacion_extranjera,
            nit_administrativo
        )

        # Guardar para debugging
        guardar_archivo_json(analisis_data, "analisis_retefuente_paralelo")

        # Liquidar
        resultado_dict = await self._ejecutar_liquidacion_normal(
            analisis_data,
            nit_administrativo,
            tipoMoneda
        )

        # Procesar resultado
        return self._procesar_resultado_normal(
            resultado_dict,
            es_facturacion_extranjera
        )

    def _preparar_analisis_data(
        self,
        analisis_factura: Any,
        es_facturacion_extranjera: bool,
        nit_administrativo: str
    ) -> Dict[str, Any]:
        """
        SRP: Solo prepara la estructura de datos para analisis.

        Args:
            analisis_factura: Analisis de Gemini
            es_facturacion_extranjera: Si es facturacion del exterior
            nit_administrativo: NIT de la entidad

        Returns:
            Dict con estructura preparada para liquidacion
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "tipo_analisis": "retefuente_paralelo",
            "nit_administrativo": nit_administrativo,
            "es_facturacion_exterior": es_facturacion_extranjera,
            "analisis": (
                analisis_factura.dict()
                if hasattr(analisis_factura, 'dict')
                else analisis_factura
            )
        }

    async def _ejecutar_liquidacion_normal(
        self,
        analisis_data: Dict[str, Any],
        nit_administrativo: str,
        tipoMoneda: str
    ) -> Dict[str, Any]:
        """
        SRP: Solo ejecuta la liquidacion normal.

        Args:
            analisis_data: Datos preparados para liquidacion
            nit_administrativo: NIT de la entidad
            tipoMoneda: Tipo de moneda

        Returns:
            Dict con resultado de liquidacion
        """
        self.logger.info(" Ejecutando liquidacion segura en procesamiento paralelo...")

        # Lazy initialization si no se inyecto
        if self.liquidador_retencion is None:
            self.liquidador_retencion = LiquidadorRetencion(
                estructura_contable=self.estructura_contable,
                db_manager=self.db_manager
            )

        return self.liquidador_retencion.liquidar_retefuente_seguro(
            analisis_data,
            nit_administrativo,
            tipoMoneda=tipoMoneda
        )

    def _procesar_resultado_normal(
        self,
        resultado_dict: Dict[str, Any],
        es_facturacion_extranjera: bool
    ) -> Dict[str, Any]:
        """
        SRP: Solo procesa y formatea el resultado final.

        Args:
            resultado_dict: Diccionario con resultado de liquidacion
            es_facturacion_extranjera: Si es facturacion del exterior

        Returns:
            Dict con estructura final de retefuente
        """
        if "error" in resultado_dict:
            return self._crear_resultado_error(resultado_dict)

        resultado_final = self._crear_resultado_exitoso(resultado_dict)

        # Agregar pais si aplica
        if es_facturacion_extranjera and "pais_proveedor" in resultado_dict:
            resultado_final["pais_proveedor"] = resultado_dict.get("pais_proveedor", "")
            self.logger.info(f" Pais proveedor: {resultado_dict.get('pais_proveedor')}")

        # Logging
        self._log_resultado(resultado_dict)

        return resultado_final

    def _crear_resultado_error(self, resultado_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        SRP: Solo crea estructura de resultado con error.

        Args:
            resultado_dict: Diccionario con error

        Returns:
            Dict con estructura de error
        """
        error_msg = resultado_dict.get('error')
        self.logger.error(f"Error tecnico en liquidacion: {error_msg}")

        return {
            "aplica": False,
            "estado": "preliquidacion_sin_finalizar",
            "valor_factura_sin_iva": 0.0,
            "valor_retencion": 0.0,
            "valor_base": 0.0,
            "conceptos_aplicados": [],
            "observaciones": [error_msg],
        }

    def _crear_resultado_exitoso(self, resultado_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        SRP: Solo crea estructura de resultado exitoso.

        Args:
            resultado_dict: Diccionario con resultado exitoso

        Returns:
            Dict con estructura exitosa
        """
        return {
            "aplica": resultado_dict.get("aplica", False),
            "estado": resultado_dict.get("estado", "preliquidacion_sin_finalizar"),
            "valor_factura_sin_iva": resultado_dict.get("valor_factura_sin_iva", 0.0),
            "valor_retencion": resultado_dict.get("valor_retencion", 0.0),
            "valor_base": resultado_dict.get("base_gravable", 0.0),
            "conceptos_aplicados": resultado_dict.get("conceptos_aplicados", []),
            "observaciones": resultado_dict.get("observaciones", []),
        }

    def _log_resultado(self, resultado_dict: Dict[str, Any]) -> None:
        """
        SRP: Solo maneja el logging del resultado.

        Args:
            resultado_dict: Diccionario con resultado
        """
        valor = resultado_dict.get('valor_retencion', 0.0)
        if valor > 0:
            self.logger.info(f"Retefuente liquidada: ${valor:,.2f}")
        else:
            estado = resultado_dict.get("estado", "preliquidado")
            self.logger.info(f"Retefuente procesada - Estado: {estado}")

        self.logger.info(f" Retefuente liquidada: ${valor:,.2f}")

    def _manejar_error(self, e: Exception) -> Dict[str, Any]:
        """
        SRP: Solo maneja errores generales.

        Args:
            e: Excepcion capturada

        Returns:
            Dict con estructura de error
        """
        self.logger.error(f" Error liquidando retefuente: {e}")
        return {"error": str(e), "aplica": False}


async def validar_retencion_en_la_fuente(
    resultados_analisis: dict,
    aplica_retencion: bool,
    es_consorcio: bool,
    es_recurso_extranjero: bool,
    es_facturacion_extranjera: bool,
    estructura_contable: int,
    db_manager: Any,
    nit_administrativo: str,
    tipoMoneda: str,
    archivos_directos: list,
    cache_archivos: dict
) -> Optional[Dict[str, Any]]:
    """
    Wrapper function para mantener compatibilidad con main.py.

    Instancia ValidadorRetefuente y delega la validacion.
    Esta funcion actua como punto de entrada publico.

    Args:
        resultados_analisis: Diccionario con analisis de Gemini para todos los impuestos
        aplica_retencion: Si el NIT administrativo aplica retencion en la fuente
        es_consorcio: Si el proveedor es un consorcio
        es_recurso_extranjero: Si es recurso de fuente extranjera
        es_facturacion_extranjera: Si es facturacion del exterior
        estructura_contable: Codigo de estructura contable
        db_manager: Gestor de base de datos
        nit_administrativo: NIT de la entidad administrativa
        tipoMoneda: Tipo de moneda ("COP" o "USD")
        archivos_directos: Lista de archivos originales
        cache_archivos: Cache de bytes de archivos para validaciones

    Returns:
        Dict con estructura completa para resultado_final["impuestos"]["retefuente"]
        o None si no aplica retencion
    """
    validador = ValidadorRetefuente(
        estructura_contable=estructura_contable,
        db_manager=db_manager
    )

    return await validador.validar(
        resultados_analisis=resultados_analisis,
        aplica_retencion=aplica_retencion,
        es_consorcio=es_consorcio,
        es_recurso_extranjero=es_recurso_extranjero,
        es_facturacion_extranjera=es_facturacion_extranjera,
        nit_administrativo=nit_administrativo,
        tipoMoneda=tipoMoneda,
        archivos_directos=archivos_directos,
        cache_archivos=cache_archivos
    )
