"""
PROMPTS ESPECIALIZADOS PARA IMPUESTO AL TIMBRE
==============================================

Modulo que contiene los prompts especializados para el analisis
del Impuesto al Timbre usando Google Gemini.

Responsabilidad (SRP): Solo definicion de prompts para timbre
"""

from typing import List


def PROMPT_ANALISIS_TIMBRE_OBSERVACIONES(observaciones_texto: str) -> str:
    """
    Genera prompt para analizar si se menciona impuesto al timbre en observaciones de PGD.

    Responsabilidad (SRP): Solo genera prompt para primera llamada a Gemini (observaciones)

    Args:
        observaciones_texto: Campo observaciones del endpoint de PGD

    Returns:
        str: Prompt estructurado para analisis de observaciones
    """

    prompt = f"""
Eres un asistente especializado en analizar informacion tributaria colombiana.

TAREA ESPECIFICA:
Analiza el campo de OBSERVACIONES proporcionado y determina si se menciona la aplicacion del IMPUESTO AL TIMBRE.

CAMPO OBSERVACIONES A ANALIZAR:
```
{observaciones_texto}
```

INSTRUCCIONES DE ANALISIS:

1. IDENTIFICACION DE APLICACION DE TIMBRE:
   - Busca menciones  similares a " aplicar impuesto al timbre", " validar timbre", " analizar estampilla timbre"
   - Busca frases que indiquen aplicacion de este impuesto
   - Si encuentras cualquier mencion, establece aplica_timbre = true
   - Si NO encuentras ninguna mencion o si encuentras " no aplicar timbre" o similares que indiquen que NO se debe aplicar el impuesto . Establece aplica_timbre = false
   

2. EXTRACCION DE BASE GRAVABLE:
   - Busca el valor de la base gravable mencionada para el impuesto al timbre
   - Puede aparecer como "base gravable timbre", "base timbre", "valor base timbre"
   - Si encuentras un valor numerico especifico, extrae ese valor
   - Si NO encuentras valor, establece base_gravable_obs = 0.0

FORMATO DE RESPUESTA REQUERIDO (JSON estricto):
```json
{{
  "aplica_timbre": true o false,
  "base_gravable_obs": 0.0
}}
```

EJEMPLOS:

Ejemplo 1 - Timbre mencionado con base:
Observaciones: "Aplicar impuesto al timbre con base gravable de $5000000"
Respuesta: {{"aplica_timbre": true, "base_gravable_obs": 5000000.0}}

Ejemplo 2 - Timbre mencionado sin base:
Observaciones: "Se debe aplicar impuesto al timbre"
Respuesta: {{"aplica_timbre": true, "base_gravable_obs": 0.0}}

Ejemplo 3 - Timbre NO mencionado:
Observaciones: "Aplicar retencion en la fuente y estampilla universidad"
Respuesta: {{"aplica_timbre": false, "base_gravable_obs": 0.0}}

IMPORTANTE:
- Solo respondes con JSON valido
- NO agregues explicaciones adicionales
- Si hay duda, establece aplica_timbre = false
- Los valores numericos deben ser float (ejemplo: 5000000.0, no 5000000)

ANALIZA AHORA LAS OBSERVACIONES PROPORCIONADAS Y RESPONDE EN FORMATO JSON:
"""

    return prompt


