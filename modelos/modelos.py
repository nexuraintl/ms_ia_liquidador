"""
MODELOS DE DATOS - DOMAIN LAYER
================================

Modelos Pydantic para el sistema de liquidacion de impuestos.
Define estructuras de datos para retencion en la fuente, deducciones
personales (Articulo 383) y resultados de liquidacion.


ORGANIZACION:
1. Modelos para Retencion General (3 modelos)
2. Modelos para Articulo 383 - Deducciones Personales (9 modelos)
3. Modelos Agregadores - Entrada/Salida (2 modelos)

Autor: Sistema Preliquidador
Version: 3.0 - Clean Architecture
"""

from pydantic import BaseModel
from typing import List, Optional

# ===============================
# SECCION 1: MODELOS PARA RETENCION EN LA FUENTE
# ===============================

class ConceptoIdentificado(BaseModel):
    """
    Concepto de retencion identificado en la factura.

    Representa un concepto tributario sobre el cual se puede aplicar
    retencion en la fuente segun normativa colombiana.

    Attributes:
        concepto: Nombre normalizado del concepto segun CONCEPTOS_RETEFUENTE
        concepto_facturado: Descripcion literal del concepto en la factura (opcional)
        base_gravable: Base sobre la que se calcula la retencion (opcional)
        concepto_index: Indice del concepto en la lista de conceptos (opcional)

    Example:
        >>> concepto = ConceptoIdentificado(
        ...     concepto="Servicios generales",
        ...     concepto_facturado="Consultoria en software",
        ...     base_gravable=5000000.0,
        ...     concepto_index=0
        ... )
    """
    concepto: str
    concepto_facturado: Optional[str] = None
    base_gravable: Optional[float] = None
    concepto_index: Optional[int] = None


class DetalleConcepto(BaseModel):
    """
    Detalle individual de un concepto liquidado.

    Proporciona transparencia total del calculo de retencion para cada
    concepto aplicado, incluyendo tarifa, base gravable y valor calculado.

    Attributes:
        concepto: Nombre del concepto de retencion
        concepto_facturado: Descripcion del concepto en la factura (opcional)
        tarifa_retencion: Porcentaje de retencion aplicado (0.0 a 100.0)
        base_gravable: Base sobre la que se calcula la retencion
        valor_retencion: Valor final de retencion calculado
        codigo_concepto: Codigo del concepto desde base de datos (opcional)

    Example:
        >>> detalle = DetalleConcepto(
        ...     concepto="Servicios generales (declarantes)",
        ...     tarifa_retencion=4.0,
        ...     base_gravable=5000000.0,
        ...     valor_retencion=200000.0,
        ...     codigo_concepto="001"
        ... )

    Version: Agregado en v2.10.0 para transparencia en calculos
    """
    concepto: str
    concepto_facturado: Optional[str] = None
    tarifa_retencion: float
    base_gravable: float
    valor_retencion: float
    codigo_concepto: Optional[str] = None


class NaturalezaTercero(BaseModel):
    """
    Informacion sobre la naturaleza juridica del tercero (proveedor).

    Determina el tipo de persona, regimen tributario y condiciones especiales
    que afectan el calculo de retencion en la fuente.

    Attributes:
        es_persona_natural: True si es persona natural, False si es persona juridica
        regimen_tributario: Tipo de regimen (SIMPLE, ORDINARIO, ESPECIAL)
        es_autorretenedor: True si es autorretenedor

    Example:
        >>> tercero = NaturalezaTercero(
        ...     es_persona_natural=False,
        ...     regimen_tributario="ORDINARIO",
        ...     es_autorretenedor=False
        ... )

    Note:
        Esta informacion es critica para determinar tarifas y aplicabilidad
        de deducciones del Articulo 383 (solo personas naturales).

    Version:
        Campo es_declarante removido - No identificado por Gemini
    """
    es_persona_natural: Optional[bool] = None
    regimen_tributario: Optional[str] = None  # SIMPLE, ORDINARIO, ESPECIAL
    es_autorretenedor: Optional[bool] = None


