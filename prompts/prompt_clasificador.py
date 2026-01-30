"""
PROMPTS PARA CLASIFICACIÓN DE DOCUMENTOS
========================================

Plantillas de prompts utilizadas por el clasificador de documentos.
"""

import json
from typing import Dict, List



def PROMPT_CLASIFICACION(textos_preprocesados: Dict[str, str], nombres_archivos_directos: List[str], proveedor: str = None) -> str:
    """
    Genera el prompt optimizado para clasificar documentos fiscales colombianos.
    Versión mejorada con prevención de alucinaciones y criterios más claros.

    Args:
        textos_preprocesados: Diccionario con textos preprocesados
        nombres_archivos_directos: Lista de nombres de archivos directos
        proveedor: Nombre del proveedor que emite la factura (v3.0)
    """

    todos_los_archivos = nombres_archivos_directos + list(textos_preprocesados.keys())
    total_archivos = len(todos_los_archivos)

    # Contexto de proveedor para mejor identificación
    contexto_proveedor = ""
    if proveedor:
        contexto_proveedor = f"""
═══════════════════════════════════════════════════════════════════════
INFORMACIÓN DEL PROVEEDOR (CONTEXTO DE VALIDACIÓN)
═══════════════════════════════════════════════════════════════════════

**PROVEEDOR ESPERADO:** {proveedor}

INSTRUCCIONES DE VALIDACIÓN CONTRA RUT:
• Verifica que el nombre/razón social del proveedor en la FACTURA coincida con el RUT
• Verifica que el NIT en la FACTURA coincida con el NIT del RUT
• Si encuentras discrepancias entre FACTURA y RUT, repórtalas explícitamente
• Si el proveedor es un CONSORCIO o UNIÓN TEMPORAL:
  - Verifica que el nombre del consorcio en FACTURA coincida con RUT
  - Identifica los miembros/integrantes del consorcio
  - Verifica los porcentajes de participación si están disponibles
  - Reporta si falta información de algún consorciado

VALIDACIÓN DE COHERENCIA:
1. Nombre en FACTURA vs Nombre en RUT → deben coincidir
2. NIT en FACTURA vs NIT en RUT → deben coincidir
3. Si es consorcio: nombre del consorcio debe aparecer en ambos documentos
4. Si hay inconsistencias, márcalas en "indicadores_consorcio" o crea campo de observaciones

"""

    return f"""
ROL: Eres un CLASIFICADOR LITERAL de documentos fiscales colombianos.
Tu función es ÚNICAMENTE identificar y clasificar basándote en lo que está ESCRITO TEXTUALMENTE.
{contexto_proveedor}

 REGLA FUNDAMENTAL ANTI-ALUCINACIÓN:
• PROHIBIDO deducir, interpretar o suponer información
• SOLO usa texto que puedas CITAR LITERALMENTE del documento
• Si no encuentras evidencia textual explícita → marca como false
• NO uses contexto implícito, SOLO texto explícito
• NO clasifiques pagina por página, clasifica el documento completo

═══════════════════════════════════════════════════════════════════════
PASO 1: CLASIFICACIÓN DE DOCUMENTOS
═══════════════════════════════════════════════════════════════════════

Debes clasificar EXACTAMENTE {total_archivos} documento(s) en UNA de estas categorías:

1. **FACTURA** - Identificar si contiene:
   ✓ Número de factura o documento equivalente
   ✓ Fecha de emisión/venta
   ✓ Valores monetarios (subtotal, total, impuestos)
   ✓ Datos del vendedor/proveedor y comprador
   ✓ Descripción de bienes o servicios vendidos
   
   SE PUEDE CLASIFICAR COMO FACTURA TAMBIÉN:
   • "SOPORTE EN ADQUISICIONES EFECTUADAS A NO OBLIGADOS A FACTURAR"
   • "CUENTA DE COBRO"
   • "DOCUMENTO EQUIVALENTE"
   • Cualquier documento con estructura de venta/cobro

2. **RUT** - Registro Único Tributario que contiene:
   ✓ Número de identificación tributaria (NIT)
   ✓ Razón social
   ✓ Responsabilidades tributarias
   ✓ Actividades económicas CIIU

4. **ANEXO_CONTRATO** - Documento que contiene ESPECÍFICAMENTE:
   ✓ Objeto del contrato
   ✓ Obligaciones contractuales
   ✓ Términos y condiciones del contrato

5. **ANEXO** - Cualquier otro documento de soporte

REGLA ESPECIAL: Si un documento combina múltiple información → clasifícalo por su función PRINCIPAL
Si hay solo UN DOCUMENTO con múltiples funciones → clasifícalo como FACTURA

═══════════════════════════════════════════════════════════════════════
PASO 2: IDENTIFICACIÓN DE CONTENIDO (FACTURA Y RUT)
═══════════════════════════════════════════════════════════════════════

**factura_identificada = true** si en CUALQUIER documento encuentras:
• Estructura de facturación (valores + conceptos + totales)
• Información de venta/cobro formal
• NO importa si está en un archivo separado o integrado

**rut_identificado = true** si en CUALQUIER documento encuentras:
• El Registro Único Tributario completo
• Información de responsabilidades tributarias
• NO importa si está en un archivo separado o integrado

═══════════════════════════════════════════════════════════════════════
PASO 3: DETECCIÓN DE CONSORCIO
═══════════════════════════════════════════════════════════════════════

 BUSCAR ÚNICAMENTE EN: **FACTURA** o **RUT**
 NO buscar en: ANEXO_CONTRATO, anexos

**es_consorcio = true** SOLO SI encuentras TEXTUALMENTE:
• La palabra "CONSORCIO" en el nombre/razón social del proveedor
• La palabra "UNIÓN TEMPORAL" en el nombre/razón social
• Texto explícito: "consorciados", "miembros del consorcio"
• Porcentajes de participación: "Empresa A: 60%, Empresa B: 40%"

Si no encuentras estas palabras EXACTAS → es_consorcio = false

═══════════════════════════════════════════════════════════════════════
PASO 4: DETERMINACIÓN DE UBICACION DEL PROVEEDOR 
═══════════════════════════════════════════════════════════════════════
 
 Para determinar si el proveedor esta fuera de colombia, debes extraer la ubicacion del proveedor buscando TEXTUALMENTE en la FACTURA.
    Buscar texto similar a Direccion, Ciudad, Pais, Domicilio, Sede Principal, Sucursal, Oficina, Establecimiento.
    
 "ubicacion_proveedor": "Texto exacto de la ubicación extraido de la factura" o ""
 
 Si la ubicacion indica que el proveedor esta fuera de colombia, entonces:
 "es_fuera_colombia": true
Si la ubicacion indica que el proveedor esta en colombia, entonces:
 "es_fuera_colombia": false

═══════════════════════════════════════════════════════════════════════
PASO 5: DETERMINACIÓN DE FUENTE DE INGRESO (NACIONAL vs EXTRANJERA)
═══════════════════════════════════════════════════════════════════════

 DOCUMENTOS A REVISAR: TODOS los documentos listados

Para determinar si es **FUENTE EXTRANJERA**, responde estas preguntas basándote SOLO en texto explícito:

1. **¿El servicio tiene uso o beneficio económico en Colombia?**
   Buscar texto similar a:
   • "servicio prestado en Colombia"
   • "para uso en territorio colombiano"
   • "beneficiario en Colombia"

2. **¿La actividad se ejecutó total o parcialmente en Colombia?**
   Buscar texto similar a:
   • "ejecutado en Colombia"
   • "realizado en [ciudad colombiana]"
   • "prestación del servicio en Colombia"

3. **¿Es asistencia técnica/consultoría usada en Colombia?**
   Buscar texto similar a:
   • "asistencia técnica para operaciones en Colombia"
   • "consultoría implementada en Colombia"
   • "know-how aplicado en territorio nacional"

4. **¿El bien vendido está ubicado en Colombia?**
   Buscar texto similar a:
   • "entrega en Colombia"
   • "bien ubicado en [dirección colombiana]"
   • "instalación en Colombia"

IMPORTANTE : Si no encuentras evidencia textual clara para alguna de las preguntas anteriores → responde null


═══════════════════════════════════════════════════════════════════════
DOCUMENTOS A ANALIZAR
═══════════════════════════════════════════════════════════════════════

**ARCHIVOS DIRECTOS:**
{_formatear_archivos_directos(nombres_archivos_directos)}

**TEXTOS PREPROCESADOS:**
{_formatear_textos_preprocesados(textos_preprocesados)}

═══════════════════════════════════════════════════════════════════════
FORMATO DE RESPUESTA OBLIGATORIO (JSON ESTRICTO)
═══════════════════════════════════════════════════════════════════════

{{
    "clasificacion": {{
        "nombre_archivo_1": "FACTURA|RUT|COTIZACION|ANEXO_CONTRATO|ANEXO",
        "nombre_archivo_2": "FACTURA|RUT|COTIZACION|ANEXO_CONTRATO|ANEXO"
    }},
    "factura_identificada": true/false,
    "rut_identificado": true/false,
    "es_consorcio": true/false,
    "indicadores_consorcio": ["cita textual exacta del RUT o FACTURA"],
    "ubicacion_proveedor": "Texto exacto de la ubicación extraido de la factura" o "",
    "es_fuera_colombia": true/false,
    "analisis_fuente_ingreso": {{
        "servicio_uso_colombia": true/false/null,
        "evidencias_uso_encontradas": ["cita textual"],
        "ejecutado_en_colombia": true/false/null,
        "evidencias_ejecucion_encontradas": ["cita textual"],
        "asistencia_tecnica_colombia": true/false/null,
        "evidencias_asistencia_encontradas": ["cita textual"],
        "bien_ubicado_colombia": true/false/null,
        "evidencias_bien_encontradas": ["cita textual"]
    }}
}}

 RECORDATORIOS FINALES:
• NO interpretes - SOLO extrae lo que está escrito
• Las evidencias deben ser CITAS TEXTUALES copiadas del documento
• Si no hay información clara, usa false o ( null para los items de analisis fuente ingreso)
• Clasifica TODOS los documentos listados
• Si hay solo UN DOCUMENTO con múltiples funciones → clasifícalo OBLIGATORIAMENTE como FACTURA

"""
def _formatear_archivos_directos(nombres_archivos_directos: List[str]) -> str:
    """
    Formatea la lista de archivos directos para el prompt.
    
    Args:
        nombres_archivos_directos: Lista de nombres de archivos directos
        
    Returns:
        str: Texto formateado para incluir en el prompt
    """
    if not nombres_archivos_directos:
        return "- No hay archivos directos en esta solicitud"
    
    texto = ""
    for i, nombre in enumerate(nombres_archivos_directos, 1):
        extension = nombre.split('.')[-1].upper() if '.' in nombre else "DESCONOCIDO"
        tipo_archivo = "PDF" if extension == "PDF" else "IMAGEN" if extension in ["JPG", "JPEG", "PNG", "GIF", "BMP", "TIFF"] else extension
        texto += f"- {nombre} (ARCHIVO {tipo_archivo} ADJUNTO - lo verás directamente)\n"
    
    return texto.strip()