def PROMPT_EXTRACCION_CONTRATO_TIMBRE(
    factura_texto: str,
    rut_texto: str,
    anexos_texto: str,
    cotizacion_texto: str = "",
    otros_texto: str = "",
    nombres_archivos_directos: List[str] = None
) -> str:
    """
    Genera prompt para extraer informacion del contrato necesaria para calculo de timbre.

    Responsabilidad (SRP): Solo genera prompt para segunda llamada a Gemini (extraccion contrato)

    Args:
        factura_texto: Texto extraido de la factura
        rut_texto: Texto extraido del RUT
        anexos_texto: Texto extraido de anexos
        cotizacion_texto: Texto extraido de cotizacion (opcional)
        otros_texto: Otros textos adicionales (opcional)
        nombres_archivos_directos: Lista de nombres de archivos procesados

    Returns:
        str: Prompt estructurado para extraccion de datos del contrato
    """

    # Preparar lista de archivos
    archivos_info = ""
    if nombres_archivos_directos:
        archivos_info = "\n".join([f"  - {nombre}" for nombre in nombres_archivos_directos])
    else:
        archivos_info = "  - [No se especificaron archivos]"

    prompt = f"""
Eres un asistente especializado en extraer informacion de contratos colombianos para el calculo del IMPUESTO AL TIMBRE.

DOCUMENTOS DISPONIBLES:
{archivos_info}

CONTENIDO DE LOS DOCUMENTOS:

=== FACTURA ===
{factura_texto if factura_texto else "[No disponible]"}

=== RUT ===
{rut_texto if rut_texto else "[No disponible]"}

=== ANEXOS Y DOCUMENTOS DEL CONTRATO ===
{anexos_texto if anexos_texto else "[No disponible]"}

=== COTIZACION ===
{cotizacion_texto if cotizacion_texto else "[No disponible]"}

=== OTROS DOCUMENTOS ===
{otros_texto if otros_texto else "[No disponible]"}

TAREA ESPECIFICA:
Extrae la siguiente informacion del contrato de forma EXACTA y LITERAL segun aparece en los documentos.

INFORMACION A EXTRAER:

1. ID DEL CONTRATO:
   - Busca el numero de contrato que aparece con etiquetas como:
     * "No. Contrato"
     * "Orden de Servicios"
     * "Numero de Contrato"
   - El formato tipico es: FNTCE-572-2023, 049-2024, FNTCE-229A-2025
   - Extrae EXACTAMENTE como aparece en el documento
   - Si NO encuentras, establece: ""
   - Si encuentras el ID del contrato menciona la cita textual del fragmento donde aparece en cita_texto_ID_contrato, SOLO agrega un corto fragmento de maximo 50 caracteres.

2. FECHA DE SUSCRIPCION DEL CONTRATO:
   - Busca la fecha con etiquetas como:
     * "Fecha de Suscripcion"
     * "Fecha Suscripcion"
     * "Fecha de firma"
   - IMPORTANTE: Convierte la fecha al formato YYYY-MM-DD
   - Ejemplos de conversion:
     * Si encuentras "15/03/2024" -> convierte a "2024-03-15"
     * Si encuentras "03-15-2024" -> convierte a "2024-03-15"
     * Si encuentras "15 de marzo de 2024" -> convierte a "2024-03-15"
   - Si NO encuentras fecha, establece: "0000-00-00"

3. VALOR INICIAL DEL CONTRATO:
   - Busca el valor inicial del contrato
   - Puede aparecer como "Valor del Contrato", "Valor Inicial"
   - Extrae solo el valor numerico (sin simbolos)
   - Si NO encuentras, establece: 0.0

4. VALOR TOTAL DEL CONTRATO:
   - Busca el valor total final del contrato (incluye adiciones si las hay)
   - Puede aparecer como "Valor Total", "Valor Final", "Valor con Adiciones"
   - Si solo hay valor inicial y no hay adiciones, el total es igual al inicial
   - Extrae solo el valor numerico
   - Si NO encuentras, establece: 0.0

5. ADICIONES AL CONTRATO:
   - Busca modificaciones monetarias al contrato (OTRO SI, ADICIONES, MODIFICACIONES)
   - Para CADA adicion encontrada, extrae:
     a) valor_adicion: Monto de la adicion (valor numerico)
     b) fecha_adicion: Fecha de la adicion o del OTRO SI en formato YYYY-MM-DD
   - Si NO hay adiciones, devuelve lista vacia: []
   - Si encuentras adiciones pero NO tienen fecha, establece fecha_adicion: "0000-00-00"
   
6. VALOR FACTURA SIN IVA :
   - Extrae el valor total de la factura sin incluir IVA solamente del documento que mencione literalmente "FACTURA", "FACTURA DE VENTA" O "FACTURA ELECTRONICA DE VENTA"
   - Extrae solo el valor numerico
   
   
   
FORMATO DE RESPUESTA REQUERIDO (JSON estricto):
```json
{{
  "id_contrato": "FNTCE-572-2023",
  "cita_texto_ID_contrato": "El contrato No. Contrato FNTCE-572-2023 fue suscrito...",
  "fecha_suscripcion": "2024-03-15",
  "valor_inicial_contrato": 10000000.0,
  "valor_factura_sin_iva": 9500000.0,
  "valor_total_contrato": 12000000.0,
  "adiciones": [
    {{
      "valor_adicion": 2000000.0,
      "fecha_adicion": "2024-06-20"
    }},
    {{
      "valor_adicion": 1000000.0,
      "fecha_adicion": "2024-09-15"
    }}
  ],
  "observaciones": ""
}}
```

REGLAS IMPORTANTES:

1. FORMATO DE FECHAS (OBLIGATORIO):
   - TODAS las fechas deben estar en formato YYYY-MM-DD
   - Ejemplos validos: "2024-03-15", "2025-12-31", "2023-01-01"
   - Si no encuentras fecha: "0000-00-00"

2. EXTRACCION LITERAL:
   - NO calcules valores, solo extrae lo que esta EXPLICITAMENTE en los documentos
   - NO sumes adiciones para calcular el total
   - Convierte fechas al formato requerido YYYY-MM-DD

3. VALORES NUMERICOS:
   - Siempre como float: 10000000.0 (NO 10000000)
   - Sin simbolos de moneda ni separadores de miles
   - Si un valor no se encuentra, usa 0.0

4. ADICIONES:
   - Pueden ser multiples
   - Cada adicion debe tener valor y fecha en formato YYYY-MM-DD
   - Si no hay adiciones, devuelve: []

5. ID CONTRATO:
   - Extrae EXACTAMENTE como aparece
   - Puede tener letras, numeros, guiones
   - Si no encuentras, usa: ""
   
6. OBSERVACIONES:
   - Agrega en las observaciones la informacion que creas pertinente de tu analisis, se muy breve y conciso.
   
   
EJEMPLO DE RESPUESTA CON DATOS NO ENCONTRADOS:
```json
{{
  "id_contrato": "",
  "cita_texto_ID_contrato": "",
  "fecha_suscripcion": "0000-00-00",
  "valor_inicial_contrato": 0.0,
  "valor_factura_sin_iva": 0.0,
  "valor_total_contrato": 0.0,
  "adiciones": [],
  "observaciones": "No se encontraron datos relevantes en los documentos proporcionados."
}}
```

IMPORTANTE:
- Solo respondes con JSON valido
- NO agregues explicaciones
- NO calcules nada, solo extrae
- TODAS las fechas en formato YYYY-MM-DD
- Si tienes dudas, usa los valores por defecto (0.0, "0000-00-00", "", [])

ANALIZA AHORA LOS DOCUMENTOS Y EXTRAE LA INFORMACION EN FORMATO JSON:
"""

    return prompt