# ===============================
# SECCION 2: MODELOS PARA ARTICULO 383 - DEDUCCIONES PERSONALES
# ===============================

class ConceptoIdentificadoArt383(BaseModel):
    """
    Concepto deducible identificado para Articulo 383.

    Representa un concepto de servicio personal que califica para
    aplicacion de deducciones personales segun Articulo 383 del
    Estatuto Tributario.

    Attributes:
        concepto: Nombre del concepto deducible
        base_gravable: Monto del ingreso sujeto a deducciones

    Example:
        >>> concepto_art383 = ConceptoIdentificadoArt383(
        ...     concepto="Servicios personales - Articulo 383",
        ...     base_gravable=10000000.0
        ... )

    Note:
        Solo aplica para personas naturales con conceptos especificos.
    """
    concepto: str
    base_gravable: float = 0.0


class CondicionesArticulo383(BaseModel):
    """
    Condiciones para aplicar deducciones del Articulo 383.

    Valida si se cumplen las condiciones obligatorias para aplicar
    deducciones personales segun Articulo 383 del ET.

    Attributes:
        es_persona_natural: Condicion obligatoria - debe ser persona natural
        conceptos_identificados: Lista de conceptos que califican para Art 383
        conceptos_aplicables: True si hay conceptos que aplican
        ingreso: Ingreso base para calcular deducciones
        es_primer_pago: True si es el primer pago (afecta documentos requeridos)
        documento_soporte: True si hay documento que soporta las deducciones

    Example:
        >>> condiciones = CondicionesArticulo383(
        ...     es_persona_natural=True,
        ...     conceptos_aplicables=True,
        ...     ingreso=10000000.0,
        ...     es_primer_pago=False,
        ...     documento_soporte=True
        ... )

    Version: Estructura actualizada en v2.10.0 para validaciones manuales
    """
    es_persona_natural: bool = False
    conceptos_identificados: List[ConceptoIdentificadoArt383] = []
    conceptos_aplicables: bool = False
    ingreso: float = 0.0
    es_primer_pago: bool = False
    documento_soporte: bool = False


class InteresesVivienda(BaseModel):
    """
    Deduccion por intereses de credito de vivienda.

    Informacion sobre intereses pagados por prestamos de vivienda
    que pueden deducirse del ingreso gravable segun Art 383.

    Attributes:
        intereses_corrientes: Monto de intereses pagados
        certificado_bancario: True si hay certificado del banco

    Example:
        >>> intereses = InteresesVivienda(
        ...     intereses_corrientes=2000000.0,
        ...     certificado_bancario=True
        ... )

    Limits:
        Maximo deducible: 1.200 UVT anuales (~$55MM en 2024)
    """
    intereses_corrientes: float = 0.0
    certificado_bancario: bool = False


class DependientesEconomicos(BaseModel):
    """
    Deduccion por dependientes economicos.

    Informacion sobre dependientes economicos que pueden deducirse
    del ingreso gravable segun Art 383.

    Attributes:
        nombre_encargado: Nombre de quien declara los dependientes
        declaracion_juramentada: True si hay declaracion juramentada

    Example:
        >>> dependientes = DependientesEconomicos(
        ...     nombre_encargado="Juan Perez",
        ...     declaracion_juramentada=True
        ... )

    Limits:
        Maximo deducible: 10% del ingreso gravable, hasta 32 UVT por dependiente
    """
    nombre_encargado: str = ""
    declaracion_juramentada: bool = False


class MedicinaPrepagada(BaseModel):
    """
    Deduccion por medicina prepagada.

    Informacion sobre pagos a medicina prepagada que pueden deducirse
    del ingreso gravable segun Art 383.

    Attributes:
        valor_sin_iva_med_prepagada: Valor pagado sin IVA
        certificado_med_prepagada: True si hay certificado de la entidad

    Example:
        >>> medicina = MedicinaPrepagada(
        ...     valor_sin_iva_med_prepagada=3000000.0,
        ...     certificado_med_prepagada=True
        ... )

    Limits:
        Maximo deducible: 16 UVT mensuales (~$750.000 en 2024)
    """
    valor_sin_iva_med_prepagada: float = 0.0
    certificado_med_prepagada: bool = False


