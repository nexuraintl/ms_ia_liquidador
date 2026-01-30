"""
Modulo de validacion y liquidacion de Sobretasa Bomberil.

Implementa validador para Sobretasa Bomberil que depende del resultado de ICA.

Flujos implementados:
- Liquidacion de Sobretasa Bomberil basada en resultado de ICA
- Consulta de tarifas bomberiles por municipio
- Manejo de multiples ubicaciones

Autor: Sistema Preliquidador
Version: 1.0 - Refactorizado con POO
"""

import logging
import traceback
from typing import Dict, Any, Optional

from Liquidador.liquidador_sobretasa_b import LiquidadorSobretasaBomberil


class ValidadorSobretasa:
    """
    Validador de Sobretasa Bomberil.

    Responsabilidad: Orquestar la validacion y liquidacion de Sobretasa Bomberil
    basada en el resultado previo de ICA.

    Attributes:
        db_manager: Gestor de base de datos
        liquidador_sobretasa: Liquidador de Sobretasa Bomberil (inyectable)
        logger: Logger para registro de eventos
    """

    def __init__(
        self,
        db_manager: Any,
        liquidador_sobretasa: Optional[LiquidadorSobretasaBomberil] = None
    ):
        """
        Inicializa el validador con inyeccion de dependencias.

        Args:
            db_manager: Gestor de base de datos
            liquidador_sobretasa: Liquidador de Sobretasa Bomberil (opcional, se crea si no se provee)
        """
        self.db_manager = db_manager
        self.liquidador_sobretasa = liquidador_sobretasa
        self.logger = logging.getLogger(__name__)

    async def validar(self, resultado_final: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Orquestador principal - valida y liquida Sobretasa Bomberil.

        Coordina el flujo de liquidacion de Sobretasa Bomberil basado
        en el resultado previo de ICA.

        Args:
            resultado_final: Diccionario con resultado final que incluye
                           resultado_final["impuestos"]["ica"]

        Returns:
            Dict con estructura de sobretasa_bomberil o None si no aplica
        """
        if not self._debe_procesar_sobretasa(resultado_final):
            return None

        try:
            return self._procesar_liquidacion(resultado_final)

        except Exception as e:
            return self._manejar_error(e)

    def _debe_procesar_sobretasa(self, resultado_final: Dict[str, Any]) -> bool:
        """
        Decide si hay datos para procesar Sobretasa Bomberil.

        Args:
            resultado_final: Diccionario con resultado final completo

        Returns:
            True si debe procesar, False en caso contrario
        """
        return "impuestos" in resultado_final and "ica" in resultado_final["impuestos"]

    def _procesar_liquidacion(self, resultado_final: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa la liquidacion de Sobretasa Bomberil.

        Args:
            resultado_final: Diccionario con resultado final completo

        Returns:
            Dict con resultado de liquidacion
        """
        self.logger.info(" Liquidando Sobretasa Bomberil...")

        # Obtener resultado de ICA
        resultado_ica = resultado_final["impuestos"]["ica"]

        # Ejecutar liquidacion
        resultado_sobretasa = self._ejecutar_liquidacion(resultado_ica)

        # Loguear resultado
        self._log_resultado(resultado_sobretasa)

        return resultado_sobretasa

    def _ejecutar_liquidacion(
        self,
        resultado_ica: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ejecuta la liquidacion con el liquidador.

        Args:
            resultado_ica: Resultado de liquidacion de ICA

        Returns:
            Dict con resultado de liquidacion
        """
        # Lazy initialization si no se inyecto
        if self.liquidador_sobretasa is None:
            self.liquidador_sobretasa = LiquidadorSobretasaBomberil(
                database_manager=self.db_manager
            )

        return self.liquidador_sobretasa.liquidar_sobretasa_bomberil(resultado_ica)

    def _log_resultado(self, resultado_sobretasa: Dict[str, Any]) -> None:
        """
        Maneja el logging del resultado de Sobretasa Bomberil.

        Args:
            resultado_sobretasa: Resultado de liquidacion de Sobretasa Bomberil
        """
        estado_sobretasa = resultado_sobretasa.get("estado", "Desconocido")
        valor_sobretasa = resultado_sobretasa.get("valor_total_sobretasa", 0.0)

        self.logger.info(f" Sobretasa Bomberil - Estado: {estado_sobretasa}")
        self.logger.info(f" Sobretasa Bomberil - Valor total: ${valor_sobretasa:,.2f}")

    def _manejar_error(self, e: Exception) -> Dict[str, Any]:
        """
        Maneja errores generales.

        Args:
            e: Excepcion capturada

        Returns:
            Dict con estructura de error
        """
        self.logger.error(f" Error liquidando Sobretasa Bomberil: {e}")
        self.logger.error(traceback.format_exc())

        return {
            "aplica": False,
            "estado": "preliquidacion_sin_finalizar",
            "error": str(e),
            "valor_total_sobretasa": 0.0,
            "ubicaciones": [],
            "observaciones": [f"Error en liquidacion Sobretasa Bomberil: {str(e)}"]
        }


async def validar_sobretasa_bomberil(
    resultado_final: Dict[str, Any],
    db_manager: Any
) -> Optional[Dict[str, Any]]:
    """
    Wrapper function para mantener compatibilidad con main.py.

    Instancia ValidadorSobretasa y delega la validacion.
    Esta funcion actua como punto de entrada publico.

    Args:
        resultado_final: Diccionario con resultado final que incluye
                        resultado_final["impuestos"]["ica"]
        db_manager: Gestor de base de datos

    Returns:
        Dict con estructura para resultado_final["impuestos"]["sobretasa_bomberil"]
        o None si no aplica
    """
    validador = ValidadorSobretasa(db_manager=db_manager)

    return await validador.validar(resultado_final=resultado_final)
