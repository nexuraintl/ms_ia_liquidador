"""
Modulo de validacion y liquidacion de IVA y ReteIVA.

Implementa validador siguiendo principios SOLID:
- SRP: Cada metodo tiene una responsabilidad unica
- OCP: Extensible mediante herencia
- DIP: Inyeccion de dependencias para facilitar testing

Flujos implementados:
- Normal: Liquidacion de IVA y ReteIVA para facturas del territorio nacional
- Facturacion extranjera: Liquidacion con reglas especiales para facturas del exterior
- Recurso extranjero: Estructura vacia sin liquidacion

Autor: Sistema Preliquidador
Version: 1.0 - Refactorizado con POO
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from Liquidador.liquidador_iva import LiquidadorIVA
from config import crear_resultado_recurso_extranjero_iva


def _asignar_concepto(
    conceptos: List[Dict[str, Any]], porcentaje: float, codigo_sugerido: str = ""
) -> Tuple[str, str, Optional[str]]:
    """Elige el concepto contable cuyo porcentaje coincide con el liquidado.

    Si varios conceptos comparten porcentaje, se usa el codigo sugerido por Gemini.

    Args:
        conceptos: Conceptos {codigo_concepto, descripcion_concepto, porcentaje} de Nexura.
        porcentaje: Porcentaje liquidado en puntos (19, 15, 100).
        codigo_sugerido: Codigo elegido por Gemini (puede ser vacio).

    Returns:
        Tuple con codigo, descripcion y aviso (None si se asigno un concepto).
    """
    if not conceptos:
        return "", "", "no se pudo obtener el catalogo de conceptos de la estructura contable"
    candidatos = [c for c in conceptos if round(c["porcentaje"]) == round(porcentaje)]
    elegido = next((c for c in candidatos if c["codigo_concepto"] == codigo_sugerido), None)
    if elegido is None and len(candidatos) == 1:
        elegido = candidatos[0]
    if elegido:
        return elegido["codigo_concepto"], elegido["descripcion_concepto"], None
    if not candidatos:
        return "", "", f"no hay concepto contable del {porcentaje:g}% para la estructura contable"
    codigos = ", ".join(c["codigo_concepto"] for c in candidatos)
    return "", "", f"hay varios conceptos del {porcentaje:g}% ({codigos}) y no se pudo elegir uno"


def agregar_conceptos_iva_reteiva(
    resultado: Dict[str, Any], conceptos: Dict[str, Any], codigo_sugerido: str = ""
) -> None:
    """Agrega codigo y descripcion del concepto de IVA y de ReteIVA al resultado (in place).

    Sin IVA o sin ReteIVA liquidados los campos quedan vacios sin aviso; si hay valor pero
    no hay concepto que encaje, quedan vacios y se agrega una observacion.

    Args:
        resultado: Dict final de iva_reteiva.
        conceptos: Resultado de `obtener_conceptos_iva_reteiva` ('iva' y 'reteiva').
        codigo_sugerido: Codigo de IVA elegido por Gemini.
    """
    for clave, valor, porcentaje, sugerido in (
        ("iva", resultado.get("valor_iva_identificado"), resultado.get("porcentaje_iva"),
         codigo_sugerido),
        ("reteiva", resultado.get("valor_reteiva"), resultado.get("tarifa_reteiva"), ""),
    ):
        codigo, descripcion = "", ""
        if (valor or 0) > 0 and (porcentaje or 0) > 0:
            codigo, descripcion, aviso = _asignar_concepto(
                conceptos.get(clave) or [], porcentaje * 100, sugerido or ""
            )
            if aviso:
                resultado.setdefault("observaciones", []).append(
                    f"Concepto {'IVA' if clave == 'iva' else 'ReteIVA'} sin asignar: {aviso}"
                )
        resultado[f"codigo_concepto_{clave}"] = codigo
        resultado[f"descripcion_concepto_{clave}"] = descripcion


class ValidadorIVAReteIVA:
    """
    Validador de IVA y ReteIVA siguiendo principios SOLID.

    Responsabilidad: Orquestar la validacion y liquidacion de IVA y ReteIVA
    segun el tipo de facturacion (nacional/extranjera/recurso extranjero).

    Attributes:
        liquidador_iva: Liquidador de IVA (inyectable)
        logger: Logger para registro de eventos
    """

    def __init__(
        self,
        liquidador_iva: Optional[LiquidadorIVA] = None
    ):
        """
        Inicializa el validador con inyeccion de dependencias.

        Args:
            liquidador_iva: Liquidador de IVA (opcional, se crea si no se provee)
        """
        self.liquidador_iva = liquidador_iva
        self.logger = logging.getLogger(__name__)

    async def validar(
        self,
        resultados_analisis: dict,
        aplica_iva: bool,
        es_recurso_extranjero: bool,
        es_facturacion_extranjera: bool,
        nit_administrativo: str,
        tipoMoneda: str,
        conceptos_iva: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Orquestador principal - valida y liquida IVA y ReteIVA.

        SRP: Solo coordina el flujo, delega la logica especifica a metodos privados.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            aplica_iva: Si aplica IVA/ReteIVA
            es_recurso_extranjero: Si es recurso de fuente extranjera
            es_facturacion_extranjera: Si es facturacion del exterior
            nit_administrativo: NIT de la entidad administrativa
            tipoMoneda: Tipo de moneda ("COP" o "USD")
            conceptos_iva: Conceptos contables de `obtener_conceptos_iva_reteiva`

        Returns:
            Dict con estructura de iva_reteiva o None si no aplica
        """
        # Verificar si debe procesar
        if not self._debe_procesar_iva_reteiva(resultados_analisis, aplica_iva):
            resultado = self._manejar_caso_especial(aplica_iva, es_recurso_extranjero)
        else:
            try:
                resultado = await self._procesar_liquidacion(
                    resultados_analisis,
                    es_facturacion_extranjera,
                    nit_administrativo,
                    tipoMoneda
                )
            except Exception as e:
                return self._manejar_error(e)

        if resultado:
            analisis = resultados_analisis.get("iva_reteiva")
            extraccion = analisis.get("extraccion_factura") if isinstance(analisis, dict) else None
            sugerido = (extraccion or {}).get("codigo_concepto_iva", "")
            agregar_conceptos_iva_reteiva(resultado, conceptos_iva or {}, sugerido)
        return resultado

    def _debe_procesar_iva_reteiva(
        self,
        resultados_analisis: dict,
        aplica_iva: bool
    ) -> bool:
        """
        SRP: Solo decide si hay datos para procesar IVA/ReteIVA.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            aplica_iva: Si aplica IVA/ReteIVA

        Returns:
            True si debe procesar, False en caso contrario
        """
        return "iva_reteiva" in resultados_analisis and aplica_iva

    def _manejar_caso_especial(
        self,
        aplica_iva: bool,
        es_recurso_extranjero: bool
    ) -> Optional[Dict[str, Any]]:
        """
        SRP: Solo maneja el caso especial de recurso extranjero.

        Args:
            aplica_iva: Si aplica IVA/ReteIVA
            es_recurso_extranjero: Si es recurso de fuente extranjera

        Returns:
            Dict con estructura de recurso extranjero o None
        """
        if aplica_iva and es_recurso_extranjero:
            self.logger.info(" IVA/ReteIVA: Aplicando estructura de recurso extranjero")
            resultado_completo = crear_resultado_recurso_extranjero_iva()

            resultado_iva_reteiva = resultado_completo.get("iva_reteiva", {})
            self.logger.info(" IVA/ReteIVA: No aplica (Recurso de fuente extranjera)")

            return resultado_iva_reteiva

        return None

    async def _procesar_liquidacion(
        self,
        resultados_analisis: dict,
        es_facturacion_extranjera: bool,
        nit_administrativo: str,
        tipoMoneda: str
    ) -> Dict[str, Any]:
        """
        SRP: Solo procesa la liquidacion de IVA y ReteIVA.

        Args:
            resultados_analisis: Diccionario con analisis de Gemini
            es_facturacion_extranjera: Si es facturacion del exterior
            nit_administrativo: NIT de la entidad administrativa
            tipoMoneda: Tipo de moneda

        Returns:
            Dict con resultado de liquidacion
        """
        # Lazy initialization si no se inyecto
        if self.liquidador_iva is None:
            self.liquidador_iva = LiquidadorIVA()

        # Preparar datos
        analisis_iva_gemini = resultados_analisis["iva_reteiva"]
        clasificacion_inicial = self._preparar_clasificacion_inicial(es_facturacion_extranjera)

        # Ejecutar liquidacion
        resultado_completo = self._ejecutar_liquidacion(
            analisis_iva_gemini,
            clasificacion_inicial,
            nit_administrativo,
            tipoMoneda
        )

        # Procesar y loguear resultado
        return self._procesar_resultado(resultado_completo)

    def _preparar_clasificacion_inicial(
        self,
        es_facturacion_extranjera: bool
    ) -> Dict[str, bool]:
        """
        SRP: Solo prepara la estructura de clasificacion inicial.

        Args:
            es_facturacion_extranjera: Si es facturacion del exterior

        Returns:
            Dict con clasificacion inicial
        """
        return {
            "es_facturacion_extranjera": es_facturacion_extranjera
        }

    def _ejecutar_liquidacion(
        self,
        analisis_iva_gemini: Any,
        clasificacion_inicial: Dict[str, bool],
        nit_administrativo: str,
        tipoMoneda: str
    ) -> Dict[str, Any]:
        """
        SRP: Solo ejecuta la liquidacion con el liquidador.

        Args:
            analisis_iva_gemini: Analisis de Gemini para IVA
            clasificacion_inicial: Clasificacion inicial
            nit_administrativo: NIT de la entidad administrativa
            tipoMoneda: Tipo de moneda

        Returns:
            Dict con resultado completo de liquidacion
        """
        return self.liquidador_iva.liquidar_iva_completo(
            analisis_gemini=analisis_iva_gemini,
            clasificacion_inicial=clasificacion_inicial,
            nit_administrativo=nit_administrativo,
            tipoMoneda=tipoMoneda
        )

    def _procesar_resultado(
        self,
        resultado_completo: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        SRP: Solo procesa y formatea el resultado final.

        Args:
            resultado_completo: Resultado completo del liquidador

        Returns:
            Dict con estructura final de iva_reteiva
        """
        resultado_iva_reteiva = resultado_completo.get("iva_reteiva", {})

        # Logging
        self._log_resultados(resultado_iva_reteiva)

        return resultado_iva_reteiva

    def _log_resultados(self, resultado_iva_reteiva: Dict[str, Any]) -> None:
        """
        SRP: Solo maneja el logging de resultados.

        Args:
            resultado_iva_reteiva: Resultado de IVA y ReteIVA
        """
        valor_iva = resultado_iva_reteiva.get("valor_iva_identificado", 0.0)
        valor_reteiva = resultado_iva_reteiva.get("valor_reteiva", 0.0)

        self.logger.info(f" IVA identificado: ${valor_iva:,.2f}")
        self.logger.info(f" ReteIVA liquidada: ${valor_reteiva:,.2f}")

    def _manejar_error(self, e: Exception) -> Dict[str, Any]:
        """
        SRP: Solo maneja errores generales.

        Args:
            e: Excepcion capturada

        Returns:
            Dict con estructura de error
        """
        self.logger.error(f" Error liquidando IVA/ReteIVA: {e}")

        return {
            "error": str(e),
            "aplica": False
        }


async def validar_iva_reteiva(
    resultados_analisis: dict,
    aplica_iva: bool,
    es_recurso_extranjero: bool,
    es_facturacion_extranjera: bool,
    nit_administrativo: str,
    tipoMoneda: str,
    conceptos_iva: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Wrapper function para mantener compatibilidad con main.py.

    Instancia ValidadorIVAReteIVA y delega la validacion.
    Esta funcion actua como punto de entrada publico.

    Args:
        resultados_analisis: Diccionario con analisis de Gemini para todos los impuestos
        aplica_iva: Si aplica IVA/ReteIVA
        es_recurso_extranjero: Si es recurso de fuente extranjera
        es_facturacion_extranjera: Si es facturacion del exterior
        nit_administrativo: NIT de la entidad administrativa
        tipoMoneda: Tipo de moneda ("COP" o "USD")
        conceptos_iva: Conceptos contables de `obtener_conceptos_iva_reteiva`

    Returns:
        Dict con estructura para resultado_final["impuestos"]["iva_reteiva"]
        o None si no aplica
    """
    validador = ValidadorIVAReteIVA()

    return await validador.validar(
        resultados_analisis=resultados_analisis,
        aplica_iva=aplica_iva,
        es_recurso_extranjero=es_recurso_extranjero,
        es_facturacion_extranjera=es_facturacion_extranjera,
        nit_administrativo=nit_administrativo,
        tipoMoneda=tipoMoneda,
        conceptos_iva=conceptos_iva
    )