def _formatear_textos_preprocesados(textos_preprocesados: Dict[str, str]) -> str:
    """
    Formatea los textos preprocesados para incluir en el prompt.
    
    Args:
        textos_preprocesados: Diccionario con textos preprocesados
        
    Returns:
        str: Texto formateado para incluir en el prompt
    """
    if not textos_preprocesados:
        return "- No hay textos preprocesados en esta solicitud"
    
    import json
    return json.dumps(textos_preprocesados, indent=2, ensure_ascii=False)

def _generar_seccion_archivos_directos(nombres_archivos_directos: List[str]) -> str:
    """
    Genera sección informativa sobre archivos directos para análisis de factura.
    
    Args:
        nombres_archivos_directos: Lista de nombres de archivos directos o None
        
    Returns:
        str: Texto formateado para incluir en el prompt de análisis
    """
    if not nombres_archivos_directos:
        return " **ARCHIVOS DIRECTOS**: No hay archivos directos adjuntos."
    
    texto = " **ARCHIVOS DIRECTOS ADJUNTOS** (verás estos archivos nativamente):\n"
    for nombre in nombres_archivos_directos:
        extension = nombre.split('.')[-1].upper() if '.' in nombre else "DESCONOCIDO"
        if extension == "PDF":
            tipo = "PDF"
        elif extension in ["JPG", "JPEG", "PNG", "GIF", "BMP", "TIFF", "WEBP"]:
            tipo = "IMAGEN"
        else:
            tipo = extension
        texto += f"   - {nombre} (ARCHIVO {tipo} - procésalo directamente)\n"
    
    return texto.strip()

