"""
LIQUIDADOR IMPUESTO AL TIMBRE
==============================

Modulo para calcular el Impuesto al Timbre con validaciones manuales en Python.
Gemini solo identifica datos, Python aplica toda la logica de negocio.

Responsabilidad (SRP): Solo calculos y validaciones de timbre
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from config import UVT_2025

logger = logging.getLogger(__name__)


class ResultadoTimbre(BaseModel):
    """Modelo para el resultado del calculo de timbre"""
    aplica: bool
    estado: str
    valor: float
    tarifa: float
    tipo_cuantia: str
    base_gravable: float
    ID_contrato: str
    observaciones: str


class LiquidadorTimbre:
    """
    Liquidador especializado para Impuesto al Timbre.

    Responsabilidad (SRP): Solo validaciones y calculos de timbre
    Principio: Python hace TODAS las validaciones, Gemini solo identifica
    """

    # Fecha limite para validaciones
    FECHA_LIMITE_TIMBRE = datetime(2025, 2, 22)

    def __init__(self, db_manager=None):
        """
        Inicializa el liquidador con dependencia de base de datos.

        Args:
            db_manager: Gestor de base de datos para consultas (DIP)
        """
        self.db_manager = db_manager
        logger.info("LiquidadorTimbre inicializado")

    def liquidar_timbre(
        self,
        nit_administrativo: str,
        codigo_negocio: str,
        nit_proveedor: str,
        analisis_observaciones: Dict[str, Any],
        datos_contrato: Dict[str, Any] = None
    ) -> ResultadoTimbre:
        """
        Calcula el Impuesto al Timbre con validaciones manuales completas.

        Args:
            nit_administrativo: NIT del administrativo
            codigo_negocio: Código del negocio para consultar BD
            nit_proveedor: NIT del proveedor para consultar BD
            analisis_observaciones: Resultado del analisis de observaciones de Gemini
            datos_contrato: Resultado de la extraccion de contrato de Gemini (opcional)

        Returns:
            ResultadoTimbre: Resultado completo del calculo
        """
        logger.info(f"Iniciando liquidacion de Impuesto al Timbre para NIT: {nit_administrativo}")

        # VALIDACION 1: Verificar si aplica_timbre segun observaciones
        aplica_timbre = analisis_observaciones.get("aplica_timbre", False)
        base_gravable_obs = analisis_observaciones.get("base_gravable_obs", 0.0)

        if not aplica_timbre:
            return self._crear_resultado_no_aplica(
                observaciones="No se identifico aplicacion del impuesto al timbre en el campo Observaciones de PGD"
            )

        logger.info(f"Aplica timbre segun observaciones - Base obs: ${base_gravable_obs:,.2f}")

        # VALIDACION 1.5: Verificar datos del contrato y consultar BD para tarifa y tipo_cuantia
        if not datos_contrato:
            return self._crear_resultado_sin_finalizar(
                tipo_cuantia="",
                observaciones="No se pudieron extraer datos del contrato para determinar la base gravable"
            )

        id_contrato = datos_contrato.get("id_contrato", "")

        # Validar que ID_contrato no sea string vacío
        if not id_contrato or id_contrato.strip() == "":
            return self._crear_resultado_sin_finalizar(
                tipo_cuantia="",
                observaciones="No se pudo identificar el ID del contrato en los documentos adjuntos. Porfavor revisar adjuntos"
            )

        logger.info(f"ID contrato identificado: {id_contrato}")

        # VALIDACION 1.75: Verificar límite mínimo de 6000 UVT
        valor_total_contrato = datos_contrato.get("valor_total_contrato", 0.0)

        # Validar que exista valor_total_contrato
        if valor_total_contrato <= 0:
            logger.warning(f"Contrato {id_contrato}: valor_total_contrato no disponible o es 0 - No se puede validar límite de 6000 UVT")
            return self._crear_resultado_sin_finalizar(
                tipo_cuantia="",
                observaciones=f"No se pudo identificar el valor de la cuantía del contrato {id_contrato} para validar el límite mínimo de 6000 UVT requerido",
                id_contrato=id_contrato
            )

        # Convertir valor_total_contrato a UVT
        uvt_contrato = valor_total_contrato / UVT_2025
        limite_uvt = 6000
        valor_limite_pesos = limite_uvt * UVT_2025

        logger.info(f"Validando límite UVT para contrato {id_contrato}: Valor ${valor_total_contrato:,.2f} = {uvt_contrato:,.2f} UVT (límite mínimo: {limite_uvt} UVT)")

        # Validar que cumpla límite mínimo de 6000 UVT
        if uvt_contrato < limite_uvt:
            logger.info(f"Contrato {id_contrato} NO alcanza el límite mínimo de {limite_uvt} UVT - Impuesto NO aplica")
            return self._crear_resultado_no_aplica(
                observaciones=(
                    f"El contrato {id_contrato} no alcanza el límite mínimo de {limite_uvt:,} UVT "
                    f"(${valor_limite_pesos:,.2f}) requerido para aplicar el Impuesto al Timbre. "
                    f"Valor del contrato: ${valor_total_contrato:,.2f} ({uvt_contrato:,.2f} UVT)"
                ),
                id_contrato=id_contrato
            )

        logger.info(f"Contrato {id_contrato} cumple límite mínimo de {limite_uvt} UVT - Continuando con procesamiento")

        # Consultar BD para obtener tarifa y tipo_cuantia
        resultado_bd = self._consultar_cuantia_bd(
            id_contrato=id_contrato,
            codigo_negocio=codigo_negocio,
            nit_proveedor=nit_proveedor
        )

        # Si hay error en la consulta, retornar resultado de error
        if isinstance(resultado_bd, ResultadoTimbre):
            return resultado_bd

        # Si la consulta fue exitosa, extraer tarifa y tipo_cuantia
        tarifa_bd, tipo_cuantia_bd = resultado_bd
        logger.info(f"Tarifa BD: {tarifa_bd}, Tipo cuantía BD: {tipo_cuantia_bd}")

        # VALIDACION 2: Verificar base gravable en observaciones
        if base_gravable_obs > 0:
            # Usar base gravable de observaciones y continuar directo al calculo
            logger.info(f"Base gravable extraida de observaciones: ${base_gravable_obs:,.2f}")

            valor_impuesto = base_gravable_obs * tarifa_bd
            id_contrato = datos_contrato.get("id_contrato", "") if datos_contrato else ""

            return ResultadoTimbre(
                aplica=True,
                estado="preliquidado",
                valor=valor_impuesto,
                tarifa=tarifa_bd,
                tipo_cuantia=tipo_cuantia_bd,
                base_gravable=base_gravable_obs,
                ID_contrato=id_contrato,
                observaciones=f"Base gravable extraida del campo observaciones: ${base_gravable_obs:,.2f}"
            )

        # Si base_gravable_obs <= 0, continuar con determinacion en segunda llamada
        logger.info("Base gravable no identificada en observaciones, continuando con extraccion de contrato")

        # VALIDACION 3: Verificar que existan datos del contrato
        if not datos_contrato:
            return self._crear_resultado_sin_finalizar(
                tipo_cuantia=tipo_cuantia_bd,
                observaciones="No se pudieron extraer datos del contrato para determinar la base gravable"
            )

        # DETERMINACION DE BASE GRAVABLE SEGUN TIPO DE CUANTIA
        if tipo_cuantia_bd == "I":
            return self._procesar_cuantia_indeterminable(
                base_gravable_obs=base_gravable_obs,
                tarifa_bd=tarifa_bd,
                datos_contrato=datos_contrato
            )
        elif tipo_cuantia_bd == "D":
            return self._procesar_cuantia_determinable(
                tarifa_bd=tarifa_bd,
                datos_contrato=datos_contrato
            )
        else:
            return self._crear_resultado_sin_finalizar(
                tipo_cuantia=tipo_cuantia_bd,
                observaciones=f"Tipo de cuantia no reconocido: {tipo_cuantia_bd}"
            )

    def _procesar_cuantia_indeterminable(
        self,
        base_gravable_obs: float,
        tarifa_bd: float,
        datos_contrato: Dict[str, Any]
    ) -> ResultadoTimbre:
        """
        Procesa cuantia indeterminable.

        Para cuantia indeterminable, la base gravable DEBE venir de observaciones.
        """
        logger.info("Procesando cuantia INDETERMINABLE")

        id_contrato = datos_contrato.get("id_contrato", "")
        
        observacion_base = f"Cuantia indeterminable - Base gravable de observaciones: ${base_gravable_obs:,.2f}"

        if base_gravable_obs <= 0:
            
            valor_factura_sin_iva = datos_contrato.get("valor_factura_sin_iva", 0.0)
            
            if valor_factura_sin_iva > 0:
                
                base_gravable_obs = valor_factura_sin_iva
                logger.info(f"Usando valor factura sin IVA como base gravable: ${base_gravable_obs:,.2f}")
                observacion_base = f"Base gravable tomada del valor de la factura sin IVA: ${base_gravable_obs:,.2f}"
                
            else:
                
                return self._crear_resultado_sin_finalizar(
                    tipo_cuantia="Indeterminable",
                    observaciones="El tipo de cuantia es indeterminable y no se pudo identificar la base gravable en las observaciones , ni se encontro valor de factura sin IVA en los documentos",
                    id_contrato=id_contrato
                )

        # Calcular impuesto
        valor_impuesto = base_gravable_obs * tarifa_bd

        return ResultadoTimbre(
            aplica=True,
            estado="preliquidado",
            valor=valor_impuesto,
            tarifa=tarifa_bd,
            tipo_cuantia="Indeterminable",
            base_gravable=base_gravable_obs,
            ID_contrato=id_contrato,
            observaciones=observacion_base
        )

    def _procesar_cuantia_determinable(
        self,
        tarifa_bd: float,
        datos_contrato: Dict[str, Any]
    ) -> ResultadoTimbre:
        """
        Procesa cuantia determinable con validaciones de fechas y adiciones.

        Logica compleja de validacion segun fecha de suscripcion.
        """
        logger.info("Procesando cuantia DETERMINABLE")

        # Extraer datos del contrato
        id_contrato = datos_contrato.get("id_contrato", "")
        fecha_suscripcion_str = datos_contrato.get("fecha_suscripcion", "0000-00-00")
        valor_inicial_contrato = datos_contrato.get("valor_inicial_contrato", 0.0)
        valor_total_contrato = datos_contrato.get("valor_total_contrato", 0.0)
        adiciones = datos_contrato.get("adiciones", [])

        # VALIDACION: Fecha de suscripcion
        if fecha_suscripcion_str == "0000-00-00":
            return self._crear_resultado_sin_finalizar(
                tipo_cuantia="Determinable",
                observaciones="El tipo de cuantia es determinable y no se pudo identificar la fecha de suscripcion del contrato en los anexos",
                id_contrato=id_contrato
            )

        # Parsear fecha de suscripcion
        try:
            fecha_suscripcion = datetime.strptime(fecha_suscripcion_str, "%Y-%m-%d")
        except ValueError:
            return self._crear_resultado_sin_finalizar(
                tipo_cuantia="Determinable",
                observaciones=f"Formato de fecha de suscripcion invalido: {fecha_suscripcion_str}",
                id_contrato=id_contrato
            )

        logger.info(f"Fecha suscripcion: {fecha_suscripcion_str}")

        # CASO 1: Contrato suscrito ANTES del 22 de febrero de 2025
        if fecha_suscripcion < self.FECHA_LIMITE_TIMBRE:
            return self._procesar_contrato_antes_limite(
                fecha_suscripcion_str=fecha_suscripcion_str,
                adiciones=adiciones,
                tarifa_bd=tarifa_bd,
                id_contrato=id_contrato
            )

        # CASO 2: Contrato suscrito POSTERIOR al 22 de febrero de 2025
        else:
            return self._procesar_contrato_posterior_limite(
                fecha_suscripcion_str=fecha_suscripcion_str,
                valor_total_contrato=valor_total_contrato,
                tarifa_bd=tarifa_bd,
                id_contrato=id_contrato
            )

    def _procesar_contrato_antes_limite(
        self,
        fecha_suscripcion_str: str,
        adiciones: List[Dict[str, Any]],
        tarifa_bd: float,
        id_contrato: str
    ) -> ResultadoTimbre:
        """
        Procesa contratos suscritos ANTES del 22 de febrero de 2025.

        Solo aplica timbre a adiciones posteriores a la fecha limite.
        """
        logger.info(f"Contrato suscrito ANTES del 22/02/2025 ({fecha_suscripcion_str})")

        # Validar adiciones una por una
        adiciones_validas = []
        adiciones_con_error = []

        for idx, adicion in enumerate(adiciones):
            valor_adicion = adicion.get("valor_adicion", 0.0)
            fecha_adicion_str = adicion.get("fecha_adicion", "0000-00-00")

            # Validar que tenga valor
            if valor_adicion <= 0:
                logger.info(f"Adicion {idx+1}: Valor <= 0, omitiendo")
                continue

            # Validar que tenga fecha
            if fecha_adicion_str == "0000-00-00":
                adiciones_con_error.append({
                    "indice": idx + 1,
                    "valor": valor_adicion,
                    "error": "Sin fecha identificada"
                })
                logger.warning(f"Adicion {idx+1}: Valor ${valor_adicion:,.2f} pero sin fecha")
                continue

            # Parsear fecha de adicion
            try:
                fecha_adicion = datetime.strptime(fecha_adicion_str, "%Y-%m-%d")
            except ValueError:
                adiciones_con_error.append({
                    "indice": idx + 1,
                    "valor": valor_adicion,
                    "error": f"Formato de fecha invalido: {fecha_adicion_str}"
                })
                continue

            # Validar si la adicion es posterior al 22 de febrero de 2025
            if fecha_adicion > self.FECHA_LIMITE_TIMBRE:
                adiciones_validas.append({
                    "valor": valor_adicion,
                    "fecha": fecha_adicion_str
                })
                logger.info(f"Adicion {idx+1}: ${valor_adicion:,.2f} en {fecha_adicion_str} - VALIDA")
            else:
                logger.info(f"Adicion {idx+1}: ${valor_adicion:,.2f} en {fecha_adicion_str} - ANTES del limite")

        # Si hay adiciones con error, preliquidacion sin finalizar
        if adiciones_con_error:
            errores_desc = "; ".join([
                f"Adicion {e['indice']}: ${e['valor']:,.2f} - {e['error']}"
                for e in adiciones_con_error
            ])
            return self._crear_resultado_sin_finalizar(
                tipo_cuantia="Determinable",
                observaciones=f"No se pudo identificar la fecha de adiciones: {errores_desc}",
                id_contrato=id_contrato
            )

        # Si no hay adiciones validas
        if not adiciones_validas:
            # Verificar si todas las adiciones tienen valor <= 0
            todas_sin_valor = all(
                adicion.get("valor_adicion", 0.0) <= 0
                for adicion in adiciones
            )

            if todas_sin_valor or not adiciones:
                return self._crear_resultado_no_aplica(
                    observaciones=f"La cuantia del contrato es determinada, la fecha de suscripcion del contrato fue en {fecha_suscripcion_str} y no hay adiciones en el contrato"
                )
            else:
                # Todas las adiciones son anteriores al limite
                return self._crear_resultado_sin_finalizar(
                    tipo_cuantia="Determinable",
                    observaciones=f"La cuantia es determinada y el contrato y sus adiciones fueron suscritos antes del 22 de febrero del 2025",
                    id_contrato=id_contrato
                )

        # Calcular base gravable sumando adiciones validas
        base_gravable = sum(adicion["valor"] for adicion in adiciones_validas)
        valor_impuesto = base_gravable * tarifa_bd

        adiciones_detalle = "; ".join([
            f"${ad['valor']:,.2f} ({ad['fecha']})"
            for ad in adiciones_validas
        ])

        return ResultadoTimbre(
            aplica=True,
            estado="preliquidado",
            valor=valor_impuesto,
            tarifa=tarifa_bd,
            tipo_cuantia="Determinable",
            base_gravable=base_gravable,
            ID_contrato=id_contrato,
            observaciones=(
                f"Contrato suscrito el {fecha_suscripcion_str} (antes del 22/02/2025). "
                f"Se aplica timbre a {len(adiciones_validas)} adicion(es) posterior(es) al 22/02/2025: {adiciones_detalle}"
            )
        )

    def _procesar_contrato_posterior_limite(
        self,
        fecha_suscripcion_str: str,
        valor_total_contrato: float,
        tarifa_bd: float,
        id_contrato: str
    ) -> ResultadoTimbre:
        """
        Procesa contratos suscritos POSTERIOR al 22 de febrero de 2025.

        La base gravable es el valor total del contrato.
        """
        logger.info(f"Contrato suscrito POSTERIOR al 22/02/2025 ({fecha_suscripcion_str})")

        if valor_total_contrato <= 0:
            return self._crear_resultado_sin_finalizar(
                tipo_cuantia="Determinable",
                observaciones=f"Contrato suscrito el {fecha_suscripcion_str} pero no se identifico el valor total del contrato",
                id_contrato=id_contrato
            )

        # Calcular impuesto
        base_gravable = valor_total_contrato
        valor_impuesto = base_gravable * tarifa_bd

        return ResultadoTimbre(
            aplica=True,
            estado="preliquidado",
            valor=valor_impuesto,
            tarifa=tarifa_bd,
            tipo_cuantia="Determinable",
            base_gravable=base_gravable,
            ID_contrato=id_contrato,
            observaciones=(
                f"Contrato suscrito el {fecha_suscripcion_str} (posterior al 22/02/2025). "
                f"Base gravable: valor total del contrato ${base_gravable:,.2f}"
            )
        )

    def _consultar_cuantia_bd(
        self,
        id_contrato: str,
        codigo_negocio: str,
        nit_proveedor: str
    ):
        """
        Consulta la base de datos para obtener tarifa y tipo de cuantía.

        Args:
            id_contrato: ID del contrato identificado por Gemini
            codigo_negocio: Código del negocio
            nit_proveedor: NIT del proveedor

        Returns:
            tuple (tarifa, tipo_cuantia) si es exitoso
            ResultadoTimbre con error si falla la consulta
        """
        if not self.db_manager:
            logger.error("No se ha inyectado db_manager - No se puede consultar BD")
            return self._crear_resultado_sin_finalizar(
                tipo_cuantia="",
                observaciones="Error interno: No se puede acceder a la base de datos",
                id_contrato=id_contrato
            )

        logger.info(f"Consultando tabla CUANTIAS para contrato {id_contrato}...")

        try:
            resultado_cuantia = self.db_manager.obtener_cuantia_contrato(
                id_contrato=id_contrato,
                codigo_negocio=str(codigo_negocio),
                nit_proveedor=nit_proveedor
            )

            # Caso 1: Consulta exitosa pero sin datos
            if not resultado_cuantia.get('success'):
                logger.warning(f"No se encontró cuantía en BD para contrato {id_contrato}")
                return self._crear_resultado_sin_finalizar(
                    tipo_cuantia="",
                    observaciones=f"No se pudo identificar el ID del contrato en el sistema ya que no se encontro tipo de cuantia en base de datos para el contrato {id_contrato}",
                    id_contrato=id_contrato
                )

            # Caso 2: Consulta exitosa con datos
            data_cuantia = resultado_cuantia.get('data', {})
            tarifa = data_cuantia.get('tarifa', 0.0)
            tipo_cuantia = data_cuantia.get('tipo_cuantia', 'Indeterminable')

            logger.info(f"Cuantía encontrada en BD - Tipo: {tipo_cuantia}, Tarifa: {tarifa}")

            return (tarifa, tipo_cuantia)

        except Exception as e:
            # Caso 3: Error en la consulta
            logger.error(f"Error al consultar BD para contrato {id_contrato}: {e}")
            return self._crear_resultado_sin_finalizar(
                tipo_cuantia="",
                observaciones=f"Error en la base de datos: {str(e)}",
                id_contrato=id_contrato
            )

    def _crear_resultado_no_aplica(
        self,
        observaciones: str,
        id_contrato: str = ""
    ) -> ResultadoTimbre:
        """Crea resultado cuando no aplica el impuesto"""
        logger.info(f"NO APLICA IMPUESTO: {observaciones}")

        return ResultadoTimbre(
            aplica=False,
            estado="no_aplica_impuesto",
            valor=0.0,
            tarifa=0.0,
            tipo_cuantia="",
            base_gravable=0.0,
            ID_contrato=id_contrato,
            observaciones=observaciones
        )

    def _crear_resultado_sin_finalizar(
        self,
        tipo_cuantia: str,
        observaciones: str,
        id_contrato: str = ""
    ) -> ResultadoTimbre:
        """Crea resultado cuando la preliquidacion no puede finalizarse"""
        logger.warning(f"PRELIQUIDACION SIN FINALIZAR: {observaciones}")

        return ResultadoTimbre(
            aplica=False,
            estado="preliquidacion_sin_finalizar",
            valor=0.0,
            tarifa=0.0,
            tipo_cuantia=tipo_cuantia,
            base_gravable=0.0,
            ID_contrato=id_contrato,
            observaciones=observaciones
        )
