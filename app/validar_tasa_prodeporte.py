"""
Modulo de validacion y liquidacion de Tasa Prodeporte.

Implementa validador para Tasa Prodeporte con parametros especificos del endpoint.

Flujos implementados:
- Liquidacion de Tasa Prodeporte con parametros del contrato
- Validacion de analisis de Gemini
- Conversion de modelos Pydantic a diccionarios

Autor: Sistema Preliquidador
Version: 1.0 - Refactorizado con POO
"""

import logging
import traceback
from typing import Dict, Any, Optional

from Liquidador.liquidador_TP import LiquidadorTasaProdeporte, ParametrosTasaProdeporte


class ValidadorTasaProdeporte:
    """
    Validador de Tasa Prodeporte.

    Responsabilidad: Orquestar la validacion y liquidacion de Tasa Prodeporte
    con parametros especificos del endpoint y analisis de Gemini.

    Attributes:
        db_manager: Gestor de base de datos
        liquidador_tp: Liquidador de Tasa Prodeporte (inyectable)
        logger: Logger para registro de eventos
    """

    def __init__(
        self,
        db_manager: Any,
        liquidador_tp: Optional[LiquidadorTasaProdeporte] = None
    ):
        """
        Inicializa el validador con inyeccion de dependencias.

        Args:
            db_manager: Gestor de base de datos
            liquidador_tp: Liquidador de Tasa Prodeporte (opcional, se crea si no se provee)
        """
        self.db_manager = db_manager
        self.liquidador_tp = liquidador_tp
        self.logger = logging.getLogger(__name__)

    async def validar(
        self,
        resultados_analisis: Dict[str, Any],
        observaciones_tp: Optional[str],
        genera_presupuesto: Optional[str],
        rubro: Optional[str],
        centro_costos: Optional[int],
        numero_contrato: Optional[str],
        valor_contrato_municipio: Optional[float]
    ) -> Optional[Dict[str, Any]]:
        """
        Orquestador principal - valida y liquida Tasa Prodeporte.

        Coordina el flujo de liquidacion de Tasa Prodeporte con parametros
        del endpoint y analisis de Gemini.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            observaciones_tp: Observaciones del tercero pagador
            genera_presupuesto: Indica si genera presupuesto
            rubro: Rubro presupuestal
            centro_costos: Centro de costos
            numero_contrato: Numero del contrato
            valor_contrato_municipio: Valor del contrato con el municipio

        Returns:
            Dict con estructura de tasa_prodeporte o None si no aplica
        """
        if not self._debe_procesar_tasa_prodeporte(resultados_analisis):
            return None

        try:
            return self._procesar_liquidacion(
                resultados_analisis=resultados_analisis,
                observaciones_tp=observaciones_tp,
                genera_presupuesto=genera_presupuesto,
                rubro=rubro,
                centro_costos=centro_costos,
                numero_contrato=numero_contrato,
                valor_contrato_municipio=valor_contrato_municipio
            )

        except Exception as e:
            return self._manejar_error(e)

    def _debe_procesar_tasa_prodeporte(
        self,
        resultados_analisis: Dict[str, Any]
    ) -> bool:
        """
        Decide si hay datos para procesar Tasa Prodeporte.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini

        Returns:
            True si debe procesar, False en caso contrario
        """
        return "tasa_prodeporte" in resultados_analisis

    def _procesar_liquidacion(
        self,
        resultados_analisis: Dict[str, Any],
        observaciones_tp: Optional[str],
        genera_presupuesto: Optional[str],
        rubro: Optional[str],
        centro_costos: Optional[int],
        numero_contrato: Optional[str],
        valor_contrato_municipio: Optional[float]
    ) -> Dict[str, Any]:
        """
        Procesa la liquidacion de Tasa Prodeporte.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            observaciones_tp: Observaciones del tercero pagador
            genera_presupuesto: Indica si genera presupuesto
            rubro: Rubro presupuestal
            centro_costos: Centro de costos
            numero_contrato: Numero del contrato
            valor_contrato_municipio: Valor del contrato con el municipio

        Returns:
            Dict con resultado de liquidacion
        """
        self.logger.info(" Liquidando Tasa Prodeporte...")

        # Obtener analisis de Gemini
        analisis_tp_gemini = resultados_analisis["tasa_prodeporte"]

        # Crear parametros
        parametros_tp = self._crear_parametros(
            observaciones_tp=observaciones_tp,
            genera_presupuesto=genera_presupuesto,
            rubro=rubro,
            centro_costos=centro_costos,
            numero_contrato=numero_contrato,
            valor_contrato_municipio=valor_contrato_municipio
        )

        # Ejecutar liquidacion
        resultado_tp = self._ejecutar_liquidacion(parametros_tp, analisis_tp_gemini)

        # Convertir Pydantic a dict
        resultado_dict = resultado_tp.dict()

        # Loguear resultado
        self._log_resultado(resultado_tp)

        return resultado_dict

    def _crear_parametros(
        self,
        observaciones_tp: Optional[str],
        genera_presupuesto: Optional[str],
        rubro: Optional[str],
        centro_costos: Optional[int],
        numero_contrato: Optional[str],
        valor_contrato_municipio: Optional[float]
    ) -> ParametrosTasaProdeporte:
        """
        Crea los parametros de Tasa Prodeporte.

        Args:
            observaciones_tp: Observaciones del tercero pagador
            genera_presupuesto: Indica si genera presupuesto
            rubro: Rubro presupuestal
            centro_costos: Centro de costos
            numero_contrato: Numero del contrato
            valor_contrato_municipio: Valor del contrato con el municipio

        Returns:
            ParametrosTasaProdeporte con los datos del endpoint
        """
        return ParametrosTasaProdeporte(
            observaciones=observaciones_tp,
            genera_presupuesto=genera_presupuesto,
            rubro=rubro,
            centro_costos=centro_costos,
            numero_contrato=numero_contrato,
            valor_contrato_municipio=valor_contrato_municipio
        )

    def _ejecutar_liquidacion(
        self,
        parametros_tp: ParametrosTasaProdeporte,
        analisis_tp_gemini: Any
    ) -> Any:
        """
        Ejecuta la liquidacion con el liquidador.

        Args:
            parametros_tp: Parametros de Tasa Prodeporte
            analisis_tp_gemini: Analisis de Gemini para Tasa Prodeporte

        Returns:
            Resultado de liquidacion (modelo Pydantic)
        """
        # Lazy initialization si no se inyecto
        if self.liquidador_tp is None:
            self.liquidador_tp = LiquidadorTasaProdeporte(db_interface=self.db_manager)

        return self.liquidador_tp.liquidar(parametros_tp, analisis_tp_gemini)

    def _log_resultado(self, resultado_tp: Any) -> None:
        """
        Maneja el logging del resultado de Tasa Prodeporte.

        Args:
            resultado_tp: Resultado de liquidacion (modelo Pydantic)
        """
        if resultado_tp.aplica:
            self.logger.info(
                f" Tasa Prodeporte liquidada: ${resultado_tp.valor_imp:,.2f} "
                f"(Tarifa: {resultado_tp.tarifa*100}%)"
            )
        else:
            self.logger.info(f" Tasa Prodeporte: {resultado_tp.estado}")

    def _manejar_error(self, e: Exception) -> Dict[str, Any]:
        """
        Maneja errores generales.

        Args:
            e: Excepcion capturada

        Returns:
            Dict con estructura de error
        """
        self.logger.error(f" Error liquidando Tasa Prodeporte: {e}")
        self.logger.error(traceback.format_exc())

        return {
            "error": str(e),
            "aplica": False,
            "estado": "preliquidacion_sin_finalizar"
        }