class AFCInfo(BaseModel):
    """
    Deduccion por AFC (Ahorro para Fomento a la Construccion).

    Informacion sobre aportes a cuentas AFC que pueden deducirse
    del ingreso gravable segun Art 383.

    Attributes:
        valor_a_depositar: Monto a depositar en cuenta AFC
        planilla_de_cuenta_AFC: True si hay planilla de la cuenta

    Example:
        >>> afc = AFCInfo(
        ...     valor_a_depositar=5000000.0,
        ...     planilla_de_cuenta_AFC=True
        ... )

    Limits:
        Maximo deducible: 30% del ingreso gravable del mes
    """
    valor_a_depositar: float = 0.0
    planilla_de_cuenta_AFC: bool = False


class PlanillaSeguridadSocial(BaseModel):
    """
    Deduccion por aportes a seguridad social.

    Informacion sobre aportes obligatorios a seguridad social que
    se deducen del ingreso gravable segun Art 383.

    Attributes:
        IBC_seguridad_social: Ingreso Base de Cotizacion
        planilla_seguridad_social: True si hay planilla PILA
        fecha_de_planilla_seguridad_social: Fecha de pago de la planilla

    Example:
        >>> planilla = PlanillaSeguridadSocial(
        ...     IBC_seguridad_social=8000000.0,
        ...     planilla_seguridad_social=True,
        ...     fecha_de_planilla_seguridad_social="2024-10-15"
        ... )

    Note:
        Planilla debe ser de maximo 2 meses antes del pago.
        IBC minimo: 1 SMMLV, maximo: 25 SMMLV
    """
    IBC_seguridad_social: float = 0.0
    planilla_seguridad_social: bool = False
    fecha_de_planilla_seguridad_social: str = "0000-00-00"


class DeduccionesArticulo383(BaseModel):
    """
    Contenedor de todas las deducciones del Articulo 383.

    Agrupa todas las deducciones personales identificadas que pueden
    aplicarse al calculo de retencion segun Art 383.

    Attributes:
        intereses_vivienda: Deduccion por intereses de vivienda
        dependientes_economicos: Deduccion por dependientes
        medicina_prepagada: Deduccion por medicina prepagada
        AFC: Deduccion por aportes AFC
        planilla_seguridad_social: Deduccion por seguridad social

    Example:
        >>> deducciones = DeduccionesArticulo383(
        ...     intereses_vivienda=InteresesVivienda(intereses_corrientes=2000000.0),
        ...     medicina_prepagada=MedicinaPrepagada(valor_sin_iva_med_prepagada=1000000.0)
        ... )

    Version: Estructura actualizada en v2.10.0
    """
    intereses_vivienda: InteresesVivienda = InteresesVivienda()
    dependientes_economicos: DependientesEconomicos = DependientesEconomicos()
    medicina_prepagada: MedicinaPrepagada = MedicinaPrepagada()
    AFC: AFCInfo = AFCInfo()
    planilla_seguridad_social: PlanillaSeguridadSocial = PlanillaSeguridadSocial()


class InformacionArticulo383(BaseModel):
    """
    Informacion completa del Articulo 383.

    Contenedor principal para toda la informacion relacionada con
    deducciones personales del Articulo 383.

    Attributes:
        condiciones_cumplidas: Condiciones evaluadas para aplicar Art 383
        deducciones_identificadas: Todas las deducciones identificadas

    Example:
        >>> info_art383 = InformacionArticulo383(
        ...     condiciones_cumplidas=CondicionesArticulo383(...),
        ...     deducciones_identificadas=DeduccionesArticulo383(...)
        ... )

    Version: Estructura actualizada en v2.10.0 para separar IA-Validacion Manual
    """
    condiciones_cumplidas: CondicionesArticulo383 = CondicionesArticulo383()
    deducciones_identificadas: DeduccionesArticulo383 = DeduccionesArticulo383()


