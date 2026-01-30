"""
LIQUIDADOR DE CONSORCIOS - ARQUITECTURA SOLID
============================================

Módulo especializado para liquidación de retención en la fuente para consorcios,
siguiendo los principios SOLID y separando la lógica de negocio de la extracción de datos.

PRINCIPIOS APLICADOS:
- SRP: Responsabilidad única - solo liquidación de consorcios
- OCP: Abierto para extensión - fácil agregar nuevos tipos de validaciones
- LSP: Sustituible - implementa interfaces comunes
- ISP: Interfaces segregadas - funciones específicas por responsabilidad
- DIP: Inversión de dependencias - depende de abstracciones

Autor: Sistema Preliquidador v3.1.1
Arquitectura: SOLID + Clean Architecture + Validaciones Manuales
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_HALF_UP

# Configuración de logging
logger = logging.getLogger(__name__)


# ===============================
# DATACLASSES PARA ESTRUCTURAS
# ===============================

@dataclass
class ConceptoLiquidado:
    """
    Estructura para concepto liquidado individualmente por consorciado.

    Detalla el resultado de liquidación de un concepto específico para un consorciado.
    """
    nombre_concepto: str
    tarifa_retencion: float
    base_gravable_individual: Decimal
    base_minima_normativa: Decimal
    aplica_concepto: bool
    valor_retencion_concepto: Decimal
    codigo_concepto: Optional[str] = None
    razon_no_aplicacion: Optional[str] = None

@dataclass
class ConsorciadoLiquidado:
    """
    Estructura para consorciado liquidado.

    Encapsula toda la información de liquidación de un consorciado individual.
    """
    nombre: str
    nit: str
    porcentaje_participacion: float
    aplica_retencion: bool
    valor_retencion: Decimal  # Total de todos los conceptos
    valor_base: Decimal
    conceptos_liquidados: List[ConceptoLiquidado]  # NUEVO: Detalle por concepto
    razon_no_aplicacion: Optional[str] = None
    naturaleza_tributaria: Optional[Dict[str, Any]] = None


@dataclass
class ResultadoLiquidacionConsorcio:
    """
    Estructura para resultado completo de liquidación de consorcio.

    Encapsula el resultado final con todos los consorciados liquidados.
    """
    es_consorcio: bool
    nombre_consorcio: str
    consorciados: List[ConsorciadoLiquidado]
    retencion_total: Decimal
    valor_factura_sin_iva: Decimal
    conceptos_aplicados: List[Dict[str, Any]]
    estado: str
    observaciones: List[str]
    procesamiento_exitoso: bool


# ===============================
# INTERFACES Y ABSTRACCIONES
# ===============================

class IValidadorNaturaleza(ABC):
    """
    Interface para validadores de naturaleza tributaria.

    ISP: Interface específica para validación de naturaleza
    """

    @abstractmethod
    def validar_naturaleza_consorcio(self, consorciado: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """
        Valida la naturaleza tributaria de un consorciado.

        Args:
            consorciado: Datos del consorciado

        Returns:
            Tuple[bool, str, Optional[str]]: (aplica_retencion, razon_no_aplicacion, campo_faltante)
        """
        pass


class IValidadorConceptos(ABC):
    """
    Interface para validadores de conceptos.

    ISP: Interface específica para validación de conceptos
    """

    @abstractmethod
    def validar_concepto(self, concepto: str, diccionario_conceptos: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Valida si un concepto existe en el diccionario.

        Args:
            concepto: Nombre del concepto a validar
            diccionario_conceptos: Diccionario de conceptos válidos

        Returns:
            Tuple[bool, Dict]: (es_valido, datos_concepto)
        """
        pass


class ICalculadorRetencion(ABC):
    """
    Interface para calculadores de retención.

    ISP: Interface específica para cálculos
    """

    @abstractmethod
    def calcular_retencion_general(self, datos_liquidacion: Dict[str, Any]) -> Decimal:
        """
        Calcula la retención general del consorcio procesando TODOS los conceptos.

        Args:
            datos_liquidacion: Datos para el cálculo (debe incluir valor_total y conceptos_identificados)

        Returns:
            Decimal: Valor de retención general total (suma de todas las retenciones por concepto)
        """
        pass

    @abstractmethod
    def calcular_retencion_individual(self,
                                    valor_factura_sin_iva: Decimal,
                                    porcentaje_participacion: float,
                                    conceptos_validados: List[Dict[str, Any]],
                                    diccionario_conceptos: Dict[str, Any]) -> Tuple[Decimal, List[ConceptoLiquidado]]:
        """
        Calcula la retención individual de un consorciado validando base gravable por concepto.

        Args:
            valor_factura_sin_iva: Valor total de la factura sin IVA
            porcentaje_participacion: Porcentaje de participación del consorciado (0-100)
            conceptos_validados: Lista de conceptos ya validados con sus datos
            diccionario_conceptos: Diccionario de conceptos de config.py con bases mínimas

        Returns:
            Tuple[Decimal, List[ConceptoLiquidado]]: (valor_retencion_total, lista_conceptos_liquidados)
        """
        pass