async def validar_tasa_prodeporte(
    resultados_analisis: Dict[str, Any],
    db_manager: Any,
    observaciones_tp: Optional[str] = None,
    genera_presupuesto: Optional[str] = None,
    rubro: Optional[str] = None,
    centro_costos: Optional[int] = None,
    numero_contrato: Optional[str] = None,
    valor_contrato_municipio: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """
    Wrapper function para mantener compatibilidad con main.py.

    Instancia ValidadorTasaProdeporte y delega la validacion.
    Esta funcion actua como punto de entrada publico.

    Args:
        resultados_analisis: Diccionario con analisis de Gemini
        db_manager: Gestor de base de datos
        observaciones_tp: Observaciones del tercero pagador
        genera_presupuesto: Indica si genera presupuesto
        rubro: Rubro presupuestal
        centro_costos: Centro de costos
        numero_contrato: Numero del contrato
        valor_contrato_municipio: Valor del contrato con el municipio

    Returns:
        Dict con estructura para resultado_final["impuestos"]["tasa_prodeporte"]
        o None si no aplica
    """
    validador = ValidadorTasaProdeporte(db_manager=db_manager)

    return await validador.validar(
        resultados_analisis=resultados_analisis,
        observaciones_tp=observaciones_tp,
        genera_presupuesto=genera_presupuesto,
        rubro=rubro,
        centro_costos=centro_costos,
        numero_contrato=numero_contrato,
        valor_contrato_municipio=valor_contrato_municipio
    )