# ===============================
# SECCION 3: MODELOS AGREGADORES - ENTRADA/SALIDA
# ===============================

class AnalisisFactura(BaseModel):
    """
    Analisis completo de una factura para liquidacion.

    Modelo de entrada principal que contiene toda la informacion
    extraida y analizada de una factura para calcular retencion.

    Attributes:
        conceptos_identificados: Lista de conceptos de retencion encontrados
        naturaleza_tercero: Tipo de tercero (persona natural/juridica, etc.)
        articulo_383: Informacion de deducciones personales (solo si aplica)
        es_facturacion_exterior: True si es facturacion internacional
        pais_proveedor: Pais del proveedor (solo facturacion extranjera)
        valor_total: Valor total de la factura
        observaciones: Lista de observaciones del analisis

    Example:
        >>> analisis = AnalisisFactura(
        ...     conceptos_identificados=[concepto1, concepto2],
        ...     naturaleza_tercero=NaturalezaTercero(...),
        ...     articulo_383=InformacionArticulo383(...),
        ...     valor_total=10000000.0,
        ...     observaciones=["Factura valida"]
        ... )

    Note:
        Este es el modelo principal de entrada para el liquidador.
        articulo_383 es opcional y solo se incluye para personas naturales.

    Version: articulo_383 agregado en v2.10.0
    Version: pais_proveedor agregado en v3.1.1 (facturacion extranjera)
    """
    conceptos_identificados: List[ConceptoIdentificado]
    naturaleza_tercero: Optional[NaturalezaTercero]
    articulo_383: Optional[InformacionArticulo383] = None
    es_facturacion_exterior: bool = False
    pais_proveedor: Optional[str] = None
    valor_total: Optional[float]
    observaciones: List[str]


class ResultadoLiquidacion(BaseModel):
    """
    Resultado final de la liquidacion de retencion en la fuente.

    Modelo de salida principal que contiene todos los calculos,
    detalles por concepto y estado de la liquidacion.

    Attributes:
        valor_base_retencion: Base gravable total para retencion
        valor_retencion: Valor total de retencion calculado
        valor_factura_sin_iva: Valor total de la factura sin IVA
        conceptos_aplicados: Lista detallada de conceptos liquidados
        resumen_conceptos: Resumen descriptivo de los conceptos
        fecha_calculo: Timestamp del calculo
        puede_liquidar: True si fue posible liquidar
        mensajes_error: Lista de errores o advertencias
        estado: Estado de la liquidacion (ver Estados Posibles)

    Estados Posibles:
        - "no_aplica_impuesto": No aplica retencion (autorretenedor, etc.)
        - "preliquidacion_sin_finalizar": Error o datos incompletos
        - "preliquidado": Liquidacion exitosa

    Example:
        >>> resultado = ResultadoLiquidacion(
        ...     valor_base_retencion=10000000.0,
        ...     valor_retencion=400000.0,
        ...     valor_factura_sin_iva=10000000.0,
        ...     conceptos_aplicados=[detalle1, detalle2],
        ...     resumen_conceptos="Servicios generales (4.0%)",
        ...     fecha_calculo="2024-10-30T10:30:00",
        ...     puede_liquidar=True,
        ...     mensajes_error=[],
        ...     estado="preliquidado"
        ... )

    Version:
        - valor_factura_sin_iva: Agregado en v2.10.0
        - conceptos_aplicados: Agregado en v2.10.0 (transparencia)
        - resumen_conceptos: Agregado en v2.10.0
        - estado: Agregado en v2.10.0
    """
    valor_base_retencion: float
    valor_retencion: float
    valor_factura_sin_iva: float
    conceptos_aplicados: List[DetalleConcepto]
    resumen_conceptos: str
    fecha_calculo: str
    puede_liquidar: bool
    mensajes_error: List[str]
    estado: str


# ===============================
# METADATA DEL MODULO
# ===============================

__version__ = "3.0.0"
__author__ = "Sistema Preliquidador"
__architecture__ = "Clean Architecture - Domain Layer"

# Total de modelos definidos
__total_modelos__ = 14
