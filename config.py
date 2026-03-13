"""
CONFIGURACIÓN DEL PRELIQUIDADOR DE RETEFUENTE
==========================================

Maneja la configuración de conceptos, tarifas y parámetros del sistema.
"""

import os
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)



# Conceptos exactos con base mínima y tarifa específica
# Estructura: {concepto: {base_pesos: int, tarifa_retencion: float}}
CONCEPTOS_RETEFUENTE = {
    "Compras generales (declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.025
    },
    "Compras generales (no declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Compras con tarjeta débito o crédito": {
        "base_pesos": 0,
        "tarifa_retencion": 0.015
    },
    "Compras de bienes o productos agrícolas o pecuarios sin procesamiento industrial": {
        "base_pesos": 3486000,
        "tarifa_retencion": 0.015
    },
    "Compras de bienes o productos agrícolas o pecuarios con procesamiento industrial (declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.025
    },
    "Compras de bienes o productos agrícolas o pecuarios con procesamiento industrial declarantes (no declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Compras de café pergamino o cereza": {
        "base_pesos": 3486000,
        "tarifa_retencion": 0.005
    },
    "Compras de combustibles derivados del petróleo": {
        "base_pesos": 0,
        "tarifa_retencion": 0.001
    },
    "Enajenación de activos fijos de personas naturales (notarías y tránsito son agentes retenedores)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.01
    },
    "Compras de vehículos": {
        "base_pesos": 0,
        "tarifa_retencion": 0.01
    },
    "Servicios generales (declarantes)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.04
    },
    "Servicios generales (no declarantes)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.06
    },
    "Servicios de transporte de carga": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.01
    },
    "Servicios de transporte nacional de pasajeros por vía terrestre": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Servicios de transporte nacional de pasajeros por vía aérea o marítima": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.01
    },
    "Servicios prestados por empresas de servicios temporales (sobre AIU)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.01
    },
    "Servicios prestados por empresas de vigilancia y aseo (sobre AIU)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.02
    },
    "Servicios integrales de salud prestados por IPS": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.02
    },
    "Arrendamiento de bienes muebles": {
        "base_pesos": 0,
        "tarifa_retencion": 0.04
    },
    "Arrendamiento de bienes inmuebles": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Otros ingresos tributarios (declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.025
    },
    "Otros ingresos tributarios (no declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Honorarios y comisiones por servicios (persona juridica)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.11
    },
     "Honorarios y comisiones por servicios (declarantes)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.11
    },
    "Honorarios y comisiones por servicios (no declarantes)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.10
    },
    "Servicios de hoteles y restaurantes (declarantes)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.035
    },
    "Servicios de hoteles y restaurantes (no declarantes)": {
        "base_pesos": 100000,
        "tarifa_retencion": 0.035
    },
     "Servicios de licenciamiento o derecho de uso de software": {
        "base_pesos": 0,
        "tarifa_retencion": 0.035
    },
       "Intereses o rendimientos financieros": {
        "base_pesos": 0,
        "tarifa_retencion": 0.07
    },
    "Loterías, rifas, apuestas y similares": {
        "base_pesos": 2390000,
        "tarifa_retencion": 0.2
    },
    "Emolumentos eclesiásticos (declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.04
    },
    "Emolumentos eclesiásticos ( no declarantes)": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.035
    },
    "Retención en colocación independiente de juegos de suerte y azar": {
        "base_pesos": 249000,
        "tarifa_retencion": 0.03
    },
     "Contratos de construcción y urbanización.": {
        "base_pesos": 498000,
        "tarifa_retencion": 0.02
    },
    "compra de oro por las sociedades de comercialización internacional.": {
        "base_pesos": 0,
        "tarifa_retencion": 0.025
    },
    "Compras de bienes raíces cuya destinación y uso sea vivienda de habitación (por las primeras $497990000 pesos colombianos)": {
        "base_pesos": 0,
        "tarifa_retencion": 0.01
    },
    "Compras de bienes raíces cuya destinación y uso sea vivienda de habitación (exceso de $497990000 pesos colombianos)": {
        "base_pesos": 497990000,
        "tarifa_retencion": 0.025
    },
    "Compras de bienes raíces cuya destinación y uso sea distinto a vivienda de habitación": {
        "base_pesos": 0,
        "tarifa_retencion": 0.025
    },
    "Servicios de consultoría en informática":{
        "base_pesos":0,
        "tarifa_retencion":0.035
    },
    "Alquiler":{
        "base_pesos": 0,
        "tarifa_retencion": 0.03
    },
    "comision a terceros":{
        "base_pesos": 0,
        "tarifa_retencion": 0.11
    },
    "personal de servicio":{
        "base_pesos": 0,
        "tarifa_retencion": 0.035
    }
}


# ===============================
# CONCEPTOS Y TARIFAS EXTRANJEROS
# ===============================

# Conceptos de retención para pagos al exterior
CONCEPTOS_EXTRANJEROS = {
    "Pagos por intereses, comisiones, honorarios, regalías, arrendamientos, compensaciones por servicios personales, explotación de propiedad industrial, know-how, prestación de servicios, beneficios o regalías de propiedad literaria, artística y científica, explotación de películas cinematográficas y software": {
        "base_pesos": 0,  # Sin base mínima
        "tarifa_normal": 0.20,  # 20%
        "tarifa_convenio": 0.10  # 10%
    },
    "Consultorías, servicios técnicos y de asistencia técnica prestados por personas no residentes o no domiciliadas en Colombia": {
        "base_pesos": 0,
        "tarifa_normal": 0.20,  # 20%
        "tarifa_convenio": 0.10  # 10%
    },
    "Rendimientos financieros realizados a personas no residentes, originados en créditos obtenidos en el exterior por término igual o superior a un (1) año o por intereses o costos financieros del canon de arrendamiento en contratos de leasing con empresas extranjeras sin domicilio en colombia": {
        "base_pesos": 0,
        "tarifa_normal": 0.15,  # 15%
        "tarifa_convenio": 0.10  # 10%
    },
    "Contratos de leasing sobre naves, helicópteros y/o aerodinos, así como sus partes con empresas extranjeras sin domicilio en Colombia": {
        "base_pesos": 0,
        "tarifa_normal": 0.01,  # 1%
        "tarifa_convenio": 0.01  # 1%
    },
    "Rendimientos financieros o intereses realizados a personas no residentes, originados en créditos o valores de contenido crediticio, por término igual o superior a ocho (8) años, destinados a financiación de proyectos de infraestructura bajo esquema de Asociaciones Público-Privadas": {
        "base_pesos": 0,
        "tarifa_normal": 0.05,  # 5%
        "tarifa_convenio": 0.05  # 5%
    },
    "Prima cedida por reaseguros realizados a personas no residentes o no domiciliadas en el país": {
        "base_pesos": 0,
        "tarifa_normal": 0.01,  # 1%
        "tarifa_convenio": 0.01  # 1%
    },
    "Administración, servicios de gestión o dirección empresarial (como planificación, supervisión o coordinación) realizados a personas no residentes o no domiciliadas en el país, tales como casas matrices o entidades vinculadas en el exterior.": {
        "base_pesos": 0,
        "tarifa_normal": 0.33,  # 33%
        "tarifa_convenio": 0.33  # 33%
    }
}

# Países con convenio de doble tributación vigente
PAISES_CONVENIO_DOBLE_TRIBUTACION = [
    "Francia",
    "Italia", 
    "Reino Unido",
    "República Checa",
    "Portugal",
    "India",
    "Corea del Sur",
    "México",
    "Canadá",
    "Suiza",
    "Chile",
    "España"
]

# Países de la Comunidad Andina de Naciones (Decisión 578)
PAISES_COMUNIDAD_ANDINA = [
    "Perú",
    "Ecuador", 
    "Bolivia"
]

# Todos los países con convenio (incluye CAN)
PAISES_CON_CONVENIO = PAISES_CONVENIO_DOBLE_TRIBUTACION + PAISES_COMUNIDAD_ANDINA

# Preguntas para determinar fuente nacional
PREGUNTAS_FUENTE_NACIONAL = [
    "¿El servicio tiene uso o beneficio económico en Colombia?",
    "¿La actividad (servicio) se ejecutó total o parcialmente en Colombia?", 
    "¿El servicio corresponde a asistencia técnica, consultoría o know-how usado en Colombia?",
    "¿El bien vendido o utilizado está ubicado en Colombia?"
]


# ===============================
# CONFIGURACIÓN GENERAL
# ===============================

