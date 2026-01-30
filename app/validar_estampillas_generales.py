"""
Modulo de validacion y liquidacion de estampillas generales.

Implementa validador para estampillas generales identificadas por Gemini.
Incluye validacion de formato de respuesta y presentacion de resultados.

Flujos implementados:
- Validacion de formato de respuesta de Gemini
- Correccion automatica de errores de formato
- Presentacion estructurada de resultados

Autor: Sistema Preliquidador
Version: 1.0 - Refactorizado con POO
"""

import logging
from typing import Dict, Any, Optional

from Liquidador.liquidador_estampillas_generales import (
    validar_formato_estampillas_generales,
    presentar_resultado_estampillas_generales
)


class ValidadorEstampillasGenerales:
    """
    Validador de estampillas generales.

    Responsabilidad: Orquestar la validacion y liquidacion de estampillas
    generales identificadas en el analisis de Gemini.

    Attributes:
        logger: Logger para registro de eventos
    """

    def __init__(self):
        """Inicializa el validador."""
        self.logger = logging.getLogger(__name__)

    async def validar(
        self,
        resultados_analisis: dict
    ) -> Optional[Dict[str, Any]]:
        """
        Orquestador principal - valida y liquida estampillas generales.

        Coordina el flujo de validacion de formato y presentacion de resultados
        para estampillas generales identificadas por Gemini.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini

        Returns:
            Dict con estructura de estampillas_generales o None si no aplica
        """
        # Verificar si debe procesar
        if not self._debe_procesar_estampillas_generales(resultados_analisis):
            return None

        # Procesar liquidacion
        try:
            return await self._procesar_liquidacion(resultados_analisis)
        except Exception as e:
            return self._manejar_error(e)

    def _debe_procesar_estampillas_generales(
        self,
        resultados_analisis: dict
    ) -> bool:
        """
        Decide si hay datos para procesar estampillas generales.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini

        Returns:
            True si debe procesar, False en caso contrario
        """
        return "estampillas_generales" in resultados_analisis

    async def _procesar_liquidacion(
        self,
        resultados_analisis: dict
    ) -> Dict[str, Any]:
        """
        Procesa la liquidacion de estampillas generales.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini

        Returns:
            Dict con resultado de liquidacion
        """
        analisis_estampillas = resultados_analisis["estampillas_generales"]

        # Validar formato
        validacion = self._validar_formato(analisis_estampillas)

        # Loguear resultado de validacion
        self._log_validacion(validacion)

        # Obtener respuesta validada
        respuesta_validada = validacion["respuesta_validada"]

        # Presentar resultado final
        return self._presentar_resultado(respuesta_validada)

    def _validar_formato(
        self,
        analisis_estampillas: Any
    ) -> Dict[str, Any]:
        """
        Valida el formato de la respuesta de Gemini.

        Args:
            analisis_estampillas: Analisis de Gemini para estampillas

        Returns:
            Dict con resultado de validacion (formato_valido, errores, respuesta_validada)
        """
        return validar_formato_estampillas_generales(analisis_estampillas)

    def _log_validacion(self, validacion: Dict[str, Any]) -> None:
        """
        Maneja el logging del resultado de validacion.

        Args:
            validacion: Resultado de validacion de formato
        """
        if validacion["formato_valido"]:
            self.logger.info(" Formato de estampillas generales válido")
        else:
            errores = validacion.get("errores", [])
            self.logger.warning(f" Formato de estampillas con errores: {len(errores)} errores")
            self.logger.warning(f"Errores: {errores}")

    def _presentar_resultado(
        self,
        respuesta_validada: Any
    ) -> Dict[str, Any]:
        """
        Presenta el resultado final estructurado.

        Args:
            respuesta_validada: Respuesta validada y corregida

        Returns:
            Dict con estructura final de estampillas_generales
        """
        resultado_completo = presentar_resultado_estampillas_generales(respuesta_validada)
        return resultado_completo.get("estampillas_generales", {})

    def _manejar_error(self, e: Exception) -> Dict[str, Any]:
        """
        Maneja errores generales.

        Args:
            e: Excepcion capturada

        Returns:
            Dict con estructura de error
        """
        self.logger.error(f" Error liquidando estampillas generales: {e}")

        return {
            "procesamiento_exitoso": False,
            "error": str(e),
            "observaciones_generales": ["Error procesando estampillas generales"]
        }


async def validar_estampillas_generales(
    resultados_analisis: dict
) -> Optional[Dict[str, Any]]:
    """
    Wrapper function para mantener compatibilidad con main.py.

    Instancia ValidadorEstampillasGenerales y delega la validacion.
    Esta funcion actua como punto de entrada publico.

    Args:
        resultados_analisis: Diccionario con analisis de Gemini para todos los impuestos

    Returns:
        Dict con estructura para resultado_final["impuestos"]["estampillas_generales"]
        o None si no aplica
    """
    validador = ValidadorEstampillasGenerales()

    return await validador.validar(
        resultados_analisis=resultados_analisis
    )
