"""
PROMPT PARA ESTAMPILLA Y OBRA PUBLICA
======================================

Prompt especializado para análisis integrado de Estampilla Pro Universidad Nacional
y Contribución a Obra Pública.

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo prompts de estampilla y obra pública
- OCP: Abierto para extensión
- DIP: Funciones puras

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

from typing import List

# Import de función auxiliar compartida
from .prompt_clasificador import _generar_seccion_archivos_directos


def PROMPT_ANALISIS_OBRA_PUBLICA_ESTAMPILLA_INTEGRADO(factura_texto: str, rut_texto: str, anexos_texto: str,
                                                       cotizaciones_texto: str, anexo_contrato: str,
                                                       nit_administrativo: str, nombres_archivos_directos: List[str] = None) -> str:
    """
    PROMPT INTEGRADO OPTIMIZADO - EXTRACCIÓN Y CLASIFICACIÓN

    Analiza documentos para extraer información y clasificar el tipo de contrato
    para posterior cálculo de impuestos (Estampilla y Obra Pública).

    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        nit_administrativo: NIT de la entidad administrativa
        nombres_archivos_directos: Lista de nombres de archivos analizados

    Returns:
        str: Prompt optimizado para extracción y clasificación
    """

    # Importar configuración desde config.py
    from config import (
        UVT_2025,
        CODIGOS_NEGOCIO_ESTAMPILLA,
        TERCEROS_RECURSOS_PUBLICOS,
        OBJETOS_CONTRATO_ESTAMPILLA,
        OBJETOS_CONTRATO_OBRA_PUBLICA,
        RANGOS_ESTAMPILLA_UNIVERSIDAD,
        obtener_configuracion_impuestos_integrada
    )

    config_integrada = obtener_configuracion_impuestos_integrada()

    return f"""
### TAREA: EXTRACCIÓN DE DATOS Y CLASIFICACIÓN DE CONTRATO ###
═════════════════════════════════════════════════════════════

INSTRUCCIÓN PRINCIPAL:
Eres un sistema de extracción de datos especializado en documentos contractuales colombianos.
Tu ÚNICA tarea es:
1. Extraer información específica de los documentos proporcionados
2. Clasificar el tipo de contrato basándote en el objeto extraído

NO debes:
- Calcular impuestos
- Determinar si aplican o no los impuestos
- Inventar información que no esté en los documentos
- Hacer interpretaciones más allá de la clasificación

### DOCUMENTOS PROPORCIONADOS ###
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{_generar_seccion_archivos_directos(nombres_archivos_directos)}

<<INICIO_FACTURA>>
{factura_texto if factura_texto else "[NO PROPORCIONADO]"}
<<FIN_FACTURA>>

<<INICIO_RUT>>
{rut_texto if rut_texto else "[NO PROPORCIONADO]"}
<<FIN_RUT>>

<<INICIO_ANEXOS>>
{anexos_texto if anexos_texto else "[NO PROPORCIONADO]"}
<<FIN_ANEXOS>>

<<INICIO_ANEXO_CONTRATO>>
{anexo_contrato if anexo_contrato else "[NO PROPORCIONADO]"}
<<FIN_ANEXO_CONTRATO>>

### PROCESO DE EXTRACCIÓN ###
════════════════════════════

PASO 1 - EXTRAER OBJETO DEL CONTRATO:
--------------------------------------
• ORDEN DE BÚSQUEDA: Anexo Contrato → Factura → Anexos
• IDENTIFICACION : Buscar TEXTUALMENTE una seccion que mencione OBJETO DEL CONTRATO, No confundas CONCEPTO de la factura con OBJETO del contrato
• ACCIÓN: Copiar la descripción TEXTUAL EXACTA del objeto del contrato
• SI NO EXISTE LA SECCION TEXTUAL OBJETO DEL CONTRATO EN LOS DOCUMENTOS : Asignar valor "no_identificado"
• IMPORTANTE: No parafrasear, copiar literalmente

PASO 2 - EXTRAER VALORES MONETARIOS:
------------------------------------
2.1 VALOR FACTURA SIN IVA:
    • Buscar en la factura principal
    • Identificar: "subtotal", "valor antes de IVA", "base gravable"
    • SI NO EXISTE: Asignar valor 0