CONFIG = {
    "archivo_excel": "RETEFUENTE_CONCEPTOS.xlsx",
    "max_archivos": 6,
    "max_tamaño_mb": 50,
    "extensiones_soportadas": [".pdf", ".xlsx", ".xls", ".jpg", ".jpeg", ".png", ".docx", ".doc"],
    "min_caracteres_ocr": 1000,
    "timeout_gemini_segundos": 30,
    "encoding_default": "utf-8"
}

# ===============================
# CONFIGURACIÓN DE NITS ADMINISTRATIVOS
# ===============================

NITS_CONFIGURACION = {
    "800178148": {
        "nombre": "Fiduciaria Colombiana de Comercio Exterior S.A.",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "IVA",
            "RETENCION_ICA",
            "CONTRIBUCION_OBRA_PUBLICA",
            "ESTAMPILLA_UNIVERSIDAD_NACIONAL",
            "IMPUESTO_TIMBRE"
        ]
    },
    "830054060": {
        "nombre": "FIDEICOMISOS SOCIEDAD FIDUCIARIA FIDUCOLDEX",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "IVA",
            "RETENCION_ICA",
            "CONTRIBUCION_OBRA_PUBLICA",
            "ESTAMPILLA_UNIVERSIDAD_NACIONAL",
            "IMPUESTO_TIMBRE"
        ]
    },
    "900649119": {
        "nombre": "PATRIMONIO AUTÓNOMO FONTUR",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "IVA",
            "RETENCION_ICA",
            "CONTRIBUCION_OBRA_PUBLICA",
            "ESTAMPILLA_UNIVERSIDAD_NACIONAL",
            "IMPUESTO_TIMBRE"
        ]
    },
    "901281733": {
        "nombre": "FONDOS DE INVERSIÓN - ABIERTA Y 60 MODERADO",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "RETENCION_ICA"
        ]
    },
    "900566230": {
        "nombre": "CONSORCIO",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "RETENCION_ICA"
        ]
    },
    "901427860": {
        "nombre": "CONSORCIO", 
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "RETENCION_ICA"
        ]
    },
    "900139498": {
        "nombre": "FIC FIDUCOLDEX",
        "impuestos_aplicables": [
            "RETENCION_FUENTE",
            "RETENCION_ICA"
        ]
    }
}

# ===============================
# FUNCIONES PARA GESTIÓN DE NITS
# ===============================

def obtener_nits_disponibles() -> Dict[str, Dict[str, Any]]:
    """Obtiene todos los NITs configurados"""
    return NITS_CONFIGURACION.copy()

def validar_nit_administrativo(nit: str) -> tuple[bool, str, List[str]]:
    """
    Valida si un NIT administrativo existe y retorna su información
    
    Args:
        nit: NIT a validar
        
    Returns:
        tuple: (es_valido, nombre_entidad, impuestos_aplicables)
    """
    nit_limpio = nit.strip()
    
    if nit_limpio in NITS_CONFIGURACION:
        datos = NITS_CONFIGURACION[nit_limpio]
        return True, datos["nombre"], datos["impuestos_aplicables"]
    else:
        return False, "", []

def nit_aplica_retencion_fuente(nit: str) -> bool:
    """
    Verifica si un NIT aplica retención en la fuente
    
    Args:
        nit: NIT a verificar
        
    Returns:
        bool: True si aplica retención en la fuente
    """
    es_valido, _, impuestos = validar_nit_administrativo(nit)
    return es_valido and "RETENCION_FUENTE" in impuestos


# =====================================
# FUNCIONES PARA FACTURACIÓN EXTRANJERA
# =====================================

def obtener_conceptos_extranjeros() -> Dict[str, Dict[str, Any]]:
    """Obtiene todos los conceptos de retención para facturación extranjera"""
    return CONCEPTOS_EXTRANJEROS.copy()
#no se usa
def obtener_conceptos_extranjeros_para_prompt() -> str:
    """Formatea conceptos extranjeros para uso en prompts de Gemini"""
    conceptos_formateados = []
    for concepto, datos in CONCEPTOS_EXTRANJEROS.items():
        tarifa_normal = datos["tarifa_normal"] * 100
        tarifa_convenio = datos["tarifa_convenio"] * 100
        conceptos_formateados.append(
            f"- {concepto}\n  * Tarifa normal: {tarifa_normal}%\n  * Tarifa con convenio: {tarifa_convenio}%"
        )
    return "\n\n".join(conceptos_formateados)
#si se usa
def obtener_paises_con_convenio() -> List[str]:
    """Obtiene la lista de países con convenio de doble tributación"""
    return PAISES_CON_CONVENIO.copy()

def obtener_preguntas_fuente_nacional() -> List[str]:
    """Obtiene las preguntas para determinar fuente nacional"""
    return PREGUNTAS_FUENTE_NACIONAL.copy()
#no se usa 
def es_pais_con_convenio(pais: str) -> bool:
    """Verifica si un país tiene convenio de doble tributación"""
    if not pais:
        return False
    
    pais_normalizado = pais.strip().title()
    return pais_normalizado in PAISES_CON_CONVENIO
#no se usa 
def obtener_tarifa_extranjera(concepto: str, tiene_convenio: bool = False) -> float:
    """Obtiene la tarifa para un concepto de facturación extranjera"""
    
    # Buscar concepto exacto
    if concepto in CONCEPTOS_EXTRANJEROS:
        datos = CONCEPTOS_EXTRANJEROS[concepto]
        return datos["tarifa_convenio"] if tiene_convenio else datos["tarifa_normal"]
    
    # Buscar por similitud (keywords)
    concepto_lower = concepto.lower()
    
    # Mapeo por palabras clave para conceptos extranjeros
    mapeo_keywords = {
        "interes": "Rendimientos financieros realizados a personas no residentes, originados en créditos obtenidos en el exterior por término igual o superior a un (1) año o por intereses o costos financieros del canon de arrendamiento en contratos de leasing con empresas extranjeras",
        "honorario": "Pagos por intereses, comisiones, honorarios, regalías, arrendamientos, compensaciones por servicios personales, explotación de propiedad industrial, know-how, prestación de servicios, beneficios o regalías de propiedad literaria, artística y científica, explotación de películas cinematográficas y software",
        "consultoria": "Consultorías, servicios técnicos y de asistencia técnica prestados por personas no residentes o no domiciliadas en Colombia",
        "asistencia": "Consultorías, servicios técnicos y de asistencia técnica prestados por personas no residentes o no domiciliadas en Colombia",
        "regalias": "Pagos por intereses, comisiones, honorarios, regalías, arrendamientos, compensaciones por servicios personales, explotación de propiedad industrial, know-how, prestación de servicios, beneficios o regalías de propiedad literaria, artística y científica, explotación de películas cinematográficas y software",
        "software": "Pagos por intereses, comisiones, honorarios, regalías, arrendamientos, compensaciones por servicios personales, explotación de propiedad industrial, know-how, prestación de servicios, beneficios o regalías de propiedad literaria, artística y científica, explotación de películas cinematográficas y software",
        "leasing": "Contratos de leasing sobre naves, helicópteros y/o aerodinos, así como sus partes con empresas extranjeras sin domicilio en Colombia",
        "reaseguro": "Prima cedida por reaseguros realizados a personas no residentes o no domiciliadas en el país",
        "administracion": "Administración o dirección realizados a personas no residentes o no domiciliadas en el país",
        "direccion": "Administración o dirección realizados a personas no residentes o no domiciliadas en el país"
    }
    
    for keyword, concepto_mapped in mapeo_keywords.items():
        if keyword in concepto_lower:
            datos = CONCEPTOS_EXTRANJEROS[concepto_mapped]
            return datos["tarifa_convenio"] if tiene_convenio else datos["tarifa_normal"]
    
    # Por defecto, usar el primer concepto (más general)
    primer_concepto = list(CONCEPTOS_EXTRANJEROS.keys())[0]
    datos = CONCEPTOS_EXTRANJEROS[primer_concepto]
    return datos["tarifa_convenio"] if tiene_convenio else datos["tarifa_normal"]

# ===============================
# ARTÍCULO 383 - PERSONAS NATURALES
# ===============================

# Valores para la vigencia 2025
UVT_2025 = 52374  # Valor UVT 2025 en pesos
SMMLV_2025 = 1750905   # Salario Mínimo Mensual Legal Vigente 2025

# Conceptos que aplican para Artículo 383 ET
CONCEPTOS_ARTICULO_383 = [
    "Honorarios y comisiones por servicios (declarantes)",
    "Honorarios y comisiones por servicios (no declarantes)", 
    "Prestacion de servicios",
    "Comisiones",
    "Viaticos"
    # Nota: Incluye honorarios, prestación de servicios, diseños, comisiones, viáticos
]

