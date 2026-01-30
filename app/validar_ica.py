"""
Modulo de validacion y liquidacion de ICA (Impuesto de Industria y Comercio).

Implementa validador para ICA con manejo de municipios y actividades economicas.
Incluye liquidacion por actividad economica y calculo de tarifas por municipio.

Flujos implementados:
- Liquidacion de ICA por municipio
- Calculo de tarifa segun actividad economica
- Manejo de multiples municipios

Autor: Sistema Preliquidador
Version: 1.0 - Refactorizado con POO
"""

import logging
import traceback
from typing import Dict, Any, Optional

from Liquidador.liquidador_ica import LiquidadorICA


class ValidadorICA:
    """
    Validador de ICA (Impuesto de Industria y Comercio).

    Responsabilidad: Orquestar la validacion y liquidacion de ICA
    segun municipios y actividades economicas identificadas.

    Attributes:
        estructura_contable: Codigo de estructura contable
        db_manager: Gestor de base de datos
        liquidador_ica: Liquidador de ICA (inyectable)
        logger: Logger para registro de eventos
    """

    def __init__(
        self,
        estructura_contable: int,
        db_manager: Any,
        liquidador_ica: Optional[LiquidadorICA] = None
    ):
        """
        Inicializa el validador con inyeccion de dependencias.

        Args:
            estructura_contable: Codigo de estructura contable
            db_manager: Gestor de base de datos
            liquidador_ica: Liquidador de ICA (opcional, se crea si no se provee)
        """
        self.estructura_contable = estructura_contable
        self.db_manager = db_manager
        self.liquidador_ica = liquidador_ica
        self.logger = logging.getLogger(__name__)

    async def validar(
        self,
        resultados_analisis: dict,
        aplica_ica: bool,
        tipoMoneda: str
    ) -> Optional[Dict[str, Any]]:
        """
        Orquestador principal - valida y liquida ICA.

        Coordina el flujo de liquidacion de ICA segun municipios y
        actividades economicas identificadas en el analisis.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            aplica_ica: Si aplica ICA
            tipoMoneda: Tipo de moneda ("COP" o "USD")

        Returns:
            Dict con estructura de ica o None si no aplica
        """
        # Verificar si debe procesar
        if not self._debe_procesar_ica(resultados_analisis, aplica_ica):
            return None

        # Procesar liquidacion
        try:
            return await self._procesar_liquidacion(
                resultados_analisis,
                tipoMoneda
            )
        except Exception as e:
            return self._manejar_error(e)

    def _debe_procesar_ica(
        self,
        resultados_analisis: dict,
        aplica_ica: bool
    ) -> bool:
        """
        Decide si hay datos para procesar ICA.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            aplica_ica: Si aplica ICA

        Returns:
            True si debe procesar, False en caso contrario
        """
        return "ica" in resultados_analisis and aplica_ica

    async def _procesar_liquidacion(
        self,
        resultados_analisis: dict,
        tipoMoneda: str
    ) -> Dict[str, Any]:
        """
        Procesa la liquidacion de ICA.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            tipoMoneda: Tipo de moneda

        Returns:
            Dict con resultado de liquidacion
        """
        self.logger.info(" Liquidando ICA...")

        # Obtener analisis
        analisis_ica = resultados_analisis["ica"]

        # Ejecutar liquidacion
        resultado_ica = self._ejecutar_liquidacion(
            analisis_ica,
            tipoMoneda
        )

        # Loguear resultado
        self._log_resultado(resultado_ica)

        return resultado_ica

    def _ejecutar_liquidacion(
        self,
        analisis_ica: Any,
        tipoMoneda: str
    ) -> Dict[str, Any]:
        """
        Ejecuta la liquidacion con el liquidador.

        Args:
            analisis_ica: Analisis de ICA
            tipoMoneda: Tipo de moneda

        Returns:
            Dict con resultado de liquidacion
        """
        # Lazy initialization si no se inyecto
        if self.liquidador_ica is None:
            self.liquidador_ica = LiquidadorICA(database_manager=self.db_manager)

        return self.liquidador_ica.liquidar_ica(
            analisis_ica,
            self.estructura_contable,
            tipoMoneda=tipoMoneda
        )

    def _log_resultado(self, resultado_ica: Dict[str, Any]) -> None:
        """
        Maneja el logging del resultado de ICA.

        Args:
            resultado_ica: Resultado de liquidacion de ICA
        """
        estado_ica = resultado_ica.get("estado", "Desconocido")
        valor_ica = resultado_ica.get("valor_total_ica", 0.0)

        self.logger.info(f" ICA - Estado: {estado_ica}")
        self.logger.info(f" ICA - Valor total: ${valor_ica:,.2f}")

    def _manejar_error(self, e: Exception) -> Dict[str, Any]:
        """
        Maneja errores generales.

        Args:
            e: Excepcion capturada

        Returns:
            Dict con estructura de error
        """
        self.logger.error(f" Error liquidando ICA: {e}")
        self.logger.error(traceback.format_exc())

        return {
            "aplica": False,
            "estado": "preliquidacion_sin_finalizar",
            "error": str(e),
            "observaciones": [f"Error en liquidación ICA: {str(e)}"]
        }


async def validar_ica(
    resultados_analisis: dict,
    aplica_ica: bool,
    estructura_contable: int,
    db_manager: Any,
    tipoMoneda: str
) -> Optional[Dict[str, Any]]:
    """
    Wrapper function para mantener compatibilidad con main.py.

    Instancia ValidadorICA y delega la validacion.
    Esta funcion actua como punto de entrada publico.

    Args:
        resultados_analisis: Diccionario con analisis de Gemini para todos los impuestos
        aplica_ica: Si aplica ICA
        estructura_contable: Codigo de estructura contable
        db_manager: Gestor de base de datos
        tipoMoneda: Tipo de moneda ("COP" o "USD")

    Returns:
        Dict con estructura para resultado_final["impuestos"]["ica"]
        o None si no aplica
    """
    validador = ValidadorICA(
        estructura_contable=estructura_contable,
        db_manager=db_manager
    )

    return await validador.validar(
        resultados_analisis=resultados_analisis,
        aplica_ica=aplica_ica,
        tipoMoneda=tipoMoneda
    )
