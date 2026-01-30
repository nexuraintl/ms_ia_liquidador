"""
LIQUIDADOR IVA Y RETEIVA v2.1 - ARQUITECTURA SOLID
===================================================

Módulo refactorizado siguiendo principios SOLID para validación y cálculo
de IVA y ReteIVA según normativa colombiana.

Arquitectura:
- ValidadorIVA: Validaciones específicas de IVA (SRP)
- CalculadorIVA: Cálculos de IVA (SRP)
- ValidadorReteIVA: Validaciones específicas de ReteIVA (SRP)
- CalculadorReteIVA: Cálculos de ReteIVA (SRP)
- LiquidadorIVA: Orquestador que coordina validadores y calculadores (DIP)

Responsabilidades separadas:
- Gemini: Solo extracción e identificación de datos
- Python: Todas las validaciones y cálculos manuales

Flujos diferenciados:
- Facturación Nacional: Validaciones completas (RUT, responsabilidad IVA, etc.)
- Facturación Extranjera: Validación simplificada (solo valor > 0) + cálculo manual IVA 19%

Autor: Miguel Angel Jaramillo Durango
Versión: 2.1.0
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

# Importar módulo Conversor TRM para conversión USD a COP
from Conversor import ConversorTRM
from Conversor.exceptions import TRMServiceError, TRMValidationError
from datetime import datetime

# Configuración de IVA
from config import (
    obtener_configuracion_iva,
    obtener_tarifa_reteiva,
    nit_aplica_iva_reteiva
)

logger = logging.getLogger(__name__)


# ===============================
# DATACLASSES - ESTRUCTURAS DE DATOS
# ===============================

@dataclass
class DatosExtraccionIVA:
    """Datos extraídos de la respuesta de Gemini"""
    # Extracción RUT
    rut_disponible: bool
    es_responsable_iva: Optional[bool]
    texto_evidencia: str

    # Extracción factura
    valor_iva: float
    porcentaje_iva: int
    valor_subtotal_sin_iva: float
    valor_total_con_iva: float
    concepto_facturado: str

    # Clasificación concepto
    categoria: str
    justificacion: str
    coincidencia_encontrada: str

    # Clasificación inicial (de primera llamada Gemini)
    es_facturacion_extranjera: bool


@dataclass
class ResultadoValidacionIVA:
    """Resultado de validaciones de IVA"""
    es_valido: bool
    estado: str
    observaciones: List[str]
    warnings: List[str]
    valor_iva_calculado: float
    porcentaje_iva_calculado: float


@dataclass
class ResultadoLiquidacionIVA:
    """Resultado final de la liquidación de IVA y ReteIVA"""
    aplica: bool
    valor_iva_identificado: float
    valor_reteiva: float
    porcentaje_iva: float
    tarifa_reteiva: float
    es_fuente_nacional: bool
    estado_liquidacion: str
    es_responsable_iva: Optional[bool]
    observaciones: List[str]
    calculo_exitoso: bool


# ===============================
# VALIDADOR IVA - SRP
# ===============================

class ValidadorIVA:
    """
    SRP: Solo responsable de validar condiciones de IVA.
    No realiza cálculos, solo valida reglas de negocio.
    """

    def __init__(self):
        """Inicializa el validador de IVA"""
        logger.info("ValidadorIVA inicializado")

    def validar_precondiciones(self, datos: DatosExtraccionIVA) -> ResultadoValidacionIVA:
        """
        Valida todas las precondiciones necesarias para aplicar IVA.

        Validaciones en orden:
        1. RUT disponible
        2. Responsabilidad IVA identificada
        3. Valor IVA (directo o calculado)
        4. Porcentaje IVA (si valor > 0)
        5. Categoría según responsabilidad
        6. Fuente extranjera (si aplica)

        Args:
            datos: Datos extraídos de Gemini

        Returns:
            ResultadoValidacionIVA: Resultado completo de validaciones
        """
        observaciones = []
        warnings = []

        # VALIDACIÓN 1: RUT disponible
        if not datos.rut_disponible:
            observaciones.append("RUT no disponible en los documentos")

        # VALIDACIÓN 2: Responsabilidad IVA identificada
        if datos.es_responsable_iva is None:
            return ResultadoValidacionIVA(
                es_valido=False,
                estado="preliquidacion_sin_finalizar",
                observaciones=["No se identificó responsabilidad de IVA en la documentación, por favor adjuntar el RUT"],
                warnings=[],
                valor_iva_calculado=0.0,
                porcentaje_iva_calculado=0.0
            )

        # VALIDACIÓN 3: Calcular/validar valor IVA
        valor_iva_final = self._validar_valor_iva(datos, observaciones)

        # VALIDACIÓN 4: Calcular/validar porcentaje IVA (solo si valor > 0)
        porcentaje_iva_final = 0.0
        if valor_iva_final > 0:
            porcentaje_iva_final = self._validar_porcentaje_iva(
                datos, valor_iva_final, observaciones
            )

        # VALIDACIÓN 5: Validar según responsabilidad IVA
        resultado_responsabilidad = self._validar_segun_responsabilidad(
            datos, valor_iva_final, observaciones, warnings
        )

        if not resultado_responsabilidad["es_valido"]:
            return ResultadoValidacionIVA(
                es_valido=False,
                estado=resultado_responsabilidad["estado"],
                observaciones=observaciones,
                warnings=warnings,
                valor_iva_calculado=valor_iva_final,
                porcentaje_iva_calculado=porcentaje_iva_final
            )

        # VALIDACIÓN 6: Fuente extranjera
        resultado_extranjera = self._validar_fuente_extranjera(
            datos, porcentaje_iva_final, observaciones
        )

        if not resultado_extranjera["es_valido"]:
            return ResultadoValidacionIVA(
                es_valido=False,
                estado="preliquidacion_sin_finalizar",
                observaciones=observaciones,
                warnings=warnings,
                valor_iva_calculado=valor_iva_final,
                porcentaje_iva_calculado=porcentaje_iva_final
            )

        # Todas las validaciones pasaron
        return ResultadoValidacionIVA(
            es_valido=True,
            estado="preliquidado",
            observaciones=observaciones,
            warnings=warnings,
            valor_iva_calculado=valor_iva_final,
            porcentaje_iva_calculado=porcentaje_iva_final
        )

    def _validar_valor_iva(self, datos: DatosExtraccionIVA,
                           observaciones: List[str]) -> float:
        """
        Valida y calcula el valor del IVA.

        Manera 1: Directamente de Gemini si valor_iva > 0
        Manera 2: Si valor_iva <= 0 y valor_subtotal > 0,
                  calcular: valor_total_con_iva - valor_subtotal_sin_iva

        Args:
            datos: Datos extraídos
            observaciones: Lista para agregar observaciones

        Returns:
            float: Valor del IVA calculado/validado
        """
        # Manera 1: Valor directo de Gemini
        if datos.valor_iva > 0:
            observaciones.append(f"Valor IVA identificado directamente: ${datos.valor_iva:,.2f}")
            return datos.valor_iva

        # Manera 2: Calcular desde subtotal y total
        if datos.valor_iva <= 0 and datos.valor_subtotal_sin_iva > 0:
            valor_iva_calculado = datos.valor_total_con_iva - datos.valor_subtotal_sin_iva
            if valor_iva_calculado > 0:
                observaciones.append(
                    f"Valor IVA calculado: ${datos.valor_total_con_iva:,.2f} - "
                    f"${datos.valor_subtotal_sin_iva:,.2f} = ${valor_iva_calculado:,.2f}"
                )
                return valor_iva_calculado

        # No hay IVA
        observaciones.append("Valor IVA = 0")
        return 0.0

    def _validar_porcentaje_iva(self, datos: DatosExtraccionIVA,
                                valor_iva: float,
                                observaciones: List[str]) -> float:
        """
        Valida y calcula el porcentaje del IVA.

        Manera directa: Si porcentaje_iva > 0 de Gemini
        Manera calculada: porcentaje = (valor_iva / valor_subtotal_sin_iva) * 100

        Args:
            datos: Datos extraídos
            valor_iva: Valor del IVA ya validado
            observaciones: Lista para agregar observaciones

        Returns:
            float: Porcentaje del IVA (como decimal, ej: 0.19 para 19%)
        """
        # Manera directa de Gemini
        if datos.porcentaje_iva > 0:
            porcentaje_decimal = datos.porcentaje_iva / 100.0
            observaciones.append(
                f"Porcentaje IVA identificado: {datos.porcentaje_iva}% ({porcentaje_decimal})"
            )
            return porcentaje_decimal

        # Manera calculada
        if valor_iva > 0 and datos.valor_subtotal_sin_iva > 0:
            porcentaje_calculado = (valor_iva / datos.valor_subtotal_sin_iva)
            porcentaje_entero = int(round(porcentaje_calculado * 100))
            observaciones.append(
                f"Porcentaje IVA calculado: ({valor_iva:,.2f} / "
                f"{datos.valor_subtotal_sin_iva:,.2f}) * 100 = {porcentaje_entero}% ({porcentaje_calculado:.4f})"
            )
            return porcentaje_calculado

        return 0.0

    def _validar_segun_responsabilidad(self, datos: DatosExtraccionIVA,
                                       valor_iva: float,
                                       observaciones: List[str],
                                       warnings: List[str]) -> Dict[str, Any]:
        """
        Valida según la responsabilidad de IVA del tercero.

        Casos:
        - es_responsable_iva == True y valor_iva > 0: Validar categoría "gravado"
        - es_responsable_iva == True y valor_iva == 0: Validar categoría exenta/excluida
        - es_responsable_iva == False: Validar valor_iva == 0

        Args:
            datos: Datos extraídos
            valor_iva: Valor del IVA validado
            observaciones: Lista para observaciones
            warnings: Lista para warnings

        Returns:
            Dict con es_valido y estado
        """
        # CASO 1: Responsable de IVA con valor IVA > 0
        if datos.es_responsable_iva and valor_iva > 0:
            if datos.categoria != "gravado":
                warnings.append(
                    f"ADVERTENCIA: Categoría '{datos.categoria}' esperada 'gravado' "
                    f"para operación con IVA. Proceso continúa."
                )
                observaciones.append(
                    f"Inconsistencia: Categoría '{datos.categoria}' con IVA aplicado"
                )
            else:
                observaciones.append("Categoría 'gravado' validada correctamente")

            return {"es_valido": True, "estado": "preliquidado"}

        # CASO 2: Responsable de IVA pero sin valor IVA
        if datos.es_responsable_iva and valor_iva == 0:
            categorias_validas = ["no_causa_iva", "exento", "excluido"]

            if datos.categoria == "no_clasificado":
                observaciones.append(
                    "Se identifico inconsistencia, el proveedor es responsable de IVA, la factura no muestra IVA y el concepto facturado no esta exento de iva, verificar soportes"
                )
                return {
                    "es_valido": False,
                    "estado": "preliquidacion_sin_finalizar"
                }

            if datos.categoria in categorias_validas:
                observaciones.append(
                    f"Categoría '{datos.categoria}' válida para IVA = 0"
                )
                observaciones.append(f"Justificación: {datos.justificacion}")
                if datos.coincidencia_encontrada:
                    observaciones.append(
                        f"Coincidencia: {datos.coincidencia_encontrada}"
                    )
                return {"es_valido": True, "estado": "no_aplica_impuesto"}

            # Categoría inesperada
            warnings.append(
                f"ADVERTENCIA: Categoría '{datos.categoria}' con IVA = 0"
            )
            return {"es_valido": True, "estado": "no_aplica_impuesto"}

        # CASO 3: NO responsable de IVA
        if not datos.es_responsable_iva:
            if valor_iva == 0:
                observaciones.append("No responsable de IVA y valor IVA = 0 (correcto)")
                return {"es_valido": True, "estado": "no_aplica_impuesto"}
            else:
                observaciones.append(
                    "El tercero reporta -No responsable de IVA- pero la factura incluye IVA. Verificar datos."
                )
                return {
                    "es_valido": False,
                    "estado": "preliquidacion_sin_finalizar"
                }

        return {"es_valido": True, "estado": "preliquidado"}

    def _validar_fuente_extranjera(self, datos: DatosExtraccionIVA,
                                   porcentaje_iva: float,
                                   observaciones: List[str]) -> Dict[str, Any]:
        """
        Valida casos de facturación extranjera.

        Si es_facturacion_extranjera == True:
        - Porcentaje IVA debe ser 19%
        - Si no, estado "Preliquidacion sin finalizar"
        - Si sí, observación positiva

        Args:
            datos: Datos extraídos
            porcentaje_iva: Porcentaje validado
            observaciones: Lista para observaciones

        Returns:
            Dict con es_valido
        """
        if not datos.es_facturacion_extranjera:
            return {"es_valido": True}

        # Es facturación extranjera
        porcentaje_entero = int(round(porcentaje_iva * 100))

        if porcentaje_entero != 19:
            observaciones.append(
                f"Inconsistencia: Ingreso de fuente extranjera con IVA del "
                f"{porcentaje_entero}% (esperado 19%)"
            )
            return {"es_valido": False}

        # Porcentaje correcto
        observaciones.append(
            "IVA teórico correcto (19%) para ingreso de fuente extranjera"
        )
        return {"es_valido": True}


# ===============================
# CALCULADOR IVA - SRP
# ===============================

class CalculadorIVA:
    """
    SRP: Solo responsable de realizar cálculos de IVA.
    No realiza validaciones, solo operaciones matemáticas.
    """

    def __init__(self):
        """Inicializa el calculador de IVA"""
        logger.info("CalculadorIVA inicializado")

    def calcular_iva_preciso(self, valor_base: float,
                            porcentaje: float) -> Decimal:
        """
        Calcula IVA con precisión usando Decimal.

        Args:
            valor_base: Valor base gravable
            porcentaje: Porcentaje de IVA (como decimal, ej: 0.19)

        Returns:
            Decimal: Valor del IVA calculado con precisión
        """
        valor_decimal = Decimal(str(valor_base))
        porcentaje_decimal = Decimal(str(porcentaje))

        valor_iva = valor_decimal * porcentaje_decimal

        return valor_iva.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ===============================
# VALIDADOR RETEIVA - SRP
# ===============================

class ValidadorReteIVA:
    """
    SRP: Solo responsable de validar condiciones para aplicar ReteIVA.
    """

    def __init__(self):
        """Inicializa el validador de ReteIVA"""
        logger.info("ValidadorReteIVA inicializado")

    def debe_aplicar_reteiva(self,
                            es_responsable_iva: bool,
                            valor_iva: float,
                            categoria: str,
                            estado_iva: str) -> Tuple[bool, str]:
        """
        Determina si se debe aplicar ReteIVA según condiciones.

        Condiciones para aplicar ReteIVA:
        - El tercero/proveedor es responsable de IVA
        - La operación está gravada con IVA (No exenta, No excluida)
        - El valor del IVA es mayor a cero (0)
        - Se aplicó IVA teórico (para fuente extranjera o nacional)

        Args:
            es_responsable_iva: Responsabilidad del tercero
            valor_iva: Valor del IVA
            categoria: Categoría del concepto
            estado_iva: Estado de la liquidación de IVA

        Returns:
            Tuple[bool, str]: (debe_aplicar, razon)
        """
        # Condición 1: Debe ser responsable de IVA
        if not es_responsable_iva:
            return False, "Tercero no es responsable de IVA"

        # Condición 2: Valor IVA debe ser mayor a 0
        if valor_iva <= 0:
            return False, "Valor de IVA es cero o negativo"

        # Condición 3: Operación debe estar gravada
        categorias_no_aplican = ["no_causa_iva", "exento", "excluido"]
        if categoria in categorias_no_aplican:
            return False, f"Operación con categoría '{categoria}' no aplica ReteIVA"

        # Condición 4: Estado de IVA debe ser válido
        if estado_iva in ["preliquidacion_sin_finalizar", "no_aplica_impuesto"]:
            return False, f"Estado IVA '{estado_iva}' no permite ReteIVA"

        # Todas las condiciones cumplidas
        return True, "Condiciones para ReteIVA cumplidas"


# ===============================
# CALCULADOR RETEIVA - SRP
# ===============================

class CalculadorReteIVA:
    """
    SRP: Solo responsable de calcular valores de ReteIVA.
    """

    def __init__(self):
        """Inicializa el calculador de ReteIVA"""
        logger.info("CalculadorReteIVA inicializado")

    def calcular_reteiva_preciso(self,
                                 valor_iva: float,
                                 es_fuente_nacional: bool) -> Dict[str, Any]:
        """
        Calcula ReteIVA con precisión según tipo de fuente.

        Tarifas:
        - Fuente nacional: 15% sobre el valor del IVA
        - Fuente extranjera: 100% sobre el valor del IVA

        Args:
            valor_iva: Valor del IVA identificado
            es_fuente_nacional: True si es nacional, False si extranjera

        Returns:
            Dict con resultado del cálculo
        """
        try:
            # Usar Decimal para cálculos precisos
            valor_iva_decimal = Decimal(str(valor_iva))

            # Obtener tarifa según fuente
            if es_fuente_nacional:
                tarifa_reteiva = 0.15
                porcentaje_texto = "15%"
            else:
                tarifa_reteiva = 1.0
                porcentaje_texto = "100%"

            tarifa_decimal = Decimal(str(tarifa_reteiva))

            # Calcular ReteIVA
            valor_reteiva_decimal = valor_iva_decimal * tarifa_decimal

            # Redondear a 2 decimales
            valor_reteiva_redondeado = valor_reteiva_decimal.quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

            resultado = {
                "valor_reteiva": float(valor_reteiva_redondeado),
                "tarifa_reteiva": tarifa_reteiva,
                "porcentaje_texto": porcentaje_texto,
                "formula": (
                    f"${valor_iva:,.2f} x {porcentaje_texto} = "
                    f"${float(valor_reteiva_redondeado):,.2f}"
                )
            }

            logger.info(f"Cálculo ReteIVA: {resultado['formula']}")
            return resultado

        except Exception as e:
            logger.error(f"Error calculando ReteIVA: {str(e)}")
            raise ValueError(f"Error en cálculo de ReteIVA: {str(e)}")


# ===============================
# LIQUIDADOR IVA - ORQUESTADOR (DIP)
# ===============================

class LiquidadorIVA:
    """
    Orquestador principal que coordina validadores y calculadores.

    DIP: Depende de abstracciones (ValidadorIVA, CalculadorIVA, etc.)
    SRP: Solo coordina el flujo, delega responsabilidades
    OCP: Extensible para nuevos tipos de validaciones/cálculos
    """

    VERSION = "2.1.0"

    def __init__(self,
                 validador_iva: Optional[ValidadorIVA] = None,
                 calculador_iva: Optional[CalculadorIVA] = None,
                 validador_reteiva: Optional[ValidadorReteIVA] = None,
                 calculador_reteiva: Optional[CalculadorReteIVA] = None):
        """
        Inicializa el liquidador con inyección de dependencias.

        Args:
            validador_iva: Validador de IVA (DIP)
            calculador_iva: Calculador de IVA (DIP)
            validador_reteiva: Validador de ReteIVA (DIP)
            calculador_reteiva: Calculador de ReteIVA (DIP)
        """
        # Inyección de dependencias con valores por defecto
        self.validador_iva = validador_iva or ValidadorIVA()
        self.calculador_iva = calculador_iva or CalculadorIVA()
        self.validador_reteiva = validador_reteiva or ValidadorReteIVA()
        self.calculador_reteiva = calculador_reteiva or CalculadorReteIVA()

        logger.info(f"LiquidadorIVA v{self.VERSION} inicializado con arquitectura SOLID")

    def _convertir_resultado_iva_usd_a_cop(self, resultado: Dict[str, Any], trm_valor: float) -> Dict[str, Any]:
        """
        Convierte todos los valores monetarios de IVA/ReteIVA de USD a COP.

        SRP: Solo responsable de convertir valores monetarios usando la TRM

        Args:
            resultado: Diccionario con resultado de IVA en USD
            trm_valor: Valor de la TRM para conversión

        Returns:
            Diccionario con todos los valores convertidos a COP
        """
        logger.info(f"Convirtiendo resultado IVA de USD a COP usando TRM: {trm_valor}")

        # Acceder a la estructura anidada
        iva_reteiva = resultado.get("iva_reteiva", {})

        # Convertir valores principales
        if "valor_iva_identificado" in iva_reteiva:
            iva_reteiva["valor_iva_identificado"] = iva_reteiva["valor_iva_identificado"] * trm_valor

        if "valor_subtotal_sin_iva" in iva_reteiva:
            iva_reteiva["valor_subtotal_sin_iva"] = iva_reteiva["valor_subtotal_sin_iva"] * trm_valor

        if "valor_total_con_iva" in iva_reteiva:
            iva_reteiva["valor_total_con_iva"] = iva_reteiva["valor_total_con_iva"] * trm_valor

        if "valor_reteiva" in iva_reteiva:
            iva_reteiva["valor_reteiva"] = iva_reteiva["valor_reteiva"] * trm_valor

        # Agregar mensaje de conversión
        if "observaciones" not in iva_reteiva:
            iva_reteiva["observaciones"] = []

        mensaje_conversion = f"Valores convertidos de USD a COP usando TRM: ${trm_valor:,.2f}"
        if mensaje_conversion not in iva_reteiva["observaciones"]:
            iva_reteiva["observaciones"].append(mensaje_conversion)

        logger.info(f"Conversión IVA completada. ReteIVA en COP: ${iva_reteiva.get('valor_reteiva', 0):,.2f}")

        # Actualizar estructura
        resultado["iva_reteiva"] = iva_reteiva
        return resultado

    def liquidar_iva_completo(self,
                             analisis_gemini: Dict[str, Any],
                             clasificacion_inicial: Dict[str, Any],
                             nit_administrativo: str,
                             tipoMoneda: str = "COP") -> Dict[str, Any]:
        """
        Realiza la liquidación completa de IVA y ReteIVA.

        Flujo para facturación NACIONAL:
        1. Extraer datos de respuesta Gemini
        2. Validar precondiciones completas de IVA (ValidadorIVA)
           - RUT disponible
           - Responsabilidad de IVA
           - Valor y porcentaje de IVA
           - Categoría según responsabilidad
        3. Validar condiciones completas ReteIVA (ValidadorReteIVA)
           - Es responsable de IVA
           - Valor IVA > 0
           - Categoría gravada
           - Estado IVA válido
        4. Si aplica ReteIVA, calcular con tarifa 15% (CalculadorReteIVA)
        5. Construir respuesta final
        6. Si tipoMoneda es USD, convertir todos los valores a COP usando TRM

        Flujo para facturación EXTRANJERA:
        1. Extraer datos de respuesta Gemini
        2. Validación simplificada IVA:
           - Solo verificar valor_subtotal_sin_iva > 0
           - Calcular IVA manualmente (19%)
        3. Validación simplificada ReteIVA:
           - Solo verificar valor_iva_calculado > 0
        4. Si aplica ReteIVA, calcular con tarifa 100% (CalculadorReteIVA)
        5. Construir respuesta final
        6. Si tipoMoneda es USD, convertir todos los valores a COP usando TRM

        Args:
            analisis_gemini: Respuesta del PROMPT_ANALISIS_IVA
            clasificacion_inicial: Clasificación de primera llamada (incluye es_facturacion_extranjera)
            nit_administrativo: NIT de la entidad
            tipoMoneda: Tipo de moneda ("COP" o "USD"), por defecto "COP"

        Returns:
            Dict con estructura de respuesta final (valores en COP)
        """
        logger.info(f"Iniciando liquidación IVA para NIT: {nit_administrativo}")

        try:
            # PASO 1: Extraer datos de Gemini
            datos_extraccion = self._extraer_datos_gemini(
                analisis_gemini, clasificacion_inicial
            )

            # PASO 2: Validar IVA - Bifurcación según tipo de facturación
            if datos_extraccion.es_facturacion_extranjera:
                # Flujo simplificado para facturación extranjera
                logger.info("Procesando facturación extranjera con flujo simplificado")
                resultado_validacion = self._validar_facturacion_extranjera(
                    datos_extraccion
                )
            else:
                # Flujo normal para facturación nacional
                logger.info("Procesando facturación nacional con validaciones completas")
                resultado_validacion = self.validador_iva.validar_precondiciones(
                    datos_extraccion
                )

            # Registrar warnings si existen
            for warning in resultado_validacion.warnings:
                logger.warning(warning)

            # Si validación falla, retornar resultado sin ReteIVA
            if not resultado_validacion.es_valido:
                resultado_no_aplica = self._crear_respuesta_no_aplica(
                    datos_extraccion,
                    resultado_validacion
                )
                # Convertir si es USD
                if tipoMoneda and tipoMoneda.upper() == "USD":
                    try:
                        with ConversorTRM(timeout=30) as conversor:
                            trm_valor = conversor.obtener_trm_valor()
                            resultado_no_aplica = self._convertir_resultado_iva_usd_a_cop(resultado_no_aplica, trm_valor)
                    except Exception as e:
                        logger.warning(f"No se pudo convertir resultado no_aplica: {e}")
                return resultado_no_aplica

            # PASO 3: Determinar fuente de ingreso
            es_fuente_nacional = not datos_extraccion.es_facturacion_extranjera

            # PASO 4: Validar si aplica ReteIVA - Bifurcación según tipo de facturación
            if datos_extraccion.es_facturacion_extranjera:
                # Facturación extranjera: solo validar valor IVA > 0
                if resultado_validacion.valor_iva_calculado <= 0:
                    razon_reteiva = "Valor de IVA es cero o negativo"
                    logger.info(f"ReteIVA no aplica (extranjera): {razon_reteiva}")
                    resultado_sin_reteiva = self._crear_respuesta_sin_reteiva(
                        datos_extraccion,
                        resultado_validacion,
                        es_fuente_nacional,
                        razon_reteiva
                    )
                    # Convertir si es USD
                    if tipoMoneda and tipoMoneda.upper() == "USD":
                        try:
                            with ConversorTRM(timeout=30) as conversor:
                                trm_valor = conversor.obtener_trm_valor()
                                resultado_sin_reteiva = self._convertir_resultado_iva_usd_a_cop(resultado_sin_reteiva, trm_valor)
                        except Exception as e:
                            logger.warning(f"No se pudo convertir resultado sin_reteiva: {e}")
                    return resultado_sin_reteiva
                # Si valor IVA > 0, continuar al cálculo (debe_aplicar = True implícito)
                logger.info("ReteIVA aplica para facturación extranjera (IVA > 0)")
            else:
                # Facturación nacional: validaciones completas
                debe_aplicar, razon_reteiva = self.validador_reteiva.debe_aplicar_reteiva(
                    es_responsable_iva=datos_extraccion.es_responsable_iva,
                    valor_iva=resultado_validacion.valor_iva_calculado,
                    categoria=datos_extraccion.categoria,
                    estado_iva=resultado_validacion.estado
                )

                if not debe_aplicar:
                    logger.info(f"ReteIVA no aplica (nacional): {razon_reteiva}")
                    resultado_sin_reteiva_nacional = self._crear_respuesta_sin_reteiva(
                        datos_extraccion,
                        resultado_validacion,
                        es_fuente_nacional,
                        razon_reteiva
                    )
                    # Convertir si es USD
                    if tipoMoneda and tipoMoneda.upper() == "USD":
                        try:
                            with ConversorTRM(timeout=30) as conversor:
                                trm_valor = conversor.obtener_trm_valor()
                                resultado_sin_reteiva_nacional = self._convertir_resultado_iva_usd_a_cop(resultado_sin_reteiva_nacional, trm_valor)
                        except Exception as e:
                            logger.warning(f"No se pudo convertir resultado sin_reteiva (nacional): {e}")
                    return resultado_sin_reteiva_nacional

            # PASO 5: Calcular ReteIVA
            resultado_reteiva = self.calculador_reteiva.calcular_reteiva_preciso(
                valor_iva=resultado_validacion.valor_iva_calculado,
                es_fuente_nacional=es_fuente_nacional
            )

            # PASO 6: Construir respuesta exitosa
            resultado_final = self._crear_respuesta_exitosa(
                datos_extraccion,
                resultado_validacion,
                resultado_reteiva,
                es_fuente_nacional
            )

            # PASO 7: Convertir de USD a COP si es necesario
            if tipoMoneda and tipoMoneda.upper() == "USD":
                logger.info("Moneda detectada: USD - Iniciando conversión a COP usando TRM...")
                try:
                    with ConversorTRM(timeout=30) as conversor:
                        trm_valor = conversor.obtener_trm_valor()
                        logger.info(f"TRM obtenida exitosamente: ${trm_valor:,.2f} COP/USD")
                        resultado_final = self._convertir_resultado_iva_usd_a_cop(resultado_final, trm_valor)
                except (TRMServiceError, TRMValidationError) as e:
                    logger.error(f"Error al obtener TRM para conversión IVA: {e}")
                    # Agregar advertencia pero no detener el proceso
                    iva_reteiva = resultado_final.get("iva_reteiva", {})
                    if "observaciones" not in iva_reteiva:
                        iva_reteiva["observaciones"] = []
                    iva_reteiva["observaciones"].append(
                        f"ADVERTENCIA: No se pudo convertir de USD a COP (Error TRM: {str(e)}). Valores mostrados en USD."
                    )
                    resultado_final["iva_reteiva"] = iva_reteiva
                except Exception as e:
                    logger.error(f"Error inesperado en conversión USD a COP (IVA): {e}")
                    iva_reteiva = resultado_final.get("iva_reteiva", {})
                    if "observaciones" not in iva_reteiva:
                        iva_reteiva["observaciones"] = []
                    iva_reteiva["observaciones"].append(
                        f"ADVERTENCIA: Error inesperado en conversión de moneda. Valores mostrados en USD."
                    )
                    resultado_final["iva_reteiva"] = iva_reteiva
            else:
                logger.info(f"Moneda: {tipoMoneda or 'COP'} - No se requiere conversión IVA")

            return resultado_final

        except Exception as e:
            error_msg = f"Error en liquidación de IVA: {str(e)}"
            logger.error(error_msg)
            return self._crear_respuesta_error(error_msg)

    def _extraer_datos_gemini(self,
                             analisis_gemini: Dict[str, Any],
                             clasificacion_inicial: Dict[str, Any]) -> DatosExtraccionIVA:
        """
        Extrae datos de la respuesta de Gemini al formato DatosExtraccionIVA.

        Args:
            analisis_gemini: Respuesta PROMPT_ANALISIS_IVA
            clasificacion_inicial: Clasificación inicial

        Returns:
            DatosExtraccionIVA: Datos estructurados
        """
        # Extraer secciones
        extraccion_rut = analisis_gemini.get("extraccion_rut", {})
        extraccion_factura = analisis_gemini.get("extraccion_factura", {})
        clasificacion_concepto = analisis_gemini.get("clasificacion_concepto", {})
        validaciones = analisis_gemini.get("validaciones", {})

        # Extraer si es facturación extranjera de la clasificación inicial
        es_facturacion_extranjera = clasificacion_inicial.get(
            "es_facturacion_extranjera", False
        )

        datos = DatosExtraccionIVA(
            # RUT
            rut_disponible=validaciones.get("rut_disponible", False),
            es_responsable_iva=extraccion_rut.get("es_responsable_iva"),
            texto_evidencia=extraccion_rut.get("texto_evidencia", ""),

            # Factura
            valor_iva=float(extraccion_factura.get("valor_iva", 0.0)),
            porcentaje_iva=int(extraccion_factura.get("porcentaje_iva", 0)),
            valor_subtotal_sin_iva=float(extraccion_factura.get("valor_subtotal_sin_iva", 0.0)),
            valor_total_con_iva=float(extraccion_factura.get("valor_total_con_iva", 0.0)),
            concepto_facturado=extraccion_factura.get("concepto_facturado", ""),

            # Clasificación
            categoria=clasificacion_concepto.get("categoria", "no_clasificado"),
            justificacion=clasificacion_concepto.get("justificacion", ""),
            coincidencia_encontrada=clasificacion_concepto.get("coincidencia_encontrada", ""),

            # Clasificación inicial
            es_facturacion_extranjera=es_facturacion_extranjera
        )

        logger.info(f"Datos extraídos - IVA: ${datos.valor_iva:,.2f}, Responsable: {datos.es_responsable_iva}")
        return datos

    def _validar_facturacion_extranjera(self,
                                        datos: DatosExtraccionIVA) -> ResultadoValidacionIVA:
        """
        Valida y calcula IVA para facturación extranjera.

        Flujo simplificado:
        1. Solo valida que valor_subtotal_sin_iva > 0
        2. Si no hay valor, retorna estado "sin finalizar"
        3. Si hay valor, aplica 19% manual para calcular IVA

        Args:
            datos: Datos extraídos de Gemini

        Returns:
            ResultadoValidacionIVA: Resultado con IVA calculado manualmente
        """
        observaciones = []
        warnings = []

        # Validación única: valor_subtotal_sin_iva > 0
        if datos.valor_subtotal_sin_iva <= 0:
            observaciones.append("No se pudo identificar el valor de la factura")
            return ResultadoValidacionIVA(
                es_valido=False,
                estado="preliquidacion_sin_finalizar",
                observaciones=observaciones,
                warnings=warnings,
                valor_iva_calculado=0.0,
                porcentaje_iva_calculado=0.0
            )

        # Cálculo manual del IVA (19%)
        porcentaje_iva = 0.19
        valor_iva_calculado = datos.valor_subtotal_sin_iva * porcentaje_iva

        observaciones.append(
            f"Facturación extranjera identificada"
        )
        observaciones.append(
            f"Valor subtotal sin IVA: ${datos.valor_subtotal_sin_iva:,.2f}"
        )
        observaciones.append(
            f"IVA calculado manualmente (19%): ${datos.valor_subtotal_sin_iva:,.2f} x 19% = ${valor_iva_calculado:,.2f}"
        )

        logger.info(
            f"Facturación extranjera: IVA calculado ${valor_iva_calculado:,.2f} "
            f"sobre base ${datos.valor_subtotal_sin_iva:,.2f}"
        )

        return ResultadoValidacionIVA(
            es_valido=True,
            estado="preliquidado",
            observaciones=observaciones,
            warnings=warnings,
            valor_iva_calculado=valor_iva_calculado,
            porcentaje_iva_calculado=porcentaje_iva
        )

    def _crear_respuesta_exitosa(self,
                                datos: DatosExtraccionIVA,
                                validacion: ResultadoValidacionIVA,
                                reteiva: Dict[str, Any],
                                es_fuente_nacional: bool) -> Dict[str, Any]:
        """
        Crea la respuesta exitosa final.

        Args:
            datos: Datos de extracción
            validacion: Resultado de validación IVA
            reteiva: Resultado de cálculo ReteIVA
            es_fuente_nacional: Tipo de fuente

        Returns:
            Dict con estructura de respuesta final
        """
        return {
            "iva_reteiva": {
                "aplica": True,
                "valor_iva_identificado": validacion.valor_iva_calculado,
                "valor_subtotal_sin_iva": datos.valor_subtotal_sin_iva,
                "valor_reteiva": reteiva["valor_reteiva"],
                "porcentaje_iva": validacion.porcentaje_iva_calculado,
                "tarifa_reteiva": reteiva["tarifa_reteiva"],
                "es_fuente_nacional": es_fuente_nacional,
                "estado_liquidacion": validacion.estado,
                "es_responsable_iva": datos.es_responsable_iva,
                "observaciones": validacion.observaciones + [
                    f"Cálculo ReteIVA: {reteiva['formula']}"
                ],
                "calculo_exitoso": True
            }
        }

    def _crear_respuesta_sin_reteiva(self,
                                     datos: DatosExtraccionIVA,
                                     validacion: ResultadoValidacionIVA,
                                     es_fuente_nacional: bool,
                                     razon: str) -> Dict[str, Any]:
        """
        Crea respuesta cuando hay IVA pero no aplica ReteIVA.
        """
        return {
            "iva_reteiva": {
                "aplica": False,
                "valor_iva_identificado": validacion.valor_iva_calculado,
                "valor_subtotal_sin_iva": datos.valor_subtotal_sin_iva,
                "valor_reteiva": 0.0,
                "porcentaje_iva": validacion.porcentaje_iva_calculado,
                "tarifa_reteiva": 0.0,
                "es_fuente_nacional": es_fuente_nacional,
                "estado_liquidacion": validacion.estado,
                "es_responsable_iva": datos.es_responsable_iva,
                "observaciones": validacion.observaciones + [
                    f"ReteIVA no aplica: {razon}"
                ],
                "calculo_exitoso": True
            }
        }

    def _crear_respuesta_no_aplica(self,
                                   datos: DatosExtraccionIVA,
                                   validacion: ResultadoValidacionIVA) -> Dict[str, Any]:
        """
        Crea respuesta cuando no aplica IVA ni ReteIVA.
        """
        return {
            "iva_reteiva": {
                "aplica": False,
                "valor_iva_identificado": validacion.valor_iva_calculado,
                "valor_subtotal_sin_iva": datos.valor_subtotal_sin_iva,
                "valor_reteiva": 0.0,
                "porcentaje_iva": validacion.porcentaje_iva_calculado,
                "tarifa_reteiva": 0.0,
                "es_fuente_nacional": not datos.es_facturacion_extranjera,
                "estado_liquidacion": validacion.estado,
                "es_responsable_iva": datos.es_responsable_iva,
                "observaciones": validacion.observaciones,
                "calculo_exitoso": False if validacion.estado == "preliquidacion_sin_finalizar" else True
            }
        }

    def _crear_respuesta_error(self, mensaje_error: str) -> Dict[str, Any]:
        """
        Crea respuesta de error.
        """
        return {
            "iva_reteiva": {
                "aplica": False,
                "valor_iva_identificado": 0.0,
                "valor_subtotal_sin_iva": 0.0,
                "valor_reteiva": 0.0,
                "porcentaje_iva": 0.0,
                "tarifa_reteiva": 0.0,
                "es_fuente_nacional": True,
                "estado_liquidacion": "preliquidacion_sin_finalizar",
                "es_responsable_iva": None,
                "observaciones": [mensaje_error],
                "calculo_exitoso": False
            }
        }


# ===============================
# EJEMPLO DE USO
# ===============================

if __name__ == "__main__":
    """
    Ejemplo de uso del LiquidadorIVA v2.0 con arquitectura SOLID.
    """
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(message)s'
    )

    # Simular respuesta de Gemini
    analisis_gemini_ejemplo = {
        "extraccion_rut": {
            "es_responsable_iva": True,
            "texto_evidencia": "RESPONSABILIDADES: 48 - Responsable de IVA"
        },
        "extraccion_factura": {
            "valor_iva": 26023887.7,
            "porcentaje_iva": 19,
            "valor_subtotal_sin_iva": 136967304.0,
            "valor_total_con_iva": 162991191.7,
            "concepto_facturado": "Servicios de consultoría tecnológica"
        },
        "clasificacion_concepto": {
            "categoria": "gravado",
            "justificacion": "La factura tiene IVA aplicado",
            "coincidencia_encontrada": ""
        },
        "validaciones": {
            "rut_disponible": True
        }
    }

    clasificacion_inicial_ejemplo = {
        "es_facturacion_extranjera": False
    }

    # Crear liquidador con inyección de dependencias
    liquidador = LiquidadorIVA()

    # Realizar liquidación
    resultado = liquidador.liquidar_iva_completo(
        analisis_gemini=analisis_gemini_ejemplo,
        clasificacion_inicial=clasificacion_inicial_ejemplo,
        nit_administrativo="800.178.148-8"
    )

    # Mostrar resultado
    print("\n" + "="*60)
    print("RESULTADO LIQUIDACIÓN IVA Y RETEIVA")
    print("="*60)
    print(f"Aplica: {resultado['iva_reteiva']['aplica']}")
    print(f"Valor Subtotal sin IVA: ${resultado['iva_reteiva']['valor_subtotal_sin_iva']:,.2f}")
    print(f"Valor IVA: ${resultado['iva_reteiva']['valor_iva_identificado']:,.2f}")
    print(f"Valor ReteIVA: ${resultado['iva_reteiva']['valor_reteiva']:,.2f}")
    print(f"Porcentaje IVA: {resultado['iva_reteiva']['porcentaje_iva']:.2%}")
    print(f"Tarifa ReteIVA: {resultado['iva_reteiva']['tarifa_reteiva']:.2%}")
    print(f"Estado: {resultado['iva_reteiva']['estado_liquidacion']}")
    print(f"\nObservaciones:")
    for obs in resultado['iva_reteiva']['observaciones']:
        print(f"  - {obs}")
    print("="*60)