# Tarifas progresivas Artículo 383 por rangos UVT
TARIFAS_ARTICULO_383 = [
    {"desde_uvt": 0, "hasta_uvt": 95, "tarifa": 0.00},      # 0%
    {"desde_uvt": 95, "hasta_uvt": 150, "tarifa": 0.19},    # 19%
    {"desde_uvt": 150, "hasta_uvt": 360, "tarifa": 0.28},   # 28%
    {"desde_uvt": 360, "hasta_uvt": 640, "tarifa": 0.33},   # 33%
    {"desde_uvt": 640, "hasta_uvt": 945, "tarifa": 0.35},   # 35%
    {"desde_uvt": 945, "hasta_uvt": 2300, "tarifa": 0.37},  # 37%
    {"desde_uvt": 2300, "hasta_uvt": float('inf'), "tarifa": 0.39}  # 39%
]

# Límites de deducciones Artículo 383 (en UVT mensuales)
LIMITES_DEDUCCIONES_ART383 = {
    "intereses_vivienda": 100,  # Hasta 100 UVT/mes
    "dependientes_economicos": 32,  # Hasta 32 UVT/mes o 10% del ingreso
    "medicina_prepagada": 16,  # Hasta 16 UVT/mes
    "rentas_exentas_uvt_anual": 3800,  # Hasta 3800 UVT/año
    "rentas_exentas_porcentaje": 0.25,  # Hasta 25% del ingreso mensual
    "deducciones_maximas_porcentaje": 0.40,  # Máximo 40% del ingreso bruto
    "seguridad_social_porcentaje": 0.40  # 40% del ingreso para seguridad social
}

# ===============================
# FUNCIONES ARTÍCULO 383
# ===============================

def es_concepto_articulo_383(concepto: str) -> bool:
    """Verifica si un concepto aplica para Artículo 383"""
    return concepto in CONCEPTOS_ARTICULO_383

def obtener_tarifa_articulo_383(base_gravable_pesos: float) -> float:
    """Obtiene la tarifa del Artículo 383 según la base gravable en pesos"""
    base_gravable_uvt = base_gravable_pesos / UVT_2025
    
    for rango in TARIFAS_ARTICULO_383:
        if rango["desde_uvt"] <= base_gravable_uvt < rango["hasta_uvt"]:
            return rango["tarifa"]
    
    # Si no encuentra rango, usar la última tarifa (39%)
    return TARIFAS_ARTICULO_383[-1]["tarifa"]

def calcular_limite_deduccion(tipo_deduccion: str, ingreso_bruto: float, valor_deducido: float) -> float:
    """Calcula el límite permitido para una deducción específica"""
    limites = LIMITES_DEDUCCIONES_ART383
    
    if tipo_deduccion == "intereses_vivienda":
        return min(valor_deducido, limites["intereses_vivienda"] * UVT_2025)
    
    elif tipo_deduccion == "dependientes_economicos":
        limite_porcentaje = ingreso_bruto * 0.10
        limite_uvt = limites["dependientes_economicos"] * UVT_2025
        return min(valor_deducido, limite_porcentaje, limite_uvt)
    
    elif tipo_deduccion == "medicina_prepagada":
        return min(valor_deducido, limites["medicina_prepagada"] * UVT_2025)
    
    elif tipo_deduccion == "rentas_exentas":
        #AGREGAR CONDICION DE DIVIDIR EL MONTO IDENTIFICADO POR LA IA POR 12 
        limite_porcentaje = ingreso_bruto * limites["rentas_exentas_porcentaje"]
        limite_uvt_mensual = (limites["rentas_exentas_uvt_anual"] * UVT_2025) / 12
        return min(valor_deducido, limite_porcentaje, limite_uvt_mensual)
    
    return 0

def obtener_constantes_articulo_383() -> Dict[str, Any]:
    """Obtiene todas las constantes del Artículo 383 para uso en prompts"""
    return {
        "uvt_2025": UVT_2025,
        "smmlv_2025": SMMLV_2025,
        "conceptos_aplicables": CONCEPTOS_ARTICULO_383,
        "tarifas": TARIFAS_ARTICULO_383,
        "limites_deducciones": LIMITES_DEDUCCIONES_ART383
    }

# ===============================
# CONFIGURACIÓN IMPUESTOS ESPECIALES INTEGRADOS
# ===============================

# IMPORTANTE: Desde 2025, estampilla pro universidad nacional y contribución
# a obra pública aplican para los MISMOS códigos de negocio

# Códigos de negocio válidos para AMBOS impuestos (estampilla + obra pública)
# Estos códigos identifican a los negocios que aplican estos dos impuestos
CODIGOS_NEGOCIO_ESTAMPILLA = {
    69164: "PATRIMONIO AUTONOMO INNPULSA COLOMBIA",
    69166: "PATRIMONIO AUTONOMO COLOMBIA PRODUCTIVA",
    99664: "PATRIMONIO AUTÓNOMO FONDO MUJER EMPRENDE"
}

# Alias para compatibilidad hacia atrás - MISMO contenido
CODIGOS_NEGOCIO_OBRA_PUBLICA = CODIGOS_NEGOCIO_ESTAMPILLA.copy()

# NITs administrativos válidos para Estampilla Universidad y Obra Pública
# Estos NITs determinan si se deben liquidar estos impuestos
NITS_ADMINISTRATIVOS_VALIDOS = {
    "800178148": "Fiduciaria Colombiana de Comercio Exterior S.A. (Fiduciaria y Encargos)",
    "900649119": "PATRIMONIO AUTONOMO FONTUR",
    "830054060": "FIDEICOMISOS SOCIEDAD FIDUCIARIA FIDUCOLDEX"
}

# NITs que requieren validación adicional por código de negocio
# Estos NITs solo aplican si además el código de negocio está en CODIGOS_NEGOCIO_ESTAMPILLA
NITS_REQUIEREN_VALIDACION_CODIGO = {"830054060"}

# DEPRECATED: Mantener por compatibilidad legacy (NO USAR en nuevo código)
NITS_ESTAMPILLA_UNIVERSIDAD = {}
NITS_CONTRIBUCION_OBRA_PUBLICA = {}
TERCEROS_RECURSOS_PUBLICOS = {
    "PATRIMONIO AUTONOMO INNPULSA COLOMBIA": True,
    "PATRIMONIO AUTONOMO COLOMBIA PRODUCTIVA": True,
    "PATRIMONIO AUTÓNOMO FONDO MUJER EMPRENDE": True
}

# Objetos de contrato que aplican para estampilla universidad
OBJETOS_CONTRATO_ESTAMPILLA = {
    "contrato_obra": {
        "palabras_clave": ["construcción", "mantenimiento", "instalación","TRABAJO MATERIAL"],
        "aplica": True
    },
    "interventoria": {
        "palabras_clave": ["interventoría", "interventoria"],
        "aplica": True
    },
    "servicios_conexos_obra": {
        "palabras_clave": [
            "estudios necesarios para la ejecución de proyectos de inversión",
            "estudios de diagnóstico",
            "estudios de prefactibilidad",
            "factibilidad para programas o proyectos",
            "asesorías tecnicas de coordinación",
            "asesorías de control",
            "asesorías de supervision",
            "asesoria",
            "gerencia de obra",
            "gerencia de proyectos dirección",
            "programación ejecución de diseño, planos, anteproyectos y proyectos",
            "diseño",
            "operación",
            "interventoria mantenimiento"
        ],
        "aplica": True
    }
}

# Objetos de contrato que aplican para contribución a obra pública (SOLO OBRA)
OBJETOS_CONTRATO_OBRA_PUBLICA = {
    "contrato_obra": {
        "palabras_clave": ["construcción", "mantenimiento", "instalación", "TRABAJO MATERIAL"],
        "aplica": True
    }
    #  IMPORTANTE: Solo aplica para contrato de obra, NO interventoría ni servicios conexos
}

# Rangos UVT y tarifas para estampilla pro universidad nacional
RANGOS_ESTAMPILLA_UNIVERSIDAD = [
    {"desde_uvt": 26, "hasta_uvt": 52652, "tarifa": 0.005},      # 0.5%
    {"desde_uvt": 52652, "hasta_uvt": 157904, "tarifa": 0.01},   # 1.0%
    {"desde_uvt": 157904, "hasta_uvt": float('inf'), "tarifa": 0.02}  # 2.0%
]

# ===============================
# FUNCIONES ESTAMPILLA UNIVERSIDAD
# ===============================

