"""
Modulo para agregar impuestos no aplicados al resultado final.

Implementa validador para estructurar impuestos que no aplicaron
segun la configuracion del negocio.

Flujos implementados:
- Agregacion de estampilla universidad no aplicada
- Agregacion de contribucion obra publica no aplicada
- Agregacion de IVA/ReteIVA no aplicado
- Agregacion de tasa prodeporte no aplicada
- Agregacion de timbre no aplicado

Autor: Sistema Preliquidador
Version: 1.0 - Refactorizado con POO
"""

import logging
from datetime import datetime
from typing import Dict, Any, List


class ValidadorNoAplicacion:
    """
    Validador para agregar impuestos no aplicados al resultado final.

    Responsabilidad: Agregar estructuras de impuestos que no aplicaron
    segun la configuracion del negocio, manteniendo consistencia en
    el formato de respuesta.

    Attributes:
        logger: Logger para registro de eventos
    """

    def __init__(self, logger: logging.Logger):
        """
        Inicializa el validador con inyeccion de dependencias.

        Args:
            logger: Logger para registro de eventos
        """
        self.logger = logger

    def agregar_impuestos_no_aplicados(
        self,
        resultado_final: Dict[str, Any],
        deteccion_impuestos: Dict[str, Any],
        aplica_estampilla: bool,
        aplica_obra_publica: bool,
        aplica_iva: bool,
        aplica_tasa_prodeporte: bool,
        aplica_timbre: bool,
        nit_administrativo: str,
        nombre_negocio: str
    ) -> None:
        """
        Orquestador principal - agrega impuestos no aplicados al resultado.

        Verifica cada impuesto y agrega su estructura al resultado_final
        si no aplica segun la configuracion del negocio y no fue procesado
        anteriormente.

        Args:
            resultado_final: Diccionario de resultado a modificar
            deteccion_impuestos: Configuracion de deteccion de impuestos
            aplica_estampilla: Si aplica estampilla universidad
            aplica_obra_publica: Si aplica contribucion obra publica
            aplica_iva: Si aplica IVA/ReteIVA
            aplica_tasa_prodeporte: Si aplica tasa prodeporte
            aplica_timbre: Si aplica timbre
            nit_administrativo: NIT administrativo del negocio
            nombre_negocio: Nombre del negocio
        """
        self._agregar_estampilla_no_aplicada(
            resultado_final=resultado_final,
            deteccion_impuestos=deteccion_impuestos,
            aplica_estampilla=aplica_estampilla,
            nombre_negocio=nombre_negocio
        )

        self._agregar_obra_publica_no_aplicada(
            resultado_final=resultado_final,
            deteccion_impuestos=deteccion_impuestos,
            aplica_obra_publica=aplica_obra_publica,
            nombre_negocio=nombre_negocio
        )

        self._agregar_iva_no_aplicado(
            resultado_final=resultado_final,
            aplica_iva=aplica_iva,
            nit_administrativo=nit_administrativo
        )

        self._agregar_tasa_prodeporte_no_aplicada(
            resultado_final=resultado_final,
            aplica_tasa_prodeporte=aplica_tasa_prodeporte,
            nit_administrativo=nit_administrativo
        )

        self._agregar_timbre_no_aplicado(
            resultado_final=resultado_final,
            aplica_timbre=aplica_timbre,
            nit_administrativo=nit_administrativo
        )

    def _agregar_estampilla_no_aplicada(
        self,
        resultado_final: Dict[str, Any],
        deteccion_impuestos: Dict[str, Any],
        aplica_estampilla: bool,
        nombre_negocio: str
    ) -> None:
        """
        Agrega estructura de estampilla universidad cuando no aplica.

        Verifica si debe agregarse segun configuracion y crea estructura
        con valores en cero y razon de no aplicacion.

        Args:
            resultado_final: Diccionario de resultado a modificar
            deteccion_impuestos: Configuracion de deteccion de impuestos
            aplica_estampilla: Si aplica estampilla segun configuracion
            nombre_negocio: Nombre del negocio
        """
        if not self._debe_agregar_impuesto(
            aplica=aplica_estampilla,
            impuesto_key="estampilla_universidad",
            resultado_final=resultado_final
        ):
            return

        razon = deteccion_impuestos.get(
            "razon_no_aplica_estampilla"
        ) or f"El negocio {nombre_negocio} no aplica este impuesto"

        estado = deteccion_impuestos.get("estado_especial") or "no_aplica_impuesto"

        mensajes_error = self._construir_mensajes_error(
            deteccion_impuestos=deteccion_impuestos,
            razon_default=razon
        )

        resultado_final["impuestos"]["estampilla_universidad"] = {
            "aplica": False,
            "estado": estado,
            "valor_estampilla": 0.0,
            "tarifa_aplicada": 0.0,
            "valor_factura_sin_iva": 0.0,
            "rango_uvt": "",
            "valor_contrato_pesos": 0.0,
            "valor_contrato_uvt": 0.0,
            "mensajes_error": mensajes_error,
            "razon": razon,
        }

        self.logger.info(f" Estampilla Universidad: {estado} - {razon}")

    def _agregar_obra_publica_no_aplicada(
        self,
        resultado_final: Dict[str, Any],
        deteccion_impuestos: Dict[str, Any],
        aplica_obra_publica: bool,
        nombre_negocio: str
    ) -> None:
        """
        Agrega estructura de contribucion obra publica cuando no aplica.

        Verifica si debe agregarse segun configuracion y crea estructura
        con valores en cero y razon de no aplicacion.

        Args:
            resultado_final: Diccionario de resultado a modificar
            deteccion_impuestos: Configuracion de deteccion de impuestos
            aplica_obra_publica: Si aplica obra publica segun configuracion
            nombre_negocio: Nombre del negocio
        """
        if not self._debe_agregar_impuesto(
            aplica=aplica_obra_publica,
            impuesto_key="contribucion_obra_publica",
            resultado_final=resultado_final
        ):
            return

        razon = deteccion_impuestos.get(
            "razon_no_aplica_obra_publica"
        ) or f"El negocio {nombre_negocio} no aplica este impuesto"

        estado = deteccion_impuestos.get("estado_especial") or "no_aplica_impuesto"

        mensajes_error = self._construir_mensajes_error(
            deteccion_impuestos=deteccion_impuestos,
            razon_default=razon
        )

        resultado_final["impuestos"]["contribucion_obra_publica"] = {
            "aplica": False,
            "estado": estado,
            "tarifa_aplicada": 0.0,
            "valor_contribucion": 0.0,
            "valor_factura_sin_iva": 0.0,
            "mensajes_error": mensajes_error,
            "razon": razon,
        }

        self.logger.info(f" Contribucion Obra Publica: {estado} - {razon}")

    def _agregar_iva_no_aplicado(
        self,
        resultado_final: Dict[str, Any],
        aplica_iva: bool,
        nit_administrativo: str
    ) -> None:
        """
        Agrega estructura de IVA/ReteIVA cuando no aplica.

        Verifica si debe agregarse segun configuracion y crea estructura
        con valores en cero y mensaje sobre configuracion de NIT.

        Args:
            resultado_final: Diccionario de resultado a modificar
            aplica_iva: Si aplica IVA/ReteIVA segun configuracion
            nit_administrativo: NIT administrativo del negocio
        """
        if not self._debe_agregar_impuesto(
            aplica=aplica_iva,
            impuesto_key="iva_reteiva",
            resultado_final=resultado_final
        ):
            return

        resultado_final["impuestos"]["iva_reteiva"] = {
            "aplica": False,
            "valor_iva_identificado": 0,
            "valor_subtotal_sin_iva": 0,
            "valor_reteiva": 0,
            "porcentaje_iva": 0,
            "tarifa_reteiva": 0,
            "es_fuente_nacional": False,
            "estado_liquidacion": "no_aplica_impuesto",
            "observaciones": [f"El NIT {nit_administrativo} no esta configurado para IVA/ReteIVA"],
            "calculo_exitoso": False
        }

        self.logger.info(f" IVA/ReteIVA: No aplica para NIT {nit_administrativo}")

    def _agregar_tasa_prodeporte_no_aplicada(
        self,
        resultado_final: Dict[str, Any],
        aplica_tasa_prodeporte: bool,
        nit_administrativo: str
    ) -> None:
        """
        Agrega estructura de tasa prodeporte cuando no aplica.

        Verifica si debe agregarse segun configuracion y crea estructura
        con valores en cero y mensaje sobre NIT FONTUR.

        Args:
            resultado_final: Diccionario de resultado a modificar
            aplica_tasa_prodeporte: Si aplica tasa prodeporte segun configuracion
            nit_administrativo: NIT administrativo del negocio
        """
        if not self._debe_agregar_impuesto(
            aplica=aplica_tasa_prodeporte,
            impuesto_key="tasa_prodeporte",
            resultado_final=resultado_final
        ):
            return

        resultado_final["impuestos"]["tasa_prodeporte"] = {
            "estado": "no_aplica_impuesto",
            "aplica": False,
            "valor_imp": 0.0,
            "tarifa": 0.0,
            "valor_convenio_sin_iva": 0.0,
            "porcentaje_convenio": 0.0,
            "valor_contrato_municipio": 0.0,
            "factura_sin_iva": 0.0,
            "factura_con_iva": 0.0,
            "municipio_dept": "",
            "numero_contrato": "",
            "observaciones": f"Tasa Prodeporte solo aplica para PATRIMONIO AUTONOMO FONTUR (NIT 900649119). NIT actual: {nit_administrativo}",
            "fecha_calculo": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        self.logger.info(f" Tasa Prodeporte: No aplica para NIT {nit_administrativo} (solo FONTUR 900649119)")

    def _agregar_timbre_no_aplicado(
        self,
        resultado_final: Dict[str, Any],
        aplica_timbre: bool,
        nit_administrativo: str
    ) -> None:
        """
        Agrega estructura de timbre cuando no aplica.

        Verifica si debe agregarse segun configuracion y crea estructura
        con valores en cero y mensaje simple de no aplicacion.

        Args:
            resultado_final: Diccionario de resultado a modificar
            aplica_timbre: Si aplica timbre segun configuracion
            nit_administrativo: NIT administrativo del negocio
        """
        if not self._debe_agregar_impuesto(
            aplica=aplica_timbre,
            impuesto_key="timbre",
            resultado_final=resultado_final
        ):
            return

        resultado_final["impuestos"]["timbre"] = {
            "aplica": False,
            "estado": "no_aplica_impuesto",
            "valor": 0.0,
            "tarifa": 0.0,
            "tipo_cuantia": "",
            "base_gravable": 0.0,
            "ID_contrato": "",
            "observaciones": f"Nit {nit_administrativo} no aplica impuesto al timbre"
        }

        self.logger.info(f" Timbre: No aplica para NIT {nit_administrativo}")

    def _construir_mensajes_error(
        self,
        deteccion_impuestos: Dict[str, Any],
        razon_default: str
    ) -> List[str]:
        """
        Construye lista de mensajes de error sin duplicados.

        Prioriza observaciones de validacion_recurso si existen,
        de lo contrario usa la razon por defecto.

        Args:
            deteccion_impuestos: Configuracion de deteccion de impuestos
            razon_default: Razon por defecto si no hay observaciones

        Returns:
            Lista con mensajes de error (sin duplicados)
        """
        validacion_recurso = deteccion_impuestos.get("validacion_recurso", {})
        observaciones = validacion_recurso.get("observaciones")

        if observaciones:
            return [observaciones]

        return [razon_default]

    def _debe_agregar_impuesto(
        self,
        aplica: bool,
        impuesto_key: str,
        resultado_final: Dict[str, Any]
    ) -> bool:
        """
        Verifica si debe agregar un impuesto no aplicado.

        Retorna True si el impuesto no aplica segun configuracion
        Y no existe previamente en resultado_final.

        Args:
            aplica: Si aplica el impuesto segun configuracion
            impuesto_key: Clave del impuesto en resultado_final["impuestos"]
            resultado_final: Diccionario de resultado a verificar

        Returns:
            True si debe agregarse, False en caso contrario
        """
        return not aplica and impuesto_key not in resultado_final["impuestos"]


def agregar_impuestos_no_aplicados(
    resultado_final: Dict[str, Any],
    deteccion_impuestos: Dict[str, Any],
    aplica_estampilla: bool,
    aplica_obra_publica: bool,
    aplica_iva: bool,
    aplica_tasa_prodeporte: bool,
    aplica_timbre: bool,
    nit_administrativo: str,
    nombre_negocio: str
) -> None:
    """
    Wrapper para mantener compatibilidad con main.py.

    Agrega al resultado_final los impuestos que no aplicaron
    segun la configuracion del negocio. Modifica resultado_final
    in-place agregando estructuras de impuestos no aplicados.

    Esta funcion actua como punto de entrada publico.

    Args:
        resultado_final: Diccionario de resultado a modificar
        deteccion_impuestos: Configuracion de deteccion de impuestos
        aplica_estampilla: Si aplica estampilla universidad
        aplica_obra_publica: Si aplica contribucion obra publica
        aplica_iva: Si aplica IVA/ReteIVA
        aplica_tasa_prodeporte: Si aplica tasa prodeporte
        aplica_timbre: Si aplica timbre
        nit_administrativo: NIT administrativo del negocio
        nombre_negocio: Nombre del negocio
    """
    validador = ValidadorNoAplicacion(logger=logging.getLogger(__name__))

    validador.agregar_impuestos_no_aplicados(
        resultado_final=resultado_final,
        deteccion_impuestos=deteccion_impuestos,
        aplica_estampilla=aplica_estampilla,
        aplica_obra_publica=aplica_obra_publica,
        aplica_iva=aplica_iva,
        aplica_tasa_prodeporte=aplica_tasa_prodeporte,
        aplica_timbre=aplica_timbre,
        nit_administrativo=nit_administrativo,
        nombre_negocio=nombre_negocio
    )
