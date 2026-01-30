"""
PROMPT PARA ANALISIS DE IVA
============================

Prompt especializado para extracción y clasificación de IVA (Impuesto al Valor Agregado).

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo prompts de IVA
- OCP: Abierto para extensión
- DIP: Funciones puras

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

import json
from typing import List

# Import de función auxiliar compartida
from .prompt_clasificador import _generar_seccion_archivos_directos


def PROMPT_ANALISIS_IVA(factura_texto: str, rut_texto: str, anexos_texto: str,
                                    cotizaciones_texto: str, anexo_contrato: str,
                                    nombres_archivos_directos: list[str] = None) -> str:
    """
    Prompt optimizado para Gemini - Enfocado en extracción y clasificación de IVA.

    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        nombres_archivos_directos: Lista de nombres de archivos directos

    Returns:
        str: Prompt formateado para enviar a Gemini
    """
    # Importar configuraciones de IVA
    from config import obtener_configuracion_iva
    # Obtener configuración de IVA
    config_iva = obtener_configuracion_iva()

    return f"""
ROL: Eres un EXTRACTOR y CLASIFICADOR de información tributaria especializado en IVA colombiano.
Tu función es ÚNICAMENTE extraer datos específicos de los documentos  y clasificar conceptos según las categorías predefinidas.

═══════════════════════════════════════════════════════════════════════
DOCUMENTOS A ANALIZAR
═══════════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}

FACTURA (DOCUMENTO PRINCIPAL):
{factura_texto}

RUT (si está disponible):
{rut_texto if rut_texto else "NO DISPONIBLE"}

ANEXOS (DETALLES ADICIONALES):
{anexos_texto if anexos_texto else "NO DISPONIBLES"}

COTIZACIONES (PROPUESTAS COMERCIALES):
{cotizaciones_texto if cotizaciones_texto else "NO DISPONIBLES"}

ANEXO CONCEPTO CONTRATO (OBJETO DEL CONTRATO):
{anexo_contrato if anexo_contrato else "NO DISPONIBLES"}

═══════════════════════════════════════════════════════════════════════
CATEGORÍAS DE CLASIFICACIÓN (SOLO SI NO HAY IVA EN FACTURA)
═══════════════════════════════════════════════════════════════════════

BIENES QUE NO CAUSAN IVA:
{json.dumps(config_iva['bienes_no_causan_iva'], indent=2, ensure_ascii=False)}

BIENES EXENTOS DE IVA:
{json.dumps(config_iva['bienes_exentos_iva'], indent=2, ensure_ascii=False)}

SERVICIOS EXCLUIDOS DE IVA:
{json.dumps(config_iva['servicios_excluidos_iva'], indent=2, ensure_ascii=False)}

═══════════════════════════════════════════════════════════════════════
TAREAS ESPECÍFICAS DE EXTRACCIÓN
═══════════════════════════════════════════════════════════════════════