def validar_nit_administrativo_para_impuestos(nit_administrativo: str, codigo_negocio: int) -> Dict[str, Any]:
    """
    Valida si un NIT administrativo aplica para estampilla y obra pública.

    SRP: Solo valida NITs administrativos según reglas de negocio

    Reglas de validación:
    1. El NIT debe estar en NITS_ADMINISTRATIVOS_VALIDOS
    2. Si el NIT es 830054060, además debe validar código de negocio
    3. Los demás NITs (800178148, 900649119) aplican directamente

    Args:
        nit_administrativo: NIT del administrativo extraído de la base de datos
        codigo_negocio: Código único del negocio

    Returns:
        Dict con información de validación:
        {
            "nit_valido": bool,
            "requiere_validacion_codigo": bool,
            "codigo_valido": bool (si aplica),
            "razon_no_aplica": str (si no aplica),
            "nombre_entidad": str
        }
    """
    # Normalizar NIT (remover puntos y guiones)
    nit_normalizado = nit_administrativo.replace(".", "").replace("-", "").strip()

    # Verificar si el NIT está en la lista de NITs válidos
    if nit_normalizado not in NITS_ADMINISTRATIVOS_VALIDOS:
        return {
            "nit_valido": False,
            "requiere_validacion_codigo": False,
            "codigo_valido": False,
            "razon_no_aplica": f"El NIT {nit_administrativo} no está autorizado para liquidar estos impuestos",
            "nombre_entidad": None
        }

    nombre_entidad = NITS_ADMINISTRATIVOS_VALIDOS[nit_normalizado]

    # Si el NIT requiere validación adicional de código de negocio
    if nit_normalizado in NITS_REQUIEREN_VALIDACION_CODIGO:
        codigo_valido = codigo_negocio in CODIGOS_NEGOCIO_ESTAMPILLA

        if not codigo_valido:
            return {
                "nit_valido": True,
                "requiere_validacion_codigo": True,
                "codigo_valido": False,
                "razon_no_aplica": f"El NIT {nit_administrativo} ({nombre_entidad}) requiere que el código de negocio sea uno de los patrimonios autónomos válidos (69164, 69166, 99664)",
                "nombre_entidad": nombre_entidad
            }

        return {
            "nit_valido": True,
            "requiere_validacion_codigo": True,
            "codigo_valido": True,
            "razon_no_aplica": None,
            "nombre_entidad": nombre_entidad
        }

    # NITs que aplican directamente sin validación de código
    return {
        "nit_valido": True,
        "requiere_validacion_codigo": False,
        "codigo_valido": True,  # No requiere validación, por lo tanto es válido
        "razon_no_aplica": None,
        "nombre_entidad": nombre_entidad
    }

def codigo_negocio_aplica_estampilla_universidad(codigo_negocio: int) -> bool:
    """
    Verifica si un código de negocio aplica para estampilla pro universidad nacional.

    SRP: Solo valida si el código está en la lista de negocios válidos

    Args:
        codigo_negocio: Código único del negocio

    Returns:
        bool: True si el código aplica para estampilla universidad
    """
    return codigo_negocio in CODIGOS_NEGOCIO_ESTAMPILLA

def codigo_negocio_aplica_obra_publica(codigo_negocio: int) -> bool:
    """
    Verifica si un código de negocio aplica para contribución a obra pública.

    SRP: Solo valida si el código está en la lista de negocios válidos

    Args:
        codigo_negocio: Código único del negocio

    Returns:
        bool: True si el código aplica para contribución a obra pública
    """
    return codigo_negocio in CODIGOS_NEGOCIO_OBRA_PUBLICA

# DEPRECATED: Mantener por compatibilidad legacy
def nit_aplica_estampilla_universidad(nit: str) -> bool:
    """DEPRECATED: Usar codigo_negocio_aplica_estampilla_universidad en su lugar"""
    return False  # Ya no se valida por NIT

def es_tercero_recursos_publicos(nombre_tercero: str) -> bool:
    """Verifica si un tercero administra recursos públicos"""
    nombre_upper = nombre_tercero.upper().strip()
    return nombre_upper in TERCEROS_RECURSOS_PUBLICOS