2.2 VALOR TOTAL DEL CONTRATO SIN ADICIONES:
    • Buscar en CUALQUIER documento disponible
    • Identificar: "valor del contrato", "valor total contrato"
    • SI NO EXISTE: Asignar valor 0

2.3 VALOR DE ADICIONES/MODIFICACIONES:
    • Buscar términos: "adición", "otrosí", "modificación", "prórroga con adición"
    • Sumar TODOS los valores de adiciones encontradas
    • SI NO EXISTE: Asignar valor 0

PASO 3 - CLASIFICAR TIPO DE CONTRATO:
-------------------------------------
Comparar el objeto extraído con estas palabras clave ESPECÍFICAS:

• Obra: {OBJETOS_CONTRATO_ESTAMPILLA['contrato_obra']['palabras_clave']}
   • Interventoría: {OBJETOS_CONTRATO_ESTAMPILLA['interventoria']['palabras_clave']}
   • Servicios conexos: {OBJETOS_CONTRATO_ESTAMPILLA['servicios_conexos_obra']['palabras_clave']}

═══ TIPO A: CONTRATO_OBRA ═══
PALABRAS CLAVE EXACTAS {OBJETOS_CONTRATO_ESTAMPILLA['contrato_obra']['palabras_clave']}


═══ TIPO B: INTERVENTORIA ═══
PALABRAS CLAVE EXACTAS: {OBJETOS_CONTRATO_ESTAMPILLA['interventoria']['palabras_clave']}


═══ TIPO C: SERVICIOS_CONEXOS ═══
PALABRAS CLAVE EXACTAS: {OBJETOS_CONTRATO_ESTAMPILLA['servicios_conexos_obra']['palabras_clave']}


═══ TIPO D: NO_APLICA ═══
Asignar cuando el objeto del contrato extraído:
• No contiene NINGUNA relación con las palabras clave de los tipos anteriores
• Es un servicio/producto completamente diferente

═══ TIPO E: NO_IDENTIFICADO ═══
Asignar cuando el objeto del contrato no se haya podido extraer de los documentos proporcionados


### REGLAS ESTRICTAS ###
═══════════════════════

 PROHIBIDO:
1. Inventar valores o descripciones no presentes en documentos
2. Redondear o modificar valores numéricos
3. Hacer cálculos de ningún tipo
4. Interpretar más allá de la clasificación por palabras clave
5. Decidir sobre aplicación de impuestos
6. Asignar el concepto de la factura como OBJETO del contrato
7. Extraer el objeto del contrato de secciones que no mencionen TEXTUALMENTE "OBJETO DEL CONTRATO"


✓ OBLIGATORIO:
1. Copiar textualmente las descripciones encontradas
2. Usar 0 cuando no encuentres un valor
3. Usar "no_identificado" cuando no encuentres una descripción
4. Clasificar ÚNICAMENTE basándote en palabras clave exactas
5. Incluir la evidencia textual que justifica la clasificación
6. Extraer el objeto del contrato SOLAMENTE de la seccion que mencione TEXTUALMENTE OBJETO DEL CONTRATO

### FORMATO DE RESPUESTA - JSON ESTRICTO ###
════════════════════════════════════════════

Responde ÚNICAMENTE con el siguiente JSON.
NO incluyas texto antes o después del JSON:

{{
  "extraccion": {{
    "objeto_contrato": {{
      "descripcion_literal": "Copiar texto exacto del documento o 'no_identificado'",
      "documento_origen": "Nombre del documento donde se encontró o 'ninguno'",
    }},
    "valores": {{
      "factura_sin_iva": valor encontrado o 0,
      "contrato_total": valor encontrado o 0,
      "adiciones": valor encontrado o 0,
      "observaciones_valores": "Notas sobre valores encontrados o faltantes"
    }}
  }},

  "clasificacion": {{
    "tipo_contrato": "CONTRATO_OBRA|INTERVENTORIA|SERVICIOS_CONEXOS|NO_APLICA|NO_IDENTIFICADO",
    "palabras_clave_encontradas": ["lista", "de", "palabras", "encontradas"],
    "fragmento_evidencia": "Copiar la frase exacta del documento que contiene las palabras clave",
    "confianza_clasificacion": "ALTA|MEDIA|BAJA",
    "razon_confianza": "Explicación breve del nivel de confianza"

  }}
}}
"""