# ===============================
# IMPLEMENTACIONES CONCRETAS
# ===============================

class ValidadorNaturalezaTributaria(IValidadorNaturaleza):
    """
    Validador concreto para naturaleza tributaria de consorciados.

    SRP: Solo responsable de validar naturaleza tributaria
    """

    def validar_naturaleza_consorcio(self, consorciado: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """
        Valida la naturaleza tributaria según las reglas de negocio.

        Reglas:
        - No responsable de IVA: No aplica retención
        - Autorretenedor: No aplica retención
        - Régimen simple: No aplica retención
        - Datos null: Preliquidación sin finalizar

        Returns:
            Tuple[bool, str, Optional[str]]: (aplica_retencion, razon_no_aplicacion, campo_faltante)
        """
        try:
            naturaleza = consorciado.get('naturaleza_tributaria', {})

            # Validar datos null - datos incompletos
            if self._tiene_datos_null(naturaleza):
                campo_faltante = self._obtener_campo_faltante(naturaleza)
                return False, "Naturaleza tributaria incompleta", campo_faltante

            # Validar condiciones de no aplicación
            es_autorretenedor = naturaleza.get('es_autorretenedor', False)
            regimen_tributario = naturaleza.get('regimen_tributario')
           

            # Responsable de IVA ya no se valida


            # Autorretenedor
            if es_autorretenedor is True:
                return False, "Autorretenedor", None

            # Régimen simple
            if regimen_tributario == "SIMPLE":
                return False, "Régimen simple", None

            # Si pasa todas las validaciones, aplica retención
            return True, "", None

        except Exception as e:
            logger.error(f"Error validando naturaleza de consorciado: {e}")
            return False, f"Error en validación: {str(e)}", None

    def _tiene_datos_null(self, naturaleza: Dict[str, Any]) -> bool:
        """
        Verifica si hay datos críticos null o faltantes.

        Args:
            naturaleza: Datos de naturaleza tributaria

        Returns:
            bool: True si hay datos null críticos
        """
        campos_criticos = ['es_persona_natural', 'regimen_tributario', 'es_autorretenedor']

        for campo in campos_criticos:
            valor = naturaleza.get(campo)
            if valor is None:
                return True

        return False

    def _obtener_campo_faltante(self, naturaleza: Dict[str, Any]) -> Optional[str]:
        """
        Obtiene el primer campo crítico que es null con su descripción legible.

        Args:
            naturaleza: Datos de naturaleza tributaria

        Returns:
            str: Descripción del campo faltante o None
        """
        campos_criticos = {
            'es_persona_natural': 'tipo de persona (natural/jurídica)',
            'regimen_tributario': 'régimen tributario',
            'es_autorretenedor': 'autorretenedor'
        }

        for campo, descripcion in campos_criticos.items():
            if naturaleza.get(campo) is None:
                return descripcion

        return None


class ValidadorConceptos(IValidadorConceptos):
    """
    Validador concreto para conceptos de retención.

    SRP: Solo responsable de validar conceptos contra diccionario
    """

    def __init__(self, estructura_contable: int = None, db_manager = None):
        """
        Inicializa el validador

        Args:
            estructura_contable: Código de estructura contable para consultas
            db_manager: Instancia de DatabaseManager para consultas a BD
        """
        self.estructura_contable = estructura_contable
        self.db_manager = db_manager

    def validar_concepto(self, concepto: str, diccionario_conceptos: Dict[str, Any], concepto_index: int = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Valida si un concepto existe y consulta datos reales desde BD si tiene index.

        Args:
            concepto: Nombre del concepto a validar
            diccionario_conceptos: Diccionario de conceptos válidos (ahora con formato {descripcion: index})
            concepto_index: Index del concepto identificado por Gemini

        Returns:
            Tuple[bool, Dict]: (es_valido, datos_concepto con tarifa y base de BD)
        """
        try:
            # Validar concepto no identificado
            if concepto == "CONCEPTO_NO_IDENTIFICADO" or not concepto:
                return False, {}

            # Validar concepto_index == 0 (concepto no mapeado a BD)
            if concepto_index == 0:
                logger.warning(f"Concepto '{concepto}' tiene concepto_index=0, no se pudo mapear a BD")
                return False, {}

            # Si tenemos concepto_index, consultar BD directamente
            if concepto_index and self.db_manager and self.estructura_contable is not None:
                try:
                    logger.info(f"Consultando BD para concepto_index={concepto_index}")
                    resultado_bd = self.db_manager.obtener_concepto_por_index(
                        concepto_index,
                        self.estructura_contable
                    )

                    if resultado_bd['success']:
                        porcentaje_bd = resultado_bd['data']['porcentaje']
                        base_minima_bd = resultado_bd['data']['base']
                        codigo_concepto = resultado_bd['data']['codigo_concepto']

                        # Retornar datos en formato esperado por el calculador
                        datos_concepto = {
                            'tarifa_retencion': porcentaje_bd / 100,  # Convertir de 11 a 0.11
                            'base_pesos': base_minima_bd,
                            'codigo_concepto': codigo_concepto
                        }

                        logger.info(f"Concepto obtenido de BD: tarifa={porcentaje_bd}%, base=${base_minima_bd:,.2f}")
                        return True, datos_concepto
                    else:
                        logger.warning(f"No se pudo obtener concepto de BD: {resultado_bd['message']}")
                except Exception as e:
                    logger.error(f"Error consultando BD para concepto_index={concepto_index}: {e}")

            # Fallback: buscar concepto en diccionario (comportamiento legacy)
            # Buscar concepto exacto
            if concepto in diccionario_conceptos:
                # Si el valor es un index, no un diccionario con datos
                if isinstance(diccionario_conceptos[concepto], int):
                    logger.warning(f"Concepto encontrado pero sin datos de BD, usando index={diccionario_conceptos[concepto]}")
                    return False, {}
                return True, diccionario_conceptos[concepto]

            # Buscar concepto con variaciones (sin acentos, mayúsculas, etc.)
            concepto_normalizado = self._normalizar_concepto(concepto)

            for nombre_concepto, datos_concepto in diccionario_conceptos.items():
                if self._normalizar_concepto(nombre_concepto) == concepto_normalizado:
                    if isinstance(datos_concepto, int):
                        return False, {}
                    return True, datos_concepto

            # No encontrado
            return False, {}

        except Exception as e:
            logger.error(f"Error validando concepto '{concepto}': {e}")
            return False, {}

    def _normalizar_concepto(self, concepto: str) -> str:
        """
        Normaliza un concepto para comparación.

        Args:
            concepto: Concepto a normalizar

        Returns:
            str: Concepto normalizado
        """
        if not concepto:
            return ""

        return concepto.lower().strip().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')


class CalculadorRetencionConsorcio(ICalculadorRetencion):
    """
    Calculador concreto para retenciones de consorcio.

    SRP: Solo responsable de cálculos de retención
    """

    def calcular_retencion_general(self, datos_liquidacion: Dict[str, Any]) -> Decimal:
        """
        Calcula la retención general teórica (solo informativo - real se calcula por consorciado).

        NOTA v3.1.2: Este método ahora es solo informativo.
        La validación de base gravable real se hace por consorciado individual.

        Args:
            datos_liquidacion: Contiene valor_total, conceptos aplicados, etc.

        Returns:
            Decimal: Valor de retención general teórica (sin validación de base mínima)
        """
        try:
            valor_total = Decimal(str(datos_liquidacion.get('valor_total', 0)))
            conceptos = datos_liquidacion.get('conceptos_identificados', [])

            if not conceptos or valor_total <= 0:
                return Decimal('0')

            logger.info(f"📊 Calculando retención general teórica para {len(conceptos)} concepto(s)")

            retencion_total_general = Decimal('0')

            # Procesar TODOS los conceptos (sin validar base mínima a nivel general)
            for concepto in conceptos:
                nombre_concepto = concepto.get('concepto', 'Concepto desconocido')
                tarifa_retencion = Decimal(str(concepto.get('tarifa_retencion', 0))) / 100

                # Calcular retención teórica para este concepto
                retencion_concepto = valor_total * tarifa_retencion
                retencion_total_general += retencion_concepto

                logger.info(f"📈 {nombre_concepto}: ${valor_total:,.2f} × {tarifa_retencion*100}% = ${retencion_concepto:,.2f}")

            # Redondear resultado final a 2 decimales
            retencion_final = retencion_total_general.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            logger.info(f"💡 Retención general teórica: ${retencion_final:,.2f} (sujeta a validación por consorciado)")

            return retencion_final

        except Exception as e:
            logger.error(f"Error calculando retención general: {e}")
            return Decimal('0')

    def calcular_retencion_individual(self,
                                    valor_factura_sin_iva: Decimal,
                                    porcentaje_participacion: float,
                                    conceptos_validados: List[Dict[str, Any]],
                                    diccionario_conceptos: Dict[str, Any]) -> Tuple[Decimal, List[ConceptoLiquidado]]:
        """
        Calcula la retención individual validando base gravable POR CONCEPTO y POR CONSORCIADO.

        NUEVA LÓGICA v3.1.2:
        1. Calcula valor proporcional del consorciado
        2. Por cada concepto, valida si supera base mínima individual
        3. Solo aplica retención para conceptos que superen la base mínima individual

        Args:
            valor_factura_sin_iva: Valor total de la factura sin IVA
            porcentaje_participacion: Porcentaje de participación (0-100)
            conceptos_validados: Lista de conceptos ya validados
            diccionario_conceptos: Diccionario de conceptos de config.py con bases mínimas

        Returns:
            Tuple[Decimal, List[ConceptoLiquidado]]: (valor_retencion_total, conceptos_liquidados)
        """
        try:
            if valor_factura_sin_iva <= 0 or porcentaje_participacion <= 0:
                return Decimal('0'), []

            # Convertir porcentaje a decimal
            porcentaje_decimal = Decimal(str(porcentaje_participacion)) / 100
            valor_individual = valor_factura_sin_iva * porcentaje_decimal

            logger.info(f" Valor individual consorciado ({porcentaje_participacion}%): ${valor_individual:,.2f}")

            retencion_total_individual = Decimal('0')
            conceptos_liquidados = []

            # Validar CADA concepto individualmente
            for concepto in conceptos_validados:
                nombre_concepto = concepto.get('concepto', 'Concepto desconocido')
                tarifa_retencion_pct = concepto.get('tarifa_retencion', 0)
                # DETECCIÓN AUTOMÁTICA DE FORMATO: decimal (0.11) vs porcentaje (11)
                if tarifa_retencion_pct <= 1.0:
                    # Ya está en formato decimal (0.11 = 11%)
                    tarifa_retencion = Decimal(str(tarifa_retencion_pct))
                    tarifa_display = tarifa_retencion_pct * 100  # Para mostrar en logs
                else:
                    # Está en formato porcentaje (11 = 11%)
                    tarifa_retencion = Decimal(str(tarifa_retencion_pct)) / 100
                    tarifa_display = tarifa_retencion_pct

                # BASE GRAVABLE DE LA FACTURA (extraída por Gemini por este concepto)
                base_gravable_factura = Decimal(str(concepto.get('base_gravable', 0)))

                # CODIGO DEL CONCEPTO (obtenido de BD en validar_concepto)
                codigo_concepto = concepto.get('codigo_concepto', None)

                # BASE MÍNIMA: Primero intentar obtener de BD (ya está en concepto), luego diccionario
                base_minima_diccionario = None

                # ESTRATEGIA 1: Si ya viene en el concepto (desde BD en validar_concepto)
                if 'base_pesos' in concepto and concepto['base_pesos'] is not None:
                    base_minima_diccionario = Decimal(str(concepto['base_pesos']))
                    logger.debug(f" Base mínima obtenida de BD (en concepto): ${base_minima_diccionario:,.2f}")
                else:
                    # ESTRATEGIA 2: Fallback a diccionario legacy
                    nombre_concepto_dict = concepto.get('concepto', '')
                    logger.debug(f" Buscando concepto '{nombre_concepto_dict}' en diccionario legacy")
                    base_minima_diccionario = self._obtener_base_minima_del_diccionario(nombre_concepto_dict, diccionario_conceptos)

                # Calcular base gravable individual del consorciado
                base_gravable_individual = base_gravable_factura * porcentaje_decimal

                # VALIDACIÓN CRÍTICA: Base gravable individual vs base mínima normativa
                if base_gravable_individual < base_minima_diccionario:
                    # No aplica este concepto
                    concepto_liquidado = ConceptoLiquidado(
                        nombre_concepto=nombre_concepto,
                        codigo_concepto=codigo_concepto,
                        tarifa_retencion=float(tarifa_retencion),
                        base_gravable_individual=base_gravable_individual,
                        base_minima_normativa=base_minima_diccionario,
                        aplica_concepto=False,
                        valor_retencion_concepto=Decimal('0'),
                        razon_no_aplicacion=f"Base individual ${base_gravable_individual:,.2f} < Base mínima ${base_minima_diccionario:,.2f}"
                    )
                    logger.info(f" {nombre_concepto}: {concepto_liquidado.razon_no_aplicacion}")
                else:
                    # Calcular retención para este concepto sobre la base gravable individual
                    retencion_concepto = base_gravable_individual * tarifa_retencion
                    retencion_total_individual += retencion_concepto

                    concepto_liquidado = ConceptoLiquidado(
                        nombre_concepto=nombre_concepto,
                        codigo_concepto=codigo_concepto,
                        tarifa_retencion=float(tarifa_retencion),
                        base_gravable_individual=base_gravable_individual,
                        base_minima_normativa=base_minima_diccionario,
                        aplica_concepto=True,
                        valor_retencion_concepto=retencion_concepto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    )
                    logger.info(f" {nombre_concepto}: Base ${base_gravable_individual:,.2f} × {tarifa_display}% = ${concepto_liquidado.valor_retencion_concepto:,.2f}")

                conceptos_liquidados.append(concepto_liquidado)

            # Redondear resultado final
            retencion_final = retencion_total_individual.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if retencion_final > 0:
                logger.info(f" Retención individual total: ${retencion_final:,.2f}")
            else:
                logger.info(" Sin retención individual - ningún concepto superó base mínima")

            return retencion_final, conceptos_liquidados

        except Exception as e:
            logger.error(f"Error calculando retención individual: {e}")
            return Decimal('0'), []

    def _obtener_base_minima_del_diccionario(self, nombre_concepto: str, diccionario_conceptos: Dict[str, Any]) -> Decimal:
        """
        Obtiene la base mínima normativa del diccionario de conceptos de config.py.

        Args:
            nombre_concepto: Nombre del concepto a buscar
            diccionario_conceptos: Diccionario de conceptos de config.py

        Returns:
            Decimal: Base mínima normativa para el concepto
        """
        try:
            if not nombre_concepto or not diccionario_conceptos:
                return Decimal('0')

            # Buscar concepto en el diccionario
            logger.debug(f" DEBUG: Buscando '{nombre_concepto}' en {len(diccionario_conceptos)} conceptos")
            logger.debug(f" DEBUG: Conceptos disponibles: {list(diccionario_conceptos.keys())[:5]}...")

            datos_concepto = diccionario_conceptos.get(nombre_concepto, {})

            if not datos_concepto:
                logger.warning(f"Concepto '{nombre_concepto}' no encontrado en diccionario")
                # Intentar búsqueda similar
                for concepto_disponible in diccionario_conceptos.keys():
                    if nombre_concepto.lower() in concepto_disponible.lower():
                        logger.info(f" Concepto similar encontrado: '{concepto_disponible}'")
                        break
                return Decimal('0')

            # Buscar base mínima (puede estar como 'base_pesos', 'base_minima', 'uvt_minima', etc.)
            base_minima = datos_concepto.get('base_pesos',
                         datos_concepto.get('base_minima',
                         datos_concepto.get('uvt_minima',
                         datos_concepto.get('base_gravable', 0))))

            base_decimal = Decimal(str(base_minima))
            logger.debug(f" Base mínima para '{nombre_concepto}': ${base_decimal:,.2f}")
            logger.debug(f" DEBUG: Datos completos del concepto: {datos_concepto}")

            return base_decimal

        except Exception as e:
            logger.error(f"Error obteniendo base mínima para '{nombre_concepto}': {e}")
            return Decimal('0')


# ===============================
# LIQUIDADOR PRINCIPAL
# ===============================

class LiquidadorConsorcios:
    """
    Liquidador principal para consorcios siguiendo principios SOLID.

    PRINCIPIOS APLICADOS:
    - SRP: Solo coordina liquidación de consorcios
    - DIP: Depende de abstracciones (interfaces)
    - OCP: Extensible mediante inyección de nuevos validadores/calculadores
    """

    def __init__(self,
                 estructura_contable: int = None,
                 db_manager = None,
                 validador_naturaleza: Optional[IValidadorNaturaleza] = None,
                 validador_conceptos: Optional[IValidadorConceptos] = None,
                 calculador_retencion: Optional[ICalculadorRetencion] = None):
        """
        Inicializa el liquidador con inyección de dependencias.

        Args:
            estructura_contable: Código de estructura contable para consultas
            db_manager: Instancia de DatabaseManager para consultas a BD
            validador_naturaleza: Validador de naturaleza tributaria
            validador_conceptos: Validador de conceptos
            calculador_retencion: Calculador de retenciones
        """
        # Guardar parámetros de BD
        self.estructura_contable = estructura_contable
        self.db_manager = db_manager

        # DIP: Inyección de dependencias con valores por defecto
        self.validador_naturaleza = validador_naturaleza or ValidadorNaturalezaTributaria()
        self.validador_conceptos = validador_conceptos or ValidadorConceptos(estructura_contable, db_manager)
        self.calculador_retencion = calculador_retencion or CalculadorRetencionConsorcio()

        logger.info("LiquidadorConsorcios inicializado con arquitectura SOLID")

    async def liquidar_consorcio(self,
                                analisis_gemini: Dict[str, Any],
                                diccionario_conceptos: Dict[str, Any],
                                archivos_directos: List = None,
                                cache_archivos: Dict[str, bytes] = None) -> ResultadoLiquidacionConsorcio:
        """
        Liquida un consorcio completo aplicando validaciones manuales y cálculos.

        FLUJO SOLID:
        1. Validar estructura del análisis
        2. Validar conceptos identificados
        3. Validar naturaleza de cada consorciado
        4. Calcular retención general
        5. Calcular retenciones individuales
        6. Generar resultado estructurado

        Args:
            analisis_gemini: Resultado del análisis de Gemini (solo extracción)
            diccionario_conceptos: Diccionario de conceptos válidos

        Returns:
            ResultadoLiquidacionConsorcio: Resultado completo de liquidación
        """
        logger.info(" Iniciando liquidación de consorcio con validaciones manuales")

        try:
            # PASO 1: Validar estructura básica
            es_valida, mensaje_error = self._validar_estructura_consorcio(analisis_gemini)
            if not es_valida:
                return self._crear_resultado_error(mensaje_error)

            # PASO 2: Validar conceptos identificados
            conceptos_validos, mensaje_concepto = self._validar_conceptos_consorcio(
                analisis_gemini.get('conceptos_identificados', []),
                diccionario_conceptos
            )

            if not conceptos_validos:
                # Preservar valor_total de la factura incluso si hay errores
                valor_total = Decimal(str(analisis_gemini.get('valor_total', 0)))
                return self._crear_resultado_sin_finalizar(mensaje_concepto, valor_total)

            # PASO 3: Validar y liquidar consorciados individuales
            consorciados_liquidados = []
            observaciones = []
            error_naturaleza_incompleta = False
            mensajes_error_naturaleza = []

            for consorciado in analisis_gemini.get('consorciados', []):
                consorciado_liquidado = self._liquidar_consorciado_individual(
                    consorciado, conceptos_validos, analisis_gemini, diccionario_conceptos
                )
                consorciados_liquidados.append(consorciado_liquidado)

                # Detectar naturaleza tributaria incompleta (NO detener, solo marcar)
                if not consorciado_liquidado.aplica_retencion and consorciado_liquidado.razon_no_aplicacion:
                    if "incompleta" in consorciado_liquidado.razon_no_aplicacion.lower():
                        # Marcar error y acumular mensaje
                        error_naturaleza_incompleta = True
                        campo_faltante = consorciado.get('_campo_faltante', 'información de naturaleza tributaria')
                        mensaje = f"No se identificó el {campo_faltante} del consorciado {consorciado_liquidado.nombre}"
                        mensajes_error_naturaleza.append(mensaje)
                    else:
                        observaciones.append(f"{consorciado_liquidado.nombre}: {consorciado_liquidado.razon_no_aplicacion}")

            # Verificar si hubo error de naturaleza incompleta DESPUÉS de procesar todos
            if error_naturaleza_incompleta:
                valor_total = Decimal(str(analisis_gemini.get('valor_total', 0)))
                return ResultadoLiquidacionConsorcio(
                    es_consorcio=True,
                    nombre_consorcio=analisis_gemini.get('nombre_consorcio', ''),
                    consorciados=consorciados_liquidados,
                    retencion_total=Decimal('0'),
                    valor_factura_sin_iva=valor_total,
                    conceptos_aplicados=conceptos_validos,
                    estado="preliquidación_sin_finalizar",
                    observaciones=mensajes_error_naturaleza,
                    procesamiento_exitoso=False
                )

            # PASO 4: Calcular totales
            retencion_total = sum(c.valor_retencion for c in consorciados_liquidados)
            valor_total = Decimal(str(analisis_gemini.get('valor_total', 0)))

            # PASO 5: Generar resultado final
            return ResultadoLiquidacionConsorcio(
                es_consorcio=True,
                nombre_consorcio=analisis_gemini.get('nombre_consorcio', ''),
                consorciados=consorciados_liquidados,
                retencion_total=retencion_total,
                valor_factura_sin_iva=valor_total,
                conceptos_aplicados=conceptos_validos,
                estado="preliquidado",
                observaciones=observaciones,
                procesamiento_exitoso=True
            )

        except Exception as e:
            logger.error(f"Error en liquidación de consorcio: {e}")
            return self._crear_resultado_error(f"Error en liquidación: {str(e)}")

    def _validar_estructura_consorcio(self, analisis: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Valida que el análisis tenga la estructura mínima requerida.

        Args:
            analisis: Análisis de Gemini

        Returns:
            Tuple[bool, str]: (es_valida, mensaje_error_para_usuario)
        """
        campos_requeridos = ['es_consorcio', 'consorciados', 'conceptos_identificados']

        # Mapeo de campos técnicos a mensajes amigables para el usuario
        mensajes_usuario = {
            'es_consorcio': 'No se pudo identificar que el documento corresponda a un consorcio',
            'consorciados': 'No se identificaron los consorciados en los documentos analizados',
            'conceptos_identificados': 'No se identificaron conceptos de retención en los documentos analizados'
        }

        for campo in campos_requeridos:
            if campo not in analisis:
                mensaje_usuario = mensajes_usuario.get(campo, f'Falta información requerida: {campo}')
                logger.error(f"Campo requerido faltante: {campo}")
                return False, mensaje_usuario

        if not analisis.get('es_consorcio', False):
            mensaje = 'El documento no corresponde a un consorcio'
            logger.error(mensaje)
            return False, mensaje

        if not analisis.get('consorciados'):
            mensaje = 'Información incompleta para uno o más consorciados. Adjuntar porcentajes de participación o soportes.'
            logger.error(mensaje)
            return False, mensaje

        return True, ""

    def _validar_conceptos_consorcio(self,
                                   conceptos_identificados: List[Dict[str, Any]],
                                   diccionario_conceptos: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
        """
        Valida los conceptos identificados contra el diccionario.

        Args:
            conceptos_identificados: Conceptos identificados por Gemini
            diccionario_conceptos: Diccionario de conceptos válidos

        Returns:
            Tuple[List[Dict], str]: (conceptos_validos, mensaje_error)
        """
        conceptos_validos = []

        for concepto_data in conceptos_identificados:
            concepto_nombre = concepto_data.get('concepto', '')
            concepto_index = concepto_data.get('concepto_index', None)

            es_valido, datos_concepto = self.validador_conceptos.validar_concepto(
                concepto_nombre, diccionario_conceptos, concepto_index
            )

            if not es_valido:
                mensaje_error = "No se pudieron relacionar los conceptos facturados con los conceptos almacenados en base de datos"
                logger.warning(f"Concepto no válido: {concepto_nombre}")
                return [], mensaje_error

            # Combinar datos de Gemini con datos del diccionario/BD
            concepto_completo = {
                **concepto_data,
                **datos_concepto
            }
            conceptos_validos.append(concepto_completo)

        return conceptos_validos, ""

    def _liquidar_consorciado_individual(self,
                                       consorciado: Dict[str, Any],
                                       conceptos_validos: List[Dict[str, Any]],
                                       analisis_general: Dict[str, Any],
                                       diccionario_conceptos: Dict[str, Any]) -> ConsorciadoLiquidado:
        """
        Liquida un consorciado individual aplicando todas las validaciones.

        Args:
            consorciado: Datos del consorciado
            conceptos_validos: Conceptos ya validados
            analisis_general: Análisis general del consorcio
            diccionario_conceptos: Diccionario de conceptos de config.py

        Returns:
            ConsorciadoLiquidado: Consorciado liquidado
        """
        nombre = consorciado.get('nombre', '')
        nit = consorciado.get('nit', '')
        porcentaje = float(consorciado.get('porcentaje_participacion', 0))

        # Validar naturaleza tributaria
        aplica_retencion, razon_no_aplicacion, campo_faltante = self.validador_naturaleza.validar_naturaleza_consorcio(consorciado)

        # Guardar campo_faltante temporalmente para uso posterior
        if campo_faltante:
            consorciado['_campo_faltante'] = campo_faltante

        if not aplica_retencion:
            # No aplica retención por naturaleza
            return ConsorciadoLiquidado(
                nombre=nombre,
                nit=nit,
                porcentaje_participacion=porcentaje,
                aplica_retencion=False,
                valor_retencion=Decimal('0'),
                valor_base=Decimal('0'),
                conceptos_liquidados=[],
                razon_no_aplicacion=razon_no_aplicacion,
                naturaleza_tributaria=consorciado.get('naturaleza_tributaria')
            )

        # Calcular valor base individual
        valor_total = Decimal(str(analisis_general.get('valor_total', 0)))
        valor_base_individual = valor_total * (Decimal(str(porcentaje)) / 100)

        # NUEVA LÓGICA v3.1.2: Calcular retención individual con validación de base gravable
        retencion_individual, conceptos_liquidados = self.calculador_retencion.calcular_retencion_individual(
            valor_total, porcentaje, conceptos_validos, diccionario_conceptos
        )

        return ConsorciadoLiquidado(
            nombre=nombre,
            nit=nit,
            porcentaje_participacion=porcentaje,
            aplica_retencion=retencion_individual > 0,
            valor_retencion=retencion_individual,
            valor_base=valor_base_individual,
            conceptos_liquidados=conceptos_liquidados,
            naturaleza_tributaria=consorciado.get('naturaleza_tributaria')
        )

    def _crear_resultado_error(self, mensaje: str) -> ResultadoLiquidacionConsorcio:
        """
        Crea un resultado de error.

        Args:
            mensaje: Mensaje de error

        Returns:
            ResultadoLiquidacionConsorcio: Resultado con error
        """
        return ResultadoLiquidacionConsorcio(
            es_consorcio=False,
            nombre_consorcio="",
            consorciados=[],
            retencion_total=Decimal('0'),
            valor_factura_sin_iva=Decimal('0'),
            conceptos_aplicados=[],
            estado="preliquidacion_sin_finalizar",
            observaciones=[mensaje],
            procesamiento_exitoso=False
        )

    def _crear_resultado_sin_finalizar(self, mensaje: str, valor_factura_sin_iva: Decimal = Decimal('0')) -> ResultadoLiquidacionConsorcio:
        """
        Crea un resultado de preliquidación sin finalizar.

        Args:
            mensaje: Mensaje explicativo
            valor_factura_sin_iva: Valor total de la factura sin IVA (extraído por Gemini)

        Returns:
            ResultadoLiquidacionConsorcio: Resultado sin finalizar
        """
        return ResultadoLiquidacionConsorcio(
            es_consorcio=True,
            nombre_consorcio="",
            consorciados=[],
            retencion_total=Decimal('0'),
            valor_factura_sin_iva=valor_factura_sin_iva,
            conceptos_aplicados=[],
            estado="preliquidacion_sin_finalizar",
            observaciones=[mensaje],
            procesamiento_exitoso=False
        )
    


# ===============================
# FUNCIONES DE UTILIDAD
# ===============================

def convertir_resultado_a_dict(resultado: ResultadoLiquidacionConsorcio) -> Dict[str, Any]:
    """
    Convierte el resultado de liquidación a diccionario para serialización.

    Args:
        resultado: Resultado de liquidación

    Returns:
        Dict: Resultado como diccionario
    """
    consorciados_dict = []

    for consorciado in resultado.consorciados:
        consorciado_dict = {
            "nombre": consorciado.nombre,
            "nit": consorciado.nit,
            "porcentaje_participacion": consorciado.porcentaje_participacion,
            "aplica": consorciado.aplica_retencion,
            "valor_retencion": float(consorciado.valor_retencion),
            "valor_base": float(consorciado.valor_base)
        }

        if consorciado.razon_no_aplicacion:
            consorciado_dict["razon_no_aplicacion"] = consorciado.razon_no_aplicacion

        # NUEVO v3.1.2: Incluir detalle completo de conceptos liquidados por consorciado
        conceptos_detalle = []
        for concepto_liq in consorciado.conceptos_liquidados:
            concepto_detalle = {
                "nombre_concepto": concepto_liq.nombre_concepto,
                "codigo_concepto": concepto_liq.codigo_concepto,
                "tarifa_retencion": concepto_liq.tarifa_retencion,
                "base_gravable_individual": float(concepto_liq.base_gravable_individual),
                "base_minima_normativa": float(concepto_liq.base_minima_normativa),
                "aplica_concepto": concepto_liq.aplica_concepto,
                "valor_retencion_concepto": float(concepto_liq.valor_retencion_concepto)
            }
            if concepto_liq.razon_no_aplicacion:
                concepto_detalle["razon_no_aplicacion"] = concepto_liq.razon_no_aplicacion

            conceptos_detalle.append(concepto_detalle)

        consorciado_dict["conceptos_liquidados"] = conceptos_detalle

        consorciados_dict.append(consorciado_dict)

    # Formatear conceptos aplicados con información detallada
    conceptos_dict = []
    for concepto in resultado.conceptos_aplicados:
        concepto_dict = {
            "concepto": concepto.get('concepto', ''),
            "tarifa_retencion": concepto.get('tarifa_retencion', 0),
            "base_gravable": concepto.get('base_gravable', 0)
        }
        conceptos_dict.append(concepto_dict)

    return {
        "retefuente": {
            "es_consorcio": resultado.es_consorcio,
            "nombre_consorcio": resultado.nombre_consorcio,
            "consorciados": consorciados_dict,
            "retencion_total": float(resultado.retencion_total),
            "valor_factura_sin_iva": float(resultado.valor_factura_sin_iva),
            "conceptos_aplicados": conceptos_dict,
            "resumen_conceptos": ", ".join([f"{c.get('concepto', '')} ({c.get('tarifa_retencion', 0)}%)" for c in resultado.conceptos_aplicados]) if resultado.conceptos_aplicados else "Sin conceptos",
            "estado": resultado.estado,
            "observaciones": resultado.observaciones,
            "procesamiento_exitoso": resultado.procesamiento_exitoso,
        }
    }


# ===============================
# FACTORY PARA CREACIÓN
# ===============================

class LiquidadorConsorciosFactory:
    """
    Factory para crear instancias de LiquidadorConsorcios.

    PRINCIPIOS APLICADOS:
    - Factory Pattern: Centraliza creación de objetos complejos
    - SRP: Solo responsable de crear liquidadores
    - DIP: Permite inyección de diferentes implementaciones
    """

    @staticmethod
    def crear_liquidador(config_personalizada: Optional[Dict[str, Any]] = None) -> LiquidadorConsorcios:
        """
        Crea instancia de LiquidadorConsorcios con configuración opcional.

        Args:
            config_personalizada: Configuración opcional para validadores/calculadores

        Returns:
            LiquidadorConsorcios: Instancia configurada
        """
        if config_personalizada:
            # Permitir inyección de implementaciones personalizadas
            validador_naturaleza = config_personalizada.get('validador_naturaleza')
            validador_conceptos = config_personalizada.get('validador_conceptos')
            calculador_retencion = config_personalizada.get('calculador_retencion')

            return LiquidadorConsorcios(
                validador_naturaleza=validador_naturaleza,
                validador_conceptos=validador_conceptos,
                calculador_retencion=calculador_retencion
            )

        # Configuración por defecto
        return LiquidadorConsorcios()


if __name__ == '__main__':
    # Ejemplo de uso
    liquidador = LiquidadorConsorciosFactory.crear_liquidador()
    logger.info("✅ LiquidadorConsorcios creado con arquitectura SOLID")