def obtener_tarifa_estampilla_universidad(
    valor_contrato_pesos: float,
    database_manager=None
) -> Dict[str, Any]:
    """
    Obtiene la tarifa de estampilla según el valor del contrato en pesos.

    ESTRATEGIA DE OBTENCION v3.0:
    1. Si database_manager esta disponible: consultar desde BD Nexura
    2. Si falla o no disponible: ERROR (no fallback a hardcoded)

    PRINCIPIOS SOLID:
    - SRP: Solo busca rango UVT aplicable (no accede a BD directamente)
    - DIP: Depende de abstraccion DatabaseInterface

    Args:
        valor_contrato_pesos: Valor del contrato en pesos colombianos
        database_manager: DatabaseManager para consultar BD (opcional para compatibilidad)

    Returns:
        Dict con estructura:
        {
            "tarifa": float,                # Multiplicador (0.005 = 0.5%)
            "rango_desde_uvt": float,       # Inicio del rango
            "rango_hasta_uvt": float,       # Fin del rango (float('inf') para infinito)
            "valor_contrato_uvt": float,    # Valor del contrato en UVT
            "uvt_2025": int,                # Valor UVT vigente
            "fuente": str                   # 'database' o 'error'
        }

    Raises:
        ValueError: Si database_manager es None o si falla la consulta a BD
    """
    global _cache_rangos_estampilla_db, _cache_timestamp_estampilla

    # Calcular valor en UVT
    valor_uvt = valor_contrato_pesos / UVT_2025

    # VALIDAR QUE DATABASE_MANAGER ESTE DISPONIBLE
    if database_manager is None:
        error_msg = (
            "database_manager es requerido para obtener tarifas de estampilla universidad. "
            "No se utiliza fallback a valores hardcodeados."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # OBTENER RANGOS DESDE BASE DE DATOS (con cache)
    if _cache_rangos_estampilla_db is None:
        logger.info("Obteniendo rangos de estampilla universidad desde base de datos")
        resultado = database_manager.obtener_rangos_estampilla_universidad()

        if not resultado.get('success', False) or not resultado.get('data'):
            error_msg = (
                f"No se pudo obtener rangos de estampilla desde BD: "
                f"{resultado.get('message', 'Error desconocido')}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Guardar en cache
        _cache_rangos_estampilla_db = resultado['data']
        _cache_timestamp_estampilla = datetime.now()

        logger.info(
            f"Rangos estampilla obtenidos y cacheados: "
            f"{len(_cache_rangos_estampilla_db)} rangos disponibles"
        )
    else:
        logger.debug("Usando rangos de estampilla desde cache")

    # BUSCAR RANGO APLICABLE
    rangos = _cache_rangos_estampilla_db

    for rango in rangos:
        desde_uvt = rango['desde_uvt']
        hasta_uvt = rango['hasta_uvt']

        # Verificar si valor_uvt esta en este rango
        if desde_uvt <= valor_uvt < hasta_uvt:
            logger.debug(
                f"Rango encontrado para {valor_uvt:.2f} UVT: "
                f"{desde_uvt} - {hasta_uvt} (tarifa: {rango['tarifa']*100:.1f}%)"
            )

            return {
                "tarifa": rango["tarifa"],
                "rango_desde_uvt": desde_uvt,
                "rango_hasta_uvt": hasta_uvt,
                "valor_contrato_uvt": valor_uvt,
                "uvt_2025": UVT_2025,
                "fuente": "database"
            }

    # Si no se encuentra rango exacto, determinar si es menor o mayor a los rangos
    if rangos:
        primer_rango = min(rangos, key=lambda r: r['desde_uvt'])
        ultimo_rango = max(rangos, key=lambda r: r['desde_uvt'])

        # Si el valor es menor al primer rango (< 26 UVT), NO APLICA el impuesto
        if valor_uvt < primer_rango['desde_uvt']:
            logger.info(
                f"Valor {valor_uvt:.2f} UVT es menor al mínimo de {primer_rango['desde_uvt']} UVT. "
                f"Estampilla Universidad NO APLICA para contratos menores a {primer_rango['desde_uvt']} UVT."
            )
            raise ValueError(
                f"NO_APLICA_ESTAMPILLA_UNIVERSIDAD: "
                f"Contrato de {valor_uvt:.2f} UVT es menor al mínimo requerido de {primer_rango['desde_uvt']} UVT"
            )

        # Si el valor es mayor al último rango, usar el último rango
        elif valor_uvt >= ultimo_rango['desde_uvt']:
            logger.debug(
                f"Valor {valor_uvt:.2f} UVT está en el rango mayor (>= {ultimo_rango['desde_uvt']} UVT), "
                f"usando tarifa: {ultimo_rango['tarifa']*100:.1f}%"
            )
            rango_aplicable = ultimo_rango

            return {
                "tarifa": rango_aplicable["tarifa"],
                "rango_desde_uvt": rango_aplicable["desde_uvt"],
                "rango_hasta_uvt": rango_aplicable["hasta_uvt"],
                "valor_contrato_uvt": valor_uvt,
                "uvt_2025": UVT_2025,
                "fuente": "database"
            }

    # ERROR: No hay rangos disponibles
    error_msg = "No se encontraron rangos de estampilla universidad en base de datos"
    logger.error(error_msg)
    raise ValueError(error_msg)

def limpiar_cache_estampilla_universidad():
    """
    Limpia el cache de rangos estampilla universidad.

    Util cuando se necesita forzar una recarga desde la base de datos.

    SRP: Solo limpia cache de rangos estampilla

    Example:
        >>> limpiar_cache_estampilla_universidad()
        >>> config = obtener_tarifa_estampilla_universidad(1000000, db_manager)
    """
    global _cache_rangos_estampilla_db, _cache_timestamp_estampilla
    _cache_rangos_estampilla_db = None
    _cache_timestamp_estampilla = None
    logger.info("Cache de rangos estampilla universidad limpiado")

def obtener_configuracion_estampilla_universidad() -> Dict[str, Any]:
    """
    Obtiene toda la configuración de estampilla para uso en prompts.

    SRP: Solo retorna configuración consolidada

    Returns:
        Dict con configuración completa de estampilla universidad
    """
    return {
        "codigos_negocio_validos": CODIGOS_NEGOCIO_ESTAMPILLA,
        "terceros_recursos_publicos": list(TERCEROS_RECURSOS_PUBLICOS.keys()),
        "objetos_contrato": OBJETOS_CONTRATO_ESTAMPILLA,
        "rangos_uvt": RANGOS_ESTAMPILLA_UNIVERSIDAD,
        "uvt_2025": UVT_2025
    }

# ===============================
# FUNCIONES CONTRIBUCIÓN A OBRA PÚBLICA
# ===============================

# DEPRECATED: Mantener por compatibilidad legacy
def nit_aplica_contribucion_obra_publica(nit: str) -> bool:
    """DEPRECATED: Usar codigo_negocio_aplica_obra_publica en su lugar"""
    return False  # Ya no se valida por NIT

def calcular_contribucion_obra_publica(valor_factura_sin_iva: float, porcentaje_participacion: float = 100.0) -> float:
    """Calcula la contribución a obra pública del 5%
    
    Args:
        valor_factura_sin_iva: Valor de la factura sin IVA
        porcentaje_participacion: % de participación (para consorcios)
    
    Returns:
        float: Valor de la contribución a obra pública
    """
    tarifa_fija = 0.05  # 5% fijo
    participacion_decimal = porcentaje_participacion / 100.0
    return valor_factura_sin_iva * tarifa_fija * participacion_decimal

def obtener_configuracion_obra_publica() -> Dict[str, Any]:
    """
    Obtiene toda la configuración de obra pública para uso en prompts.

    SRP: Solo retorna configuración consolidada

    Returns:
        Dict con configuración completa de contribución a obra pública
    """
    return {
        "codigos_negocio_validos": CODIGOS_NEGOCIO_OBRA_PUBLICA,
        "terceros_recursos_publicos": list(TERCEROS_RECURSOS_PUBLICOS.keys()),
        "objetos_contrato": OBJETOS_CONTRATO_OBRA_PUBLICA,
        "tarifa_fija": 0.05,  # 5%
        "uvt_2025": UVT_2025
    }

# ===============================
# FUNCIÓN INTEGRADA DE DETECCIÓN AUTOMÁTICA
# ===============================

def detectar_impuestos_aplicables_por_codigo(codigo_negocio: int, nombre_negocio: str = None, nit_administrativo: str = None, business_service = None) -> Dict[str, Any]:
    """
    Detecta automáticamente qué impuestos aplican según el código de negocio y NIT administrativo.

    SRP: Solo detecta y estructura información de impuestos aplicables
    DIP: Recibe business_service como dependencia inyectada

    FLUJO DE VALIDACIÓN (v3.1):
    1. Validar NIT administrativo (si se proporciona)
    2. Validar código de negocio
    3. NUEVO: Validar tipo de recurso (Públicos/Privados) en BD
    4. Retornar resultado consolidado

    Args:
        codigo_negocio: Código único del negocio
        nombre_negocio: Nombre del negocio (opcional, para logging)
        nit_administrativo: NIT del administrativo extraído de la base de datos (obligatorio)
        business_service: Servicio de datos de negocio para validar tipo de recurso (DIP)

    Returns:
        Dict con información de qué impuestos aplican, incluyendo validaciones de NIT y tipo de recurso

    Notas:
        - Si no se proporciona nit_administrativo, solo valida por código de negocio (compatibilidad)
        - Si se proporciona nit_administrativo, valida PRIMERO el NIT, DESPUÉS el código
        - Si se proporciona business_service, valida tipo de recurso (Públicos/Privados) en BD
    """
    nombre_registrado = CODIGOS_NEGOCIO_ESTAMPILLA.get(codigo_negocio, nombre_negocio or "Desconocido")


    # VALIDACIÓN POR NIT ADMINISTRATIVO
    # La función validar_nit_administrativo_para_impuestos() ya hace TODA la validación:
    # - Para NITs 800178148, 900649119: Solo valida NIT (aplican directamente)
    # - Para NIT 830054060: Valida NIT + Código internamente
    validacion_nit = validar_nit_administrativo_para_impuestos(nit_administrativo, codigo_negocio)

    # Si la validación del NIT falló, NO aplicar ningún impuesto
    if not validacion_nit["codigo_valido"]:
        # El NIT no es válido O el código no es válido para NIT 830054060
        return {
            "codigo_negocio": codigo_negocio,
            "nombre_negocio": nombre_registrado,
            "aplica_estampilla_universidad": False,
            "aplica_contribucion_obra_publica": False,
            "impuestos_aplicables": [],
            "procesamiento_paralelo": False,
            "nombre_entidad_estampilla": None,
            "nombre_entidad_obra_publica": None,
            "validacion_nit": validacion_nit,
            "razon_no_aplica_estampilla": validacion_nit["razon_no_aplica"],
            "razon_no_aplica_obra_publica": validacion_nit["razon_no_aplica"]
        }

    # Si llegamos aquí, el NIT es válido (y el código también si era necesario validarlo)

    # ===================================================================
    # VALIDACIÓN 3: TIPO DE RECURSO (PÚBLICOS/PRIVADOS) - NUEVA v3.1
    # ===================================================================
    # Si business_service está disponible, validar tipo de recurso del negocio
    if business_service:
        logger.info(f"Validando tipo de recurso para código de negocio {codigo_negocio}")

        try:
            validacion_recurso = business_service.validar_tipo_recurso_negocio(codigo_negocio)

            # CASO 1: No aplica porque administra recursos privados
            if validacion_recurso.get("tipo_recurso") == "Privados":
                logger.info(f"Negocio {codigo_negocio} administra recursos privados - No aplican impuestos especiales")
                return {
                    "codigo_negocio": codigo_negocio,
                    "nombre_negocio": nombre_registrado,
                    "aplica_estampilla_universidad": False,
                    "aplica_contribucion_obra_publica": False,
                    "impuestos_aplicables": [],
                    "procesamiento_paralelo": False,
                    "nombre_entidad_estampilla": None,
                    "nombre_entidad_obra_publica": None,
                    "validacion_nit": validacion_nit,
                    "validacion_recurso": validacion_recurso,  # Incluir resultado completo
                    "razon_no_aplica_estampilla": validacion_recurso.get("razon"),
                    "razon_no_aplica_obra_publica": validacion_recurso.get("razon")
                }

            # CASO 2: No parametrizado o error técnico
            elif not validacion_recurso.get("success"):
                logger.warning(f"No se pudo validar tipo de recurso para código {codigo_negocio}: {validacion_recurso.get('observaciones')}")
                return {
                    "codigo_negocio": codigo_negocio,
                    "nombre_negocio": nombre_registrado,
                    "aplica_estampilla_universidad": False,
                    "aplica_contribucion_obra_publica": False,
                    "impuestos_aplicables": [],
                    "procesamiento_paralelo": False,
                    "nombre_entidad_estampilla": None,
                    "nombre_entidad_obra_publica": None,
                    "validacion_nit": validacion_nit,
                    "validacion_recurso": validacion_recurso,  # Incluir resultado completo
                    "estado_especial": validacion_recurso.get("estado","preliquidacion_sin_finalizar"),
                    "razon_no_aplica_estampilla": validacion_recurso.get("observaciones"),
                    "razon_no_aplica_obra_publica": validacion_recurso.get("observaciones")
                }

            # CASO 3: Recursos Públicos - Continuar con flujo normal
            logger.info(f"Negocio {codigo_negocio} administra recursos públicos - Aplican impuestos especiales")

        except Exception as e:
            # Error inesperado en validación de recurso
            logger.error(f"Error inesperado validando tipo de recurso: {e}")
            return {
                "codigo_negocio": codigo_negocio,
                "nombre_negocio": nombre_registrado,
                "aplica_estampilla_universidad": False,
                "aplica_contribucion_obra_publica": False,
                "impuestos_aplicables": [],
                "procesamiento_paralelo": False,
                "nombre_entidad_estampilla": None,
                "nombre_entidad_obra_publica": None,
                "validacion_nit": validacion_nit,
                "validacion_recurso": {
                    "success": False,
                    "error": str(e),
                    "observaciones": f"Error técnico al validar tipo de recurso: {str(e)}"
                },
                "estado_especial": "preliquidacion_sin_finalizar",
                "razon_no_aplica_estampilla": f"Error técnico al validar tipo de recurso: {str(e)}",
                "razon_no_aplica_obra_publica": f"Error técnico al validar tipo de recurso: {str(e)}"
            }

    # Si no hay business_service, continuar sin validar tipo de recurso (compatibilidad)
    else:
        logger.warning("BusinessService no disponible - no se validó tipo de recurso")

    # APLICAR AMBOS IMPUESTOS (todas las validaciones pasaron)
    return {
        "codigo_negocio": codigo_negocio,
        "nombre_negocio": nombre_registrado,
        "aplica_estampilla_universidad": True,
        "aplica_contribucion_obra_publica": True,
        "impuestos_aplicables": ["ESTAMPILLA_UNIVERSIDAD", "CONTRIBUCION_OBRA_PUBLICA"],
        "procesamiento_paralelo": True,
        "nombre_entidad_estampilla": nombre_registrado,
        "nombre_entidad_obra_publica": nombre_registrado,
        "validacion_nit": validacion_nit,
        "validacion_recurso": validacion_recurso if business_service else None,
        "razon_no_aplica_estampilla": None,
        "razon_no_aplica_obra_publica": None
    }


# ===============================
# CONFIGURACIÓN IVA Y RETEIVA
# ===============================

# NITs de la fiduciaria que aplican IVA y ReteIVA
NITS_IVA_RETEIVA = {
    "800178148": {
        "nombre": "Fiduciaria Colombiana de Comercio Exterior S.A.",
        "aplica_iva": True,
        "aplica_reteiva": True
    },
    "830054060": {
        "nombre": "FIDEICOMISOS SOCIEDAD FIDUCIARIA FIDUCOLDEX",
        "aplica_iva": True,
        "aplica_reteiva": True
    },
    "900649119": {
        "nombre": "PATRIMONIO AUTÓNOMO FONTUR",
        "aplica_iva": True,
        "aplica_reteiva": True
    }
}


# Configuración de tarifas ReteIVA
CONFIG_RETEIVA = {
    "tarifa_fuente_nacional": 0.15,    # 15% para fuente nacional
    "tarifa_fuente_extranjera": 1.0,   # 100% para fuente extranjera
    "porcentaje_iva_extranjero_esperado": 0.19  # 19% IVA esperado para extranjeros
}

# ===============================
# CONFIGURACION TASA PRODEPORTE
# ===============================

# Diccionario de rubros presupuestales con sus tarifas y centros de costo
# RUBRO_PRESUPUESTO: Codigo del rubro presupuestal (primeros 2 digitos deben ser 28)
# TARIFA: Tarifa aplicable (decimal)
# CENTRO_COSTO: Centro de costo asociado
# MUNICIPIO_DEPARTAMENTO: Ubicacion geografica
# ===============================
# TASA PRODEPORTE - MIGRADO A DATABASE.PY
# ===============================
#
# NOTA: Configuracion de rubros presupuestales migrada a base de datos desde v3.0
#
# ANTES (v2.x):
#   - Diccionario RUBRO_PRESUPUESTAL hardcodeado (6 rubros)
#   - Funciones: rubro_existe_en_presupuesto(), obtener_datos_rubro(), validar_rubro_presupuestal()
#
# AHORA (v3.0+):
#   - Datos dinamicos desde Nexura API
#   - Metodo: db.obtener_datos_rubro_tasa_prodeporte(codigo_rubro)
#   - Ubicacion: database/database.py (lineas 86-110 DatabaseInterface, 764-789 SupabaseDatabase, 2398-2630 NexuraAPIDatabase)
#   - Parsing automatico: "Si aplica 1,5%" -> 0.015
#
# Ver: CHANGELOG.md seccion "v3.0.0 - Migracion Tasa Prodeporte a Base de Datos"
#
# ===============================

# NITs que aplican Tasa Prodeporte
NITS_TASA_PRODEPORTE = {
    "900649119": {
        "nombre": "PATRIMONIO AUTÓNOMO FONTUR",
        "aplica_tasa_prodeporte": True
    }
}

def nit_aplica_tasa_prodeporte(nit: str) -> bool:
    """Verifica si un NIT aplica para análisis de Tasa Prodeporte"""
    return nit in NITS_TASA_PRODEPORTE

# ===============================
# FUNCIONES IVA Y RETEIVA
# ===============================

def nit_aplica_iva_reteiva(nit: str) -> bool:
    """Verifica si un NIT aplica para análisis de IVA y ReteIVA"""
    return nit in NITS_IVA_RETEIVA

# ===============================
# FUNCIONES ICA (INDUSTRIA Y COMERCIO)
# ===============================

def nit_aplica_ICA(nit: str) -> bool:
    """
    Verifica si un NIT aplica para retención de ICA (Industria y Comercio).

    PRINCIPIO SRP: Responsabilidad única de validación de NIT para ICA
    PRINCIPIO DIP: Depende de la abstracción NITS_CONFIGURACION

    Args:
        nit: NIT a verificar

    Returns:
        bool: True si el NIT aplica para ICA
    """
    es_valido, _, impuestos = validar_nit_administrativo(nit)
    return es_valido and "RETENCION_ICA" in impuestos

def nit_aplica_timbre(nit: str) -> bool:
    """
    Verifica si un NIT aplica para Impuesto al Timbre.

    PRINCIPIO SRP: Responsabilidad unica de validacion de NIT para Timbre
    PRINCIPIO DIP: Depende de la abstraccion NITS_CONFIGURACION

    NITs que aplican timbre:
    - 800178148: Fiduciaria Colombiana de Comercio Exterior S.A.
    - 900649119: Fondo Nacional de Turismo FONTUR
    - 830054060: Fideicomiso Sociedad Fiduciaria Fiducoldex

    Args:
        nit: NIT a verificar

    Returns:
        bool: True si el NIT aplica para Impuesto al Timbre
    """
    es_valido, _, impuestos = validar_nit_administrativo(nit)
    return es_valido and "IMPUESTO_TIMBRE" in impuestos

# Cache global para configuracion IVA desde base de datos
_cache_config_iva_db = None
_cache_timestamp_iva = None

# Cache global para rangos estampilla universidad desde base de datos
_cache_rangos_estampilla_db = None
_cache_timestamp_estampilla = None


def obtener_configuracion_iva(database_manager=None, usar_cache: bool = True) -> Dict[str, Any]:
    """
    Obtiene toda la configuracion de IVA desde base de datos Nexura con cache.

    ESTRATEGIA DE OBTENCION:
    1. Intenta obtener desde base de datos Nexura (OBLIGATORIO - database_manager requerido)
    2. Implementa cache para evitar llamadas repetidas a la base de datos
    3. Si falla, lanza excepcion

    PRINCIPIOS SOLID APLICADOS:
    - SRP: Solo obtiene configuracion de IVA
    - OCP: Extensible para nuevas fuentes de datos
    - DIP: Depende de abstraccion (database_manager)

    Args:
        database_manager: DatabaseManager REQUERIDO para obtener datos desde BD
        usar_cache: Si True, usa cache de configuracion IVA (default: True)

    Returns:
        Dict con estructura:
        {
            'nits_validos': Dict,
            'bienes_no_causan_iva': Dict[str, str],
            'bienes_exentos_iva': Dict[str, str],
            'servicios_excluidos_iva': Dict[str, str],
            'config_reteiva': Dict,
            'fuente': str  # siempre 'database'
        }

    Raises:
        ValueError: Si database_manager es None o si falla la obtencion desde BD

    Example:
        >>> from database.setup import inicializar_database_manager
        >>> db_manager, _ = inicializar_database_manager()
        >>> config = obtener_configuracion_iva(db_manager)
        >>> print(config['fuente'])  # 'database'
    """
    global _cache_config_iva_db, _cache_timestamp_iva

    # 1. VERIFICAR CACHE (si esta habilitado)
    if usar_cache and _cache_config_iva_db is not None:
        logger.debug("Usando configuracion IVA desde cache")
        return _cache_config_iva_db

    # 2. VALIDAR QUE DATABASE_MANAGER ESTE DISPONIBLE
    if database_manager is None:
        error_msg = "database_manager es requerido para obtener configuracion IVA"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # 3. OBTENER DESDE BASE DE DATOS
    try:
        logger.info("Obteniendo configuracion IVA desde base de datos")
        resultado = database_manager.obtener_configuracion_iva_db()

        if resultado.get('success', False) and resultado.get('data'):
            datos_db = resultado['data']

            # Construir configuracion completa con datos de BD
            config_completa = {
                'nits_validos': NITS_IVA_RETEIVA,
                'bienes_no_causan_iva': datos_db.get('bienes_no_causan_iva', {}),
                'bienes_exentos_iva': datos_db.get('bienes_exentos_iva', {}),
                'servicios_excluidos_iva': datos_db.get('servicios_excluidos_iva', {}),
                'config_reteiva': CONFIG_RETEIVA,
                'fuente': 'database'
            }

            # Guardar en cache
            _cache_config_iva_db = config_completa
            _cache_timestamp_iva = datetime.now()

            logger.info(
                f"Configuracion IVA obtenida desde base de datos: "
                f"{len(config_completa['bienes_no_causan_iva'])} bienes no causan, "
                f"{len(config_completa['bienes_exentos_iva'])} bienes exentos, "
                f"{len(config_completa['servicios_excluidos_iva'])} servicios excluidos"
            )

            return config_completa

        else:
            error_msg = f"No se pudo obtener configuracion IVA desde BD: {resultado.get('message', 'Error desconocido')}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    except ValueError:
        # Re-lanzar ValueError (ya tiene el mensaje correcto)
        raise
    except Exception as e:
        error_msg = f"Error obteniendo configuracion IVA desde base de datos: {e}"
        logger.error(error_msg)
        logger.exception("Traceback del error:")
        raise ValueError(error_msg) from e


def limpiar_cache_configuracion_iva():
    """
    Limpia el cache de configuracion IVA.

    Util cuando se necesita forzar una recarga desde la base de datos.

    SRP: Solo limpia cache de configuracion IVA

    Example:
        >>> limpiar_cache_configuracion_iva()
        >>> config = obtener_configuracion_iva(db_manager, usar_cache=False)
    """
    global _cache_config_iva_db, _cache_timestamp_iva
    _cache_config_iva_db = None
    _cache_timestamp_iva = None
    logger.info("Cache de configuracion IVA limpiado")

def es_fuente_ingreso_nacional(respuestas_fuente: Dict[str, bool]) -> bool:
    """Determina si un servicio/bien es de fuente nacional según validaciones
    
    Args:
        respuestas_fuente: Diccionario con respuestas a preguntas de fuente
        
    Returns:
        bool: True si es fuente nacional, False si es extranjera
    """
    # Si CUALQUIERA de las respuestas es SÍ, es fuente nacional
    # Si TODAS son NO, es fuente extranjera
    return any(respuestas_fuente.values())

def calcular_reteiva(valor_iva: float, es_fuente_nacional: bool) -> float:
    """Calcula el valor de ReteIVA según la fuente
    
    Args:
        valor_iva: Valor del IVA calculado
        es_fuente_nacional: True si es fuente nacional, False si extranjera
        
    Returns:
        float: Valor de ReteIVA calculado
    """
    config = CONFIG_RETEIVA
    
    if es_fuente_nacional:
        return valor_iva * config["tarifa_fuente_nacional"]
    else:
        return valor_iva * config["tarifa_fuente_extranjera"]

def obtener_tarifa_reteiva(es_fuente_nacional: bool) -> float:
    """Obtiene la tarifa de ReteIVA según la fuente
    
    Args:
        es_fuente_nacional: True si es fuente nacional, False si extranjera
        
    Returns:
        float: Tarifa de ReteIVA (0.15 para nacional, 1.0 para extranjera)
    """
    config = CONFIG_RETEIVA
    
    if es_fuente_nacional:
        return config["tarifa_fuente_nacional"]
    else:
        return config["tarifa_fuente_extranjera"]

# ===============================
# FUNCIONES INTEGRADAS ACTUALIZADAS
# ===============================

def detectar_impuestos_aplicables(nit: str) -> Dict[str, Any]:
    """Detecta automáticamente qué impuestos aplican según el NIT - ACTUALIZADO CON IVA
    
    Args:
        nit: NIT administrativo
        
    Returns:
        Dict con información de qué impuestos aplican
    """
    aplica_estampilla = nit_aplica_estampilla_universidad(nit)
    aplica_obra_publica = nit_aplica_contribucion_obra_publica(nit)
    aplica_iva = nit_aplica_iva_reteiva(nit)  # ✅ NUEVA VALIDACIÓN
    
    impuestos_aplicables = []
    if aplica_estampilla:
        impuestos_aplicables.append("ESTAMPILLA_UNIVERSIDAD")
    if aplica_obra_publica:
        impuestos_aplicables.append("CONTRIBUCION_OBRA_PUBLICA")
    if aplica_iva:
        impuestos_aplicables.append("IVA_RETEIVA")  # ✅ NUEVO IMPUESTO
    
    return {
        "nit": nit,
        "aplica_estampilla_universidad": aplica_estampilla,
        "aplica_contribucion_obra_publica": aplica_obra_publica,
        "aplica_iva_reteiva": aplica_iva,  # ✅ NUEVO CAMPO
        "impuestos_aplicables": impuestos_aplicables,
        "procesamiento_paralelo": len(impuestos_aplicables) > 1,  # ✅ LÓGICA ACTUALIZADA
        "nombre_entidad_estampilla": NITS_ESTAMPILLA_UNIVERSIDAD.get(nit),
        "nombre_entidad_obra_publica": NITS_CONTRIBUCION_OBRA_PUBLICA.get(nit),
        "nombre_entidad_iva": NITS_IVA_RETEIVA.get(nit, {}).get("nombre")  # ✅ NUEVO CAMPO
    }

def obtener_configuracion_impuestos_integrada(database_manager=None) -> Dict[str, Any]:
    """
    Obtiene configuracion integrada para todos los impuestos - ACTUALIZADO CON IVA

    Args:
        database_manager: DatabaseManager para obtener configuracion IVA desde BD (REQUERIDO para IVA)

    Returns:
        Dict con configuraciones de todos los impuestos

    Raises:
        ValueError: Si database_manager es None (requerido para obtener config IVA)
    """
    return {
        "estampilla_universidad": obtener_configuracion_estampilla_universidad(),
        "contribucion_obra_publica": obtener_configuracion_obra_publica(),
        "iva_reteiva": obtener_configuracion_iva(database_manager=database_manager),
        "terceros_recursos_publicos_compartidos": list(TERCEROS_RECURSOS_PUBLICOS.keys())
    }

# ===============================
# FUNCIONES HELPER PARA RECURSOS EXTRANJEROS
# ===============================

def crear_resultado_recurso_extranjero_retefuente() -> object:
    """
    Crea estructura de retefuente para recurso de fuente extranjera.

    SRP: Responsabilidad única - generar estructura vacía con mensaje apropiado.
    Se usa cuando es_recurso_extranjero == True para evitar cálculo innecesario.

    Returns:
        object: Estructura compatible con resultado de liquidación retefuente
    """
    from datetime import datetime

    return type('ResultadoLiquidacion', (object,), {
        'aplica': False,
        'valor_retencion': 0.0,
        'valor_factura_sin_iva': 0.0,
        'conceptos_aplicados': [],
        'valor_base_retencion': 0.0,
        'fecha_calculo': datetime.now().isoformat(),
        'mensajes_error': ["Recurso de fuente extranjera - No aplica retención en la fuente"],
        'resumen_conceptos': 'N/A',
        'estado': 'no_aplica_impuesto'
    })()

def crear_resultado_recurso_extranjero_iva() -> Dict[str, Any]:
    """
    Crea estructura de IVA/ReteIVA para recurso de fuente extranjera.

    SRP: Responsabilidad única - generar estructura vacía con mensaje apropiado.
    Se usa cuando es_recurso_extranjero == True para evitar cálculo innecesario.

    Returns:
        Dict: Estructura compatible con resultado de liquidación IVA/ReteIVA
    """
    return {
        "iva_reteiva": {
            "aplica": False,
            "valor_iva_identificado": 0.0,
            "valor_subtotal_sin_iva": 0.0,
            "valor_reteiva": 0.0,
            "porcentaje_iva": 0.0,
            "tarifa_reteiva": 0.0,
            "es_fuente_nacional": False,
            "estado_liquidacion": "no_aplica_impuesto",
            "es_responsable_iva": None,
            "observaciones": ["Recurso de fuente extranjera - No aplica IVA ni ReteIVA"],
            "calculo_exitoso": True
        }
    }

# ===============================
# INICIALIZACIÓN AUTOMÁTICA
# ===============================

def inicializar_configuracion():
    """Inicializa y valida la configuración del sistema"""
    try:
        # Validar que las constantes estén definidas
        assert UVT_2025 > 0, "UVT_2025 debe ser mayor a 0"
        assert SMMLV_2025 > 0, "SMMLV_2025 debe ser mayor a 0"
        assert len(TERCEROS_RECURSOS_PUBLICOS) > 0, "Debe haber terceros configurados"
        assert len(CONCEPTOS_RETEFUENTE) > 0, "Debe haber conceptos de retefuente configurados"
        assert len(NITS_IVA_RETEIVA) > 0, "Debe haber NITs configurados para IVA y ReteIVA"
        
        logger.info(" Configuración inicializada correctamente")
        logger.info(f"   - UVT 2025: ${UVT_2025:,}")
        logger.info(f"   - Terceros: {len(TERCEROS_RECURSOS_PUBLICOS)}")
        logger.info(f"   - Conceptos ReteFuente: {len(CONCEPTOS_RETEFUENTE)}")
        logger.info(f"   - NITs IVA y ReteIVA: {len(NITS_IVA_RETEIVA)}")
        
        return True
        
    except Exception as e:
        logger.error(f" Error en inicialización: {e}")
        return False

# Inicializar al importar
#try:
    #inicializar_configuracion()
#except Exception as e:
   # logger.warning(f" Error en inicialización automática: {e}")


# ===============================
# FUNCIÓN PARA GUARDAR ARCHIVOS JSON
# ===============================

def guardar_archivo_json(contenido: dict, nombre_archivo: str, subcarpeta: str = "") -> bool:
    """
    Guarda archivos JSON en la carpeta Results/ organizados por fecha.

    FUNCIONALIDAD:
     Crea estructura Results/YYYY-MM-DD/
     Guarda archivos JSON con timestamp
     Manejo de errores sin afectar flujo principal
     Logs de confirmación
    Path absoluto para evitar errores de subpath

    Args:
        contenido: Diccionario a guardar como JSON
        nombre_archivo: Nombre base del archivo (sin extensión)
        subcarpeta: Subcarpeta opcional dentro de la fecha

    Returns:
        bool: True si se guardó exitosamente, False en caso contrario
    """
    try:
        # 1. CREAR ESTRUCTURA DE CARPETAS CON PATH ABSOLUTO
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        carpeta_base = Path.cwd()  # Path absoluto del proyecto
        carpeta_results = carpeta_base / "Results"
        carpeta_fecha = carpeta_results / fecha_actual

        if subcarpeta:
            carpeta_final = carpeta_fecha / subcarpeta
        else:
            carpeta_final = carpeta_fecha

        carpeta_final.mkdir(parents=True, exist_ok=True)

        # 2. CREAR NOMBRE CON TIMESTAMP
        timestamp = datetime.now().strftime("%H-%M-%S")
        nombre_final = f"{nombre_archivo}_{timestamp}.json"
        ruta_archivo = carpeta_final / nombre_final

        # 3. GUARDAR ARCHIVO JSON
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            json.dump(contenido, f, indent=2, ensure_ascii=False)

        # 4. LOG DE CONFIRMACIÓN CON PATH RELATIVO SEGURO
        try:
            ruta_relativa = ruta_archivo.relative_to(carpeta_base)
            logger.info(f" JSON guardado: {ruta_relativa}")
        except ValueError:
            # Fallback si relative_to falla
            logger.info(f" JSON guardado: {nombre_final} en {carpeta_final.name}")

        return True

    except Exception as e:
        logger.error(f" Error guardando JSON {nombre_archivo}: {e}")
        return False


# =====================================
# CONFIGURACION DE BASE DE DATOS
# =====================================

class DatabaseConfig:
    """
    Configuracion centralizada para diferentes fuentes de datos (SRP)

    Proporciona constantes y helpers para trabajar con multiples
    implementaciones de database (Supabase, Nexura API).

    Principios SOLID:
    - SRP: Solo maneja configuracion de databases
    - OCP: Extensible para nuevas fuentes de datos
    """

    # Tipos de database soportados
    DB_TYPE_SUPABASE = "supabase"
    DB_TYPE_NEXURA = "nexura"

    # Tipos de autenticacion soportados
    AUTH_TYPE_NONE = "none"
    AUTH_TYPE_JWT = "jwt"
    AUTH_TYPE_API_KEY = "api_key"

    # Timeouts default (segundos)
    DEFAULT_TIMEOUT = 30
    DEFAULT_HEALTH_CHECK_TIMEOUT = 10

    # Endpoints de Nexura API
    NEXURA_ENDPOINTS = {
        'negocios_fiduciaria': '/preliquidador/negociosFiduciaria/',
        'negocios': '/preliquidador/negocios/',
        'estructura_contable': '/preliquidador/estructuraContable/',
        'actividades_ica': '/preliquidador/actividadesIca/',
        'cuantias': '/preliquidador/cuantias/',
        'recursos': '/preliquidador/recursos/',
        'retefuente': '/preliquidador/retefuente/',
        'conceptos_extranjeros': '/preliquidador/conceptosExtranjeros/',
        'paises_convenio': '/preliquidador/paisesConvenio/'
    }

    @staticmethod
    def get_database_type() -> str:
        """
        Obtiene el tipo de database configurado desde variables de entorno

        Returns:
            str: Tipo de database ('supabase' o 'nexura', default: 'supabase')
        """
        return os.getenv("DATABASE_TYPE", DatabaseConfig.DB_TYPE_SUPABASE)

    @staticmethod
    def is_nexura_enabled() -> bool:
        """
        Verifica si Nexura API esta habilitada

        Returns:
            bool: True si DATABASE_TYPE es 'nexura'
        """
        return DatabaseConfig.get_database_type() == DatabaseConfig.DB_TYPE_NEXURA

    @staticmethod
    def is_supabase_enabled() -> bool:
        """
        Verifica si Supabase esta habilitado

        Returns:
            bool: True si DATABASE_TYPE es 'supabase'
        """
        return DatabaseConfig.get_database_type() == DatabaseConfig.DB_TYPE_SUPABASE

    @staticmethod
    def get_nexura_endpoint(nombre: str) -> str:
        """
        Obtiene URL de endpoint de Nexura por nombre

        Args:
            nombre: Nombre del endpoint (ej: 'negocios_fiduciaria')

        Returns:
            str: Path del endpoint o cadena vacia si no existe
        """
        return DatabaseConfig.NEXURA_ENDPOINTS.get(nombre, '')

    @staticmethod
    def get_auth_type() -> str:
        """
        Obtiene el tipo de autenticacion configurado para Nexura

        Returns:
            str: Tipo de auth ('none', 'jwt', 'api_key', default: 'none')
        """
        return os.getenv("NEXURA_AUTH_TYPE", DatabaseConfig.AUTH_TYPE_NONE)

    @staticmethod
    def validate_database_config() -> Dict[str, Any]:
        """
        Valida la configuracion de database actual

        Returns:
            Dict con resultado de validacion:
            {
                'valid': bool,
                'tipo_db': str,
                'errores': List[str],
                'warnings': List[str]
            }
        """
        errores = []
        warnings = []
        tipo_db = DatabaseConfig.get_database_type()

        if tipo_db == DatabaseConfig.DB_TYPE_SUPABASE:
            if not os.getenv("SUPABASE_URL"):
                errores.append("SUPABASE_URL no configurada")
            if not os.getenv("SUPABASE_KEY"):
                errores.append("SUPABASE_KEY no configurada")

        elif tipo_db == DatabaseConfig.DB_TYPE_NEXURA:
            if not os.getenv("NEXURA_API_BASE_URL"):
                errores.append("NEXURA_API_BASE_URL no configurada")

            auth_type = DatabaseConfig.get_auth_type()
            if auth_type == DatabaseConfig.AUTH_TYPE_JWT:
                if not os.getenv("NEXURA_JWT_TOKEN"):
                    warnings.append("NEXURA_JWT_TOKEN vacio (se usara sin autenticacion)")
            elif auth_type == DatabaseConfig.AUTH_TYPE_API_KEY:
                if not os.getenv("NEXURA_API_KEY"):
                    warnings.append("NEXURA_API_KEY vacia (se usara sin autenticacion)")

        else:
            errores.append(f"DATABASE_TYPE invalido: {tipo_db}")

        return {
            'valid': len(errores) == 0,
            'tipo_db': tipo_db,
            'errores': errores,
            'warnings': warnings
        }