1.  CRÍTICO - SOLO DEL RUT (FORMULARIO DE REGISTRO ÚNICO TRIBUTARIO) - EXTRAER:

    INSTRUCCIÓN OBLIGATORIA PARA DOCUMENTOS LARGOS:

   • DEBES escanear COMPLETAMENTE TODO el documento de INICIO a FIN
   • El RUT puede estar en CUALQUIER página del documento (inicio, medio o final)
   • NO asumas ubicaciones - REVISA TODAS LAS PÁGINAS sin excepción
   • Busca indicadores del RUT: "REGISTRO ÚNICO TRIBUTARIO", "RUT", "DIAN", "NIT"
   • Es OBLIGATORIO revisar el documento COMPLETO

    EXTRACCIÓN ESPECÍFICA una vez encuentres el RUT:

   • Buscar SOLO en la sección "RESPONSABILIDADES, CALIDADES Y ATRIBUTOS"
   • NO te fijes en pequeñas casillas marcadas, Solo en el texto principal
   • Identificar texto de responsabilidad:
     - "48 - Impuesto sobre las ventas - IVA" → es_responsable_iva: true
     - "49 - No responsable de IVA" → es_responsable_iva: false

    VALIDACIONES DE CASOS ESPECIALES:

   • Si encuentras el RUT pero NO tiene código de responsabilidad IVA:
     → "es_responsable_iva": null
     → "texto_evidencia": "RUT encontrado pero sin código de responsabilidad IVA"

   • Si NO encuentras el RUT en ninguna parte del documento, busca la responsabilidad del IVA en los demas DOCUMENTOS proporcionados (factura, anexos):
     → "rut_disponible": false
     
 1.1 Si NO encuentras el RUT , Extrae la responsabilidad de iva en el siguiente orden Factura → Anexos:
 
     • DEBES buscar palabras clave explicitas como : "Responsable de IVA", "No responsable de IVA", "somos responsables de IVA", "no somos responsables de IVA":
     
        • Si encuentras alguna de estas frases, asigna :
        "rut_disponible" : false
        "es_responsable_iva" : true or false según corresponda
        "texto_evidencia" : "Texto exacto donde encontraste la información"
        
        • Si NO encuentras ninguna mención a la responsabilidad de IVA en ningun documento, asigna :
        "rut_disponible" : false
        "es_responsable_iva" : null
        "texto_evidencia" : "No se encontró información sobre responsabilidad de IVA "
        
        • Si encuentras el valor del IVA en la factura, pero NO encuentras  mención LITERAL a la responsabilidad de IVA , asigna :
        "rut_disponible" : false
        "es_responsable_iva" : null
        "texto_evidencia" : "No se encontró información sobre responsabilidad de IVA "
        
 
 

2. SOLO DE LA FACTURA - EXTRAER:
   • Valor del IVA (buscar: "IVA", "I.V.A", "Impuesto")
   • Porcentaje del IVA (usualmente 19 si 19%, 5 si 5% o 0 si 0%) (extraelo como un numero entero >= 0)
   • Valor subtotal (factura SIN IVA)
   • Valor total (factura CON IVA incluido)
   • Concepto facturado (copiar textualmente la descripción del servicio/bien)

3. CLASIFICACIÓN DEL CONCEPTO:

   SI LA FACTURA TIENE IVA (valor > 0):
   → Asignar categoría: "gravado"

   SI LA FACTURA NO TIENE IVA (valor = 0 o no menciona IVA):
   → Comparar el concepto extraído con las listas de categorías proporcionadas
   → Asignar categoría: "no_causa_iva" | "exento" | "excluido" | "no_clasificado"

   IMPORTANTE: Si no puedes clasificar con certeza, usa "no_clasificado"

═══════════════════════════════════════════════════════════════════════
FORMATO DE RESPUESTA (JSON ESTRICTO)
═══════════════════════════════════════════════════════════════════════

Responde ÚNICAMENTE con el siguiente JSON, sin texto adicional:

{{
    "extraccion_rut": {{
        "es_responsable_iva": true | false | null,
        "texto_evidencia": "Texto exacto donde encontraste la información"
    }},
    "extraccion_factura": {{
        "valor_iva": valor encontrado o 0.0,
        "porcentaje_iva": valor encontrado o 0,
        "valor_subtotal_sin_iva": valor encontrado o 0.0,
        "valor_total_con_iva": valor encontrado o 0.0,
        "concepto_facturado": "Transcripción textual del concepto/descripción",
    }},
    "clasificacion_concepto": {{
        "categoria": "gravado|no_causa_iva|exento|excluido|no_clasificado",
        "justificacion": "Breve explicación de por qué se asignó esta categoría",
        "coincidencia_encontrada": "Item específico de las listas que coincide (si aplica)"
    }},
    "validaciones": {{
        "rut_disponible": true/false
    }}
}}

═══════════════════════════════════════════════════════════════════════
REGLAS CRÍTICAS
═══════════════════════════════════════════════════════════════════════

• NO interpretes ni deduzcas información que no esté explícita
• Si un dato no está disponible, usa 0.0 para números y null para booleanos
• La clasificación SOLO se hace si NO hay IVA en la factura
• Si hay IVA en la factura, SIEMPRE es categoría "gravado"
• Extrae EXACTAMENTE lo que aparece en los documentos
• No calcules valores que no estén explícitos en la factura
• NO ASUMAS la responsabilidad de IVA porque la factura mencione un valor de IVA, solo extrae lo que está escrito


"""
