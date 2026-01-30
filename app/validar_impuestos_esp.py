"""
Modulo de validacion y liquidacion de impuestos especiales.

Implementa validador siguiendo principios SOLID:
- SRP: Cada metodo tiene una responsabilidad unica
- OCP: Extensible mediante herencia
- DIP: Inyeccion de dependencias para facilitar testing

Flujos implementados:
- Estampilla Pro Universidad Nacional: Calculo segun tabla UVT
- Contribucion Obra Publica 5%: Tarifa fija para contratos

Autor: Sistema Preliquidador
Version: 1.0 - Refactorizado con POO
"""

import logging
from typing import Dict, Any, Optional

from Liquidador.liquidador_estampilla import LiquidadorEstampilla


class ValidadorImpuestosEspeciales:
    """
    Validador de impuestos especiales siguiendo principios SOLID.

    Responsabilidad: Orquestar la validacion y liquidacion de impuestos
    especiales (Estampilla Universidad + Obra Publica).

    Attributes:
        liquidador_estampilla: Liquidador de estampillas (inyectable)
        logger: Logger para registro de eventos
    """

    def __init__(
        self,
        liquidador_estampilla: Optional[LiquidadorEstampilla] = None
    ):
        """
        Inicializa el validador con inyeccion de dependencias.

        Args:
            liquidador_estampilla: Liquidador de estampillas (opcional, se crea si no se provee)
        """
        self.liquidador_estampilla = liquidador_estampilla
        self.logger = logging.getLogger(__name__)

    async def validar(
        self,
        resultados_analisis: dict,
        aplica_estampilla: bool,
        aplica_obra_publica: bool,
        codigo_del_negocio: int,
        nombre_negocio: str
    ) -> Optional[Dict[str, Any]]:
        """
        Orquestador principal - valida y liquida impuestos especiales.

        SRP: Solo coordina el flujo, delega la logica especifica a metodos privados.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            aplica_estampilla: Si aplica Estampilla Universidad
            aplica_obra_publica: Si aplica Obra Publica
            codigo_del_negocio: Codigo del negocio
            nombre_negocio: Nombre del negocio

        Returns:
            Dict con resultados de liquidacion o None si no aplica
        """
        # Verificar si debe procesar
        if not self._debe_procesar_impuestos_especiales(
            resultados_analisis,
            aplica_estampilla,
            aplica_obra_publica
        ):
            return None

        # Procesar liquidacion
        try:
            return await self._procesar_liquidacion(
                resultados_analisis,
                aplica_estampilla,
                aplica_obra_publica,
                codigo_del_negocio,
                nombre_negocio
            )
        except Exception as e:
            return self._manejar_error(e, aplica_estampilla, aplica_obra_publica)

    def _debe_procesar_impuestos_especiales(
        self,
        resultados_analisis: dict,
        aplica_estampilla: bool,
        aplica_obra_publica: bool
    ) -> bool:
        """
        SRP: Solo decide si hay datos para procesar impuestos especiales.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            aplica_estampilla: Si aplica Estampilla Universidad
            aplica_obra_publica: Si aplica Obra Publica

        Returns:
            True si debe procesar, False en caso contrario
        """
        return (
            "impuestos_especiales" in resultados_analisis
            and (aplica_estampilla or aplica_obra_publica)
        )

    async def _procesar_liquidacion(
        self,
        resultados_analisis: dict,
        aplica_estampilla: bool,
        aplica_obra_publica: bool,
        codigo_del_negocio: int,
        nombre_negocio: str
    ) -> Dict[str, Any]:
        """
        SRP: Solo procesa la liquidacion de impuestos especiales.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            aplica_estampilla: Si aplica Estampilla Universidad
            aplica_obra_publica: Si aplica Obra Publica
            codigo_del_negocio: Codigo del negocio
            nombre_negocio: Nombre del negocio

        Returns:
            Dict con resultados de liquidacion
        """
        # Lazy initialization si no se inyecto
        if self.liquidador_estampilla is None:
            self.liquidador_estampilla = LiquidadorEstampilla()

        # Ejecutar liquidacion
        analisis_especiales = resultados_analisis["impuestos_especiales"]
        resultado_completo = self.liquidador_estampilla.liquidar_integrado(
            analisis_especiales,
            codigo_del_negocio,
            nombre_negocio
        )

        # Procesar y loguear resultados
        return self._procesar_resultados(
            resultado_completo,
            aplica_estampilla,
            aplica_obra_publica
        )

    def _procesar_resultados(
        self,
        resultado_completo: Dict[str, Any],
        aplica_estampilla: bool,
        aplica_obra_publica: bool
    ) -> Dict[str, Any]:
        """
        SRP: Solo procesa y formatea los resultados finales.

        Args:
            resultado_completo: Resultado completo de liquidador
            aplica_estampilla: Si aplica Estampilla Universidad
            aplica_obra_publica: Si aplica Obra Publica

        Returns:
            Dict con resultados filtrados y formateados
        """
        resultado_final = {}

        # Procesar Estampilla Universidad
        if aplica_estampilla and "estampilla_universidad" in resultado_completo:
            resultado_final["estampilla_universidad"] = resultado_completo["estampilla_universidad"]
            self._log_estampilla(resultado_completo["estampilla_universidad"])

        # Procesar Obra Publica
        if aplica_obra_publica and "contribucion_obra_publica" in resultado_completo:
            resultado_final["contribucion_obra_publica"] = resultado_completo["contribucion_obra_publica"]
            self._log_obra_publica(resultado_completo["contribucion_obra_publica"])

        return resultado_final

    def _log_estampilla(self, resultado_estampilla: Dict[str, Any]) -> None:
        """
        SRP: Solo maneja el logging de Estampilla Universidad.

        Args:
            resultado_estampilla: Resultado de liquidacion de estampilla
        """
        valor = resultado_estampilla.get('valor_estampilla', 0)
        self.logger.info(f" Estampilla liquidada: ${valor:,.2f}")

    def _log_obra_publica(self, resultado_obra_publica: Dict[str, Any]) -> None:
        """
        SRP: Solo maneja el logging de Obra Publica.

        Args:
            resultado_obra_publica: Resultado de liquidacion de obra publica
        """
        valor = resultado_obra_publica.get('valor_contribucion', 0)
        self.logger.info(f" Obra pública liquidada: ${valor:,.2f}")

    def _manejar_error(
        self,
        e: Exception,
        aplica_estampilla: bool,
        aplica_obra_publica: bool
    ) -> Dict[str, Any]:
        """
        SRP: Solo maneja errores generales.

        Args:
            e: Excepcion capturada
            aplica_estampilla: Si aplica Estampilla Universidad
            aplica_obra_publica: Si aplica Obra Publica

        Returns:
            Dict con estructura de error para cada impuesto aplicable
        """
        self.logger.error(f" Error liquidando impuestos especiales: {e}")

        resultado_error = {}

        if aplica_estampilla:
            resultado_error["estampilla_universidad"] = {
                "error": str(e),
                "aplica": False
            }

        if aplica_obra_publica:
            resultado_error["contribucion_obra_publica"] = {
                "error": str(e),
                "aplica": False
            }

        return resultado_error


async def validar_impuestos_especiales(
    resultados_analisis: dict,
    aplica_estampilla: bool,
    aplica_obra_publica: bool,
    codigo_del_negocio: int,
    nombre_negocio: str
) -> Optional[Dict[str, Any]]:
    """
    Wrapper function para mantener compatibilidad con main.py.

    Instancia ValidadorImpuestosEspeciales y delega la validacion.
    Esta funcion actua como punto de entrada publico.

    Args:
        resultados_analisis: Diccionario con analisis de Gemini para todos los impuestos
        aplica_estampilla: Si aplica Estampilla Pro Universidad Nacional
        aplica_obra_publica: Si aplica Contribucion Obra Publica 5%
        codigo_del_negocio: Codigo del negocio
        nombre_negocio: Nombre del negocio

    Returns:
        Dict con estructura para resultado_final["impuestos"]
        o None si no aplica ningun impuesto especial
    """
    validador = ValidadorImpuestosEspeciales()

    return await validador.validar(
        resultados_analisis=resultados_analisis,
        aplica_estampilla=aplica_estampilla,
        aplica_obra_publica=aplica_obra_publica,
        codigo_del_negocio=codigo_del_negocio,
        nombre_negocio=nombre_negocio
    )
