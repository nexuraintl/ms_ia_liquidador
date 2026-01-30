"""
PROMPTS PARA RETENCION EN LA FUENTE
====================================

Contiene todos los prompts especializados para análisis de retención en la fuente
usando Google Gemini AI.

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo prompts de retefuente
- OCP: Abierto para extensión - nuevos prompts sin modificar existentes
- DIP: Importa solo función auxiliar necesaria

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

import json
from typing import Dict, List

# Importar función auxiliar de prompt_clasificador
from .prompt_clasificador import _generar_seccion_archivos_directos


def PROMPT_ANALISIS_FACTURA(factura_texto: str, rut_texto: str, anexos_texto: str,
                            cotizaciones_texto: str, anexo_contrato: str, conceptos_dict: dict,
                            nombres_archivos_directos: List[str] = None, proveedor: str = None) -> str:
    """
    Genera el prompt para analizar factura y extraer información de retención.

    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        conceptos_dict: Diccionario de conceptos con tarifas y bases mínimas
        nombres_archivos_directos: Lista de nombres de archivos directos
        proveedor: Nombre del proveedor que emite la factura (v3.0)

    Returns:
        str: Prompt formateado para enviar a Gemini
    """

    # Contexto de proveedor para validación
    contexto_proveedor = ""
    if proveedor:
        contexto_proveedor = f"""
═══════════════════════════════════════════════════════════════════
 INFORMACIÓN DEL PROVEEDOR (VALIDACIÓN OBLIGATORIA)
═══════════════════════════════════════════════════════════════════

**PROVEEDOR ESPERADO:** {proveedor}

 VALIDACIONES OBLIGATORIAS CONTRA RUT (si está disponible):

1. VALIDACIÓN DE IDENTIDAD:
   - Verifica que el nombre/razón social del proveedor en FACTURA coincida con el nombre en RUT
   - Verifica que el NIT en FACTURA coincida con el NIT en RUT
   - Si hay discrepancias, repórtalas en "observaciones"


"""

    return f"""
Eres un sistema de análisis tributario colombiano para FIDUCIARIA FIDUCOLDEX.
Tu función es IDENTIFICAR con PRECISIÓN conceptos de retención en la fuente y naturaleza del tercero.

 REGLA FUNDAMENTAL: SOLO usa información EXPLÍCITAMENTE presente en los documentos.
 NUNCA inventes, asumas o deduzcas información no visible.
 Si no encuentras un dato, usa NULL o el valor por defecto especificado.
{contexto_proveedor}

═══════════════════════════════════════════════════════════════════
 CONCEPTOS VÁLIDOS DE RETENCIÓN (USA SOLO ESTOS):
═══════════════════════════════════════════════════════════════════
{json.dumps(conceptos_dict, indent=2, ensure_ascii=False)}

═══════════════════════════════════════════════════════════════════
 DOCUMENTOS PROPORCIONADOS:
═══════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}

FACTURA PRINCIPAL:
{factura_texto}

RUT DEL TERCERO:
{rut_texto if rut_texto else "[NO PROPORCIONADO]"}

ANEXOS Y DETALLES:
{anexos_texto if anexos_texto else "[NO PROPORCIONADOS]"}

COTIZACIONES:
{cotizaciones_texto if cotizaciones_texto else "[NO PROPORCIONADAS]"}

OBJETO DEL CONTRATO:
{anexo_contrato if anexo_contrato else "[NO PROPORCIONADO]"}

═══════════════════════════════════════════════════════════════════
 PROTOCOLO DE ANÁLISIS ESTRICTO:
═══════════════════════════════════════════════════════════════════

 PASO 1: VERIFICACIÓN DEL RUT
├─ Si RUT existe → Continuar al PASO 2
└─ Si RUT NO existe → Continuar al PASO 2 reportarlo en observaciones :
      "observaciones": ["RUT no disponible en documentos adjuntos"]

 PASO 2: EXTRACCIÓN DE DATOS DE LA NATURALEZA DEL PROVEEDOR 
Buscar TEXTUALMENTE la informacion en el siguiente orden RUT → FACTURA → ANEXOS:
Si no encuentras el RUT, buscar en FACTURA, si no en ANEXOS.

 TIPO DE CONTRIBUYENTE (Sección 24 o equivalente):
├─ Si encuentras "Persona natural" → es_persona_natural: true
├─ Si encuentras "Persona jurídica" → es_persona_natural: false
└─ Si NO encuentras → es_persona_natural: null

 RÉGIMEN TRIBUTARIO (Buscar texto exacto):
├─ Si encuentras "RÉGIMEN SIMPLE" o "SIMPLE" o codigo "O-47" → regimen_tributario: "SIMPLE"
├─ Si encuentras "RÉGIMEN ORDINARIO" , "ORDINARIO" o "régimen ordinar" → regimen_tributario: "ORDINARIO"
├─ Si encuentras "RÉGIMEN ESPECIAL", "ESPECIAL" o "SIN ÁNIMO DE LUCRO" → regimen_tributario: "ESPECIAL"
└─ Si NO encuentras → regimen_tributario: null

 AUTORRETENEDOR:
├─ Si encuentras texto "ES AUTORRETENEDOR" o codigo "O-15" → es_autorretenedor: true
└─ Si NO encuentras esa frase → es_autorretenedor: false

CODIGO COMODIN DIAN :
├─ Si encuentras codigo "R-99-PN" →  regimen_tributario: "ORDINARIO" 

IMPORTANTE : Si encuentras el RUT, prioriza la información de naturaleza del RUT sobre los demas documentos.

 PASO 3: IDENTIFICACIÓN DE CONCEPTOS

 REGLAS DE IDENTIFICACIÓN:
1. Buscar SOLO en la FACTURA los conceptos EXACTOS facturados "concepto_facturado"
1.1 Si no encuentras los CONCEPTOS FACTURADOS  → "concepto_facturado": "" → (string vacío)
2. IMPORTANTE: IDENTIFICA LA FACTURA BUSCANDO EXPLICITAMENTE EL DOCUMENTO QUE DIGA "FACTURA" O "FACTURA ELECTRÓNICA DE VENTA"
3. RELACIONA los conceptos facturados encontrados con los nombres en CONCEPTOS VÁLIDOS
4. IMPORTANTE: Solo puedes relacionar un concepto facturado con UN concepto del diccionario
5. IMPORTANTE: El diccionario CONCEPTOS VÁLIDOS tiene formato {{descripcion: index}}
6. PUEDEN HABER MULTIPLES CONCEPTOS FACTURADOS en la misma factura

 MATCHING DE CONCEPTOS - ESTRICTO:
├─ Si encuentras coincidencia EXACTA → usar ese concepto + su index del diccionario
├─ Si encuentras coincidencia PARCIAL clara → usar el concepto más específico + su index
├─ Si NO hay coincidencia clara → "CONCEPTO_NO_IDENTIFICADO" con concepto_index: 0
├─  NUNCA inventes un concepto que no esté en la lista
└─ REVISA TODA LA LISTA DE CONCEPTOS VALIDOS ANTES DE ASIGNARLO

 EXTRACCIÓN DE VALORES:
├─ Usar SOLO valores numéricos presentes en documentos
├─ Si hay múltiples conceptos → extraer cada valor por separado
├─ NUNCA calcules o inventes valores
└─ "valor_total" es el valor total de la FACTURA SIN IVA

 PASO 5: VALIDACIÓN DE COHERENCIA
├─ Si hay incongruencia → mencionalo en observaciones
└─ Documentar TODA anomalía en observaciones

═══════════════════════════════════════════════════════════════════
 PROHIBICIONES ABSOLUTAS:
═══════════════════════════════════════════════════════════════════
 NO inventes información no presente en documentos
 NO asumas valores por defecto excepto los especificados
 NO modifiques nombres de conceptos del diccionario
 NO calcules valores no mostrados
 NO deduzcas el régimen tributario por el tipo de empresa
 NO asumas que alguien es autorretenedor sin confirmación explícita
 NO extraigas conceptos facturados de documentos que NO sean la FACTURA
═══════════════════════════════════════════════════════════════════
 FORMATO DE RESPUESTA OBLIGATORIO (JSON ESTRICTO):
═══════════════════════════════════════════════════════════════════
{{
    "conceptos_identificados": [
        {{
            "concepto_facturado": "Nombre exacto del concepto facturado" o "",
            "concepto": "Nombre exacto relacionado del diccionario o CONCEPTO_NO_IDENTIFICADO",
            "concepto_index": número del index del diccionario o 0,
            "base_gravable": número encontrado o 0.0
        }}
    ],
    "naturaleza_tercero": {{
        "es_persona_natural": true | false | null,
        "regimen_tributario": "SIMPLE" | "ORDINARIO" | "ESPECIAL" | null,
        "es_autorretenedor": true | false
    }},
    "valor_total": número encontrado o 0.0,
    "observaciones": ["Lista de observaciones relevantes"]
}}

 RESPONDE ÚNICAMENTE CON EL JSON. SIN EXPLICACIONES ADICIONALES.
"""


def PROMPT_ANALISIS_ART_383(factura_texto: str, rut_texto: str, anexos_texto: str,
                            cotizaciones_texto: str, anexo_contrato: str,
                            nombres_archivos_directos: List[str] = None,
                            conceptos_identificados: List = None) -> str:

    # Importar constantes del Artículo 383
    from config import obtener_constantes_articulo_383

    constantes_art383 = obtener_constantes_articulo_383()

    return f"""
Eres un sistema de validación del Artículo 383 del Estatuto Tributario Colombiano para FIDUCIARIA FIDUCOLDEX.
Tu función es VERIFICAR si aplican deducciones especiales para personas naturales.

 REGLA FUNDAMENTAL: SOLO reporta información TEXTUALMENTE presente en documentos.
 NUNCA asumas, deduzcas o inventes información no visible.
 Si no encuentras un dato específico, usa el valor por defecto indicado.

═══════════════════════════════════════════════════════════════════
 DATOS DE REFERENCIA ART. 383:
═══════════════════════════════════════════════════════════════════
CONCEPTOS QUE APLICAN PARA ART. 383:
{json.dumps(constantes_art383['conceptos_aplicables'], indent=2, ensure_ascii=False)}

CONCEPTOS YA IDENTIFICADOS EN ANÁLISIS PREVIO:
{json.dumps(conceptos_identificados, indent=2, ensure_ascii=False)}

═══════════════════════════════════════════════════════════════════
 DOCUMENTOS DISPONIBLES PARA ANÁLISIS:
═══════════════════════════════════════════════════════════════════
{_generar_seccion_archivos_directos(nombres_archivos_directos)}

FACTURA PRINCIPAL:
{factura_texto if factura_texto else "[NO PROPORCIONADA]"}

RUT DEL TERCERO:
{rut_texto if rut_texto else "[NO PROPORCIONADO]"}

ANEXOS:
{anexos_texto if anexos_texto else "[NO PROPORCIONADOS]"}

COTIZACIONES:
{cotizaciones_texto if cotizaciones_texto else "[NO PROPORCIONADAS]"}

OBJETO DEL CONTRATO:
{anexo_contrato if anexo_contrato else "[NO PROPORCIONADO]"}

═══════════════════════════════════════════════════════════════════
 PROTOCOLO DE VERIFICACIÓN ESTRICTO - ARTÍCULO 383:
═══════════════════════════════════════════════════════════════════

 PASO 1: VERIFICAR TIPO DE CONTRIBUYENTE
├─ Buscar EN EL RUT → Sección 24 o "Tipo de contribuyente"
├─ Si encuentra "Persona natural" o "natural" → es_persona_natural: true
├─ Si encuentra "Persona jurídica" → es_persona_natural: false
├─ Si NO encuentra RUT → Buscar en FACTURA y ANEXOS en ese orden
└─ Si NO encuentra información → es_persona_natural: false (DEFAULT)

 PASO 2: VALIDAR CONCEPTOS APLICABLES AL ART. 383

 REGLA DE MATCHING ESTRICTA:
Para CADA concepto en conceptos_identificados:
  1. Comparar TEXTUALMENTE con lista de conceptos_aplicables Art. 383
  2. CRITERIOS DE COINCIDENCIA:
     ├─ Coincidencia EXACTA del texto → INCLUIR
     ├─ Palabras clave coinciden (honorarios, servicios, comisiones) → INCLUIR
     └─ NO hay coincidencia clara → EXCLUIR

 RESULTADO:
├─ Si HAY conceptos que coinciden → Agregar a conceptos_identificados con sus valores
├─ Si hay conceptos que coinciden → conceptos_aplicables: true
├─ Si NO hay coincidencias → conceptos_identificados: [] (lista vacía)
└─ Si NO hay coincidencias → conceptos_aplicables: false

 PASO 3: DETECTAR PRIMER PAGO

 BUSCAR TEXTUALMENTE en FACTURA y ANEXOS estas frases EXACTAS:
├─ "primer pago"
├─ "pago inicial"
├─ "anticipo"
├─ "pago adelantado"
├─ "primera cuota"
├─ "entrega inicial"
├─ "adelanto"
├─ "pago #1" o "pago 1" o "pago 001"
├─ "inicio de contrato"
└─ "pago de arranque"

 RESULTADO:
├─ Si encuentras ALGUNA frase → es_primer_pago: true
└─ Si NO encuentras ALGUNA → es_primer_pago: false (DEFAULT)

 PASO 4: BUSCAR PLANILLA DE SEGURIDAD SOCIAL Y EXTRAER IBC

 BUSCAR en ANEXOS palabras clave:
├─ "planilla" Y ("salud" O "pensión" O "seguridad social" O "PILA")
├─ "aportes" Y ("EPS" O "AFP" O "parafiscales")
└─ "pago seguridad social"

 SI ENCUENTRA PLANILLA:
├─ planilla_seguridad_social: true
├─ Buscar fecha en formato: DD/MM/AAAA o AAAA-MM-DD o "mes de XXXX"
│  ├─ Si encuentra fecha → fecha_de_planilla_seguridad_social: "AAAA-MM-DD"
│  └─ Si NO encuentra fecha → fecha_de_planilla_seguridad_social: "0000-00-00"
├─ BUSCAR Y EXTRAER IBC (Ingreso Base de Cotización):
│  ├─ Buscar "IBC" o "Ingreso Base de Cotización" o "Base de cotización"
│  ├─ Si encuentra valor → IBC_seguridad_social: [valor extraído]
│  └─ Si NO encuentra → IBC_seguridad_social: 0.0
│
└─ IMPORTANTE: El IBC SOLO se extrae de la PLANILLA DE SEGURIDAD SOCIAL

 SI NO ENCUENTRA PLANILLA:
├─ planilla_seguridad_social: false (DEFAULT)
├─ fecha_de_planilla_seguridad_social: "0000-00-00" (DEFAULT)
└─ IBC_seguridad_social: 0.0 (DEFAULT)

 PASO 5: VERIFICAR DOCUMENTO SOPORTE Y EXTRAER VALOR DE INGRESO

 BUSCAR en documentos estas palabras EXACTAS:
├─ "cuenta de cobro"
├─ "factura de venta"
├─ "documento soporte"
└─ "no obligado a facturar"

 SI ENCUENTRA "DOCUMENTO SOPORTE":
├─ Documento_soporte: true
├─ BUSCAR Y EXTRAER VALOR DE INGRESO DEL DOCUMENTO SOPORTE:
│  ├─ Buscar palabras clave EN EL DOCUMENTO SOPORTE: "valor", "total", "honorarios", "servicios prestados"
│  ├─ Identificar el monto principal facturado (sin IVA ni retenciones)
│  ├─ Si encuentra valor → ingreso: [valor extraído]
│  └─ Si NO encuentra valor → ingreso: 0.0
│
└─ IMPORTANTE:
   └─ Si hay múltiples documentos soporte, priorizar el valor del ingreso de la cuenta de cobro

 SI NO ENCUENTRA "DOCUMENTO SOPORTE":
├─ Documento_soporte: false (DEFAULT)
└─ ingreso: 0.0 (DEFAULT) - No extraer de otros documentos

 RESULTADO:
├─ Si encuentra documento soporte → documento_soporte: true + extraer ingreso
└─ Si NO encuentra → documento_soporte: false + ingreso: 0.0

 PASO 6: IDENTIFICAR DEDUCCIONES (BÚSQUEDA TEXTUAL ESTRICTA)

 INTERESES POR VIVIENDA:
BUSCAR: "intereses" Y ("vivienda" O "hipoteca" O "crédito hipotecario")
├─ Si encuentra certificación bancaria:
│  ├─ Extraer valor numérico de "intereses corrientes" → intereses_corrientes: [valor]
│  └─ certificado_bancario: true
└─ Si NO encuentra:
   ├─ intereses_corrientes: 0.0 (DEFAULT)
   └─ certificado_bancario: false (DEFAULT)

 DEPENDIENTES ECONÓMICOS:
BUSCAR: "dependiente" O "declaración juramentada" Y "económico"
├─ Si encuentra declaración:
│  ├─ Extraer nombre del titular encargado si está presente → nombre_encargado: "[nombre]"
│  └─ declaracion_juramentada: true
└─ Si NO encuentra:
   ├─ nombre_encargado: "" (DEFAULT)
   └─ declaracion_juramentada: false (DEFAULT)

 MEDICINA PREPAGADA:
BUSCAR: "medicina prepagada" O "plan complementario" O "póliza de salud"
├─ Si encuentra certificación:
│  ├─ Extraer valor "sin IVA" o "valor neto" → valor_sin_iva_med_prepagada: [valor]
│  └─ certificado_med_prepagada: true
└─ Si NO encuentra:
   ├─ valor_sin_iva_med_prepagada: 0.0 (DEFAULT)
   └─ certificado_med_prepagada: false (DEFAULT)

 AFC (AHORRO PARA FOMENTO A LA CONSTRUCCIÓN):
BUSCAR: "AFC" O "ahorro para fomento" O "cuenta AFC"
├─ Si encuentra soporte:
│  ├─ Extraer "valor a depositar" → valor_a_depositar: [valor]
│  └─ planilla_de_cuenta_AFC: true
└─ Si NO encuentra:
   ├─ valor_a_depositar: 0.0 (DEFAULT)
   └─ planilla_de_cuenta_AFC: false (DEFAULT)

═══════════════════════════════════════════════════════════════════
 REGLAS ABSOLUTAS - NO NEGOCIABLES:
═══════════════════════════════════════════════════════════════════
 NO inventes valores numéricos - usa 0.0 si no los encuentras
 NO asumas fechas - usa "0000-00-00" si no las encuentras
 NO deduzcas información por contexto
 NO completes campos vacíos con suposiciones
 NO interpretes - solo busca texto LITERAL
 NO calcules valores derivados
 IBC solo se extrae de PLANILLA DE SEGURIDAD SOCIAL

═══════════════════════════════════════════════════════════════════
 FORMATO JSON DE RESPUESTA OBLIGATORIO:
═══════════════════════════════════════════════════════════════════
{{
    "articulo_383": {{
        "condiciones_cumplidas": {{
            "es_persona_natural": boolean (default: false),
            "conceptos_identificados": [
                {{
                    "concepto": "texto exacto del concepto",
                    "base_gravable": número encontrado o 0.0
                }}
            ] o [],
            "conceptos_aplicables": boolean (true si hay conceptos que aplican, false si no aplican),
            "ingreso": número o 0.0 ,
            "es_primer_pago": boolean (default: false),
            "documento_soporte": boolean (default: false)
        }},
        "deducciones_identificadas": {{
            "intereses_vivienda": {{
                "intereses_corrientes": número o 0.0,
                "certificado_bancario": boolean (default: false)
            }},
            "dependientes_economicos": {{
                "nombre_encargado": "texto encontrado" o "",
                "declaracion_juramentada": boolean (default: false)
            }},
            "medicina_prepagada": {{
                "valor_sin_iva_med_prepagada": número o 0.0,
                "certificado_med_prepagada": boolean (default: false)
            }},
            "AFC": {{
                "valor_a_depositar": número o 0.0,
                "planilla_de_cuenta_AFC": boolean (default: false)
            }},
            "planilla_seguridad_social": {{
                "IBC_seguridad_social": número o 0.0 (SOLO de planilla)
                "planilla_seguridad_social": boolean (default: false),
                "fecha_de_planilla_seguridad_social": "AAAA-MM-DD" (default: "0000-00-00")
            }}
        }}
    }}
}}

 RESPONDE ÚNICAMENTE CON EL JSON. SIN EXPLICACIONES ADICIONALES.
"""


def PROMPT_EXTRACCION_CONSORCIO(factura_texto: str, rut_texto: str, anexos_texto: str,
                                cotizaciones_texto: str, anexo_contrato: str,
                                nombres_archivos_directos: List[str] = None, proveedor: str = None) -> str:
    """
    Genera el prompt para PRIMERA LLAMADA: Extraccion de datos crudos del consorcio.
    NO hace matching de conceptos, solo extrae nombres literales.

    Args:
        factura_texto: Texto extraido de la factura principal
        rut_texto: Texto del RUT (si esta disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        nombres_archivos_directos: Lista de nombres de archivos directos
        proveedor: Nombre del consorcio/union temporal (v3.0)

    Returns:
        str: Prompt formateado para extraer datos sin matching
    """

    # Contexto de proveedor para validacion de consorcio
    contexto_proveedor = ""
    if proveedor:
        contexto_proveedor = f"""
═══════════════════════════════════════════════════════════════════
INFORMACION DEL CONSORCIO/UNION TEMPORAL (VALIDACION OBLIGATORIA)
═══════════════════════════════════════════════════════════════════

**CONSORCIO/UNION TEMPORAL ESPERADO:** {proveedor}

VALIDACIONES OBLIGATORIAS PARA CONSORCIOS:

1. VALIDACION DE IDENTIDAD DEL CONSORCIO:
   - Verifica que el nombre del consorcio en FACTURA coincida con el esperado: "{proveedor}"
   - Verifica que el nombre del consorcio en RUT coincida con FACTURA
   - Si hay discrepancias, reportalas en "observaciones"

2. VALIDACION DE CONSORCIADOS/INTEGRANTES:
   - Busca RUT individual de cada consorciado en los anexos

3. VALIDACION CONTRA RUT DEL CONSORCIO:
   - Verifica que el NIT del consorcio en FACTURA coincida con RUT

4. VALIDACION DE COHERENCIA:
   - El nombre del consorcio esperado debe aparecer en FACTURA y RUT
   - Los consorciados deben estar claramente identificados

5. REPORTE DE INCONSISTENCIAS:
   - Si nombre consorcio en FACTURA ≠ nombre esperado → agregar a observaciones
   - Si nombre consorcio en FACTURA ≠ nombre en RUT → agregar a observaciones
   - Si NIT del consorcio no coincide entre documentos → agregar a observaciones

"""

    return f"""
Eres un sistema de extraccion de datos tributarios colombianos para FIDUCIARIA FIDUCOLDEX.
Tu funcion es EXTRAER con PRECISION datos de CONSORCIOS y UNIONES TEMPORALES.

REGLA FUNDAMENTAL: SOLO usa informacion EXPLICITAMENTE presente en los documentos.
NUNCA inventes, asumas o deduzcas informacion no visible.
Si no encuentras un dato, usa NULL o el valor por defecto especificado.
{contexto_proveedor}

═══════════════════════════════════════════════════════════════════
DOCUMENTOS PROPORCIONADOS:
═══════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}

FACTURA PRINCIPAL:
{factura_texto}

RUT DEL TERCERO:
{rut_texto if rut_texto else "[NO PROPORCIONADO]"}

ANEXOS Y DETALLES:
{anexos_texto if anexos_texto else "[NO PROPORCIONADOS]"}

COTIZACIONES:
{cotizaciones_texto if cotizaciones_texto else "[NO PROPORCIONADAS]"}

OBJETO DEL CONTRATO:
{anexo_contrato if anexo_contrato else "[NO PROPORCIONADO]"}

═══════════════════════════════════════════════════════════════════
REGLA CRITICA DE FORMATO DE SALIDA:
═══════════════════════════════════════════════════════════════════

IMPORTANTE: Debes retornar SIEMPRE UN SOLO JSON de salida.
  - Incluso si hay multiples documentos de diferentes proveedores
  - Analiza el documento principal (factura/orden de pago)
  - Si hay informacion contradictoria entre documentos, reportala en "observaciones"
  - NO generes un array de JSONs con multiples objetos
  - SOLO retorna UN objeto JSON unico

═══════════════════════════════════════════════════════════════════
PROTOCOLO DE EXTRACCION ESTRICTO:
═══════════════════════════════════════════════════════════════════

PASO 1: IDENTIFICACION DEL TIPO DE ENTIDAD
Buscar en RUT y documentos:
├─ Si encuentras "CONSORCIO" → es_consorcio: true
├─ Si encuentras "UNION TEMPORAL" o "UNION TEMPORAL" → es_consorcio: true
├─ Si encuentras "CONSORCIO" o "UNION TEMPORAL" extrae el nombre general del Consorcio/Union
└─ Si NO encuentras ninguno → es_consorcio: false y asignar analisis con los valores en 0.0 o null o ""

═══════════════════════════════════════════════════════════════════
PROTOCOLO ESPECIAL PARA CONSORCIOS/UNIONES TEMPORALES:
═══════════════════════════════════════════════════════════════════

Si es_consorcio == true:

PASO A: IDENTIFICAR TODOS LOS CONSORCIADOS
Buscar en ESTE ORDEN:
1. Seccion "CONSORCIADOS" o "INTEGRANTES" en el RUT principal
2. Tabla de participacion en facturas o anexos
3. Documento de constitucion del consorcio
4. Cualquier documento que liste los integrantes

Para CADA consorciado extraer:
├─ NIT/Cedula: Numero exacto sin puntos ni guiones
├─ Nombre/Razon Social: Nombre completo tal como aparece
├─ Porcentaje participacion: Extraer SOLO el numero del porcentaje (ej: si encuentras "30%" → 30, si encuentras "0.4%" → 0.4, si encuentras "25.5%" → 25.5)
└─ Si no hay porcentaje → porcentaje_participacion: null

PASO B: ANALIZAR CADA CONSORCIADO INDIVIDUALMENTE
Para CADA consorciado identificado:
1. Buscar su RUT individual en los anexos (archivo con su NIT)
2. Si encuentra RUT individual → Extraer naturaleza tributaria del RUT  
3. Si NO encuentra RUT → Extractar naturaleza tributaria de la FACTURA o ANEXOS en ese orden

Extraer del RUT INDIVIDUAL de cada consorciado:
TIPO DE CONTRIBUYENTE (Seccion 24 o equivalente):
├─ Si encuentras "Persona natural" → es_persona_natural: true
├─ Si encuentras "Persona juridica" → es_persona_natural: false
└─ Si NO encuentras → es_persona_natural: null

REGIMEN TRIBUTARIO (Buscar texto exacto):
├─ Si encuentras "REGIMEN SIMPLE" o "SIMPLE" → regimen_tributario: "SIMPLE"
├─ Si encuentras "REGIMEN ORDINARIO" , "ORDINARIO" o "regimen ordinar"  → regimen_tributario: "ORDINARIO"
├─ Si encuentras "REGIMEN ESPECIAL", "ESPECIAL" o "SIN ANIMO DE LUCRO" → regimen_tributario: "ESPECIAL"
└─ Si NO encuentras → regimen_tributario: null

AUTORRETENEDOR:
├─ Si encuentras texto "ES AUTORRETENEDOR" → es_autorretenedor: true
└─ Si NO encuentras esa frase → es_autorretenedor: false

PASO C: EXTRAER CONCEPTOS LITERALES
Identificar los servicios/bienes facturados:
├─ Extraer el nombre LITERAL del concepto tal como aparece en la factura
├─ SOLO extrae el texto exacto que describe el servicio/bien
└─ Extrae la base_gravable asociada a cada concepto

EJEMPLO:
Si la factura dice "Servicios de consultoria especializada" → nombre_concepto: "Servicios de consultoria especializada"
Si dice "Honorarios profesionales mes de octubre" → nombre_concepto: "Honorarios profesionales mes de octubre"

PASO D: EXTRAER VALORES
├─ valor_total: Valor total de la factura SIN IVA
├─ base_gravable: Para cada concepto facturado identificado
└─ Si no encuentras valores claros → usar 0.0

═══════════════════════════════════════════════════════════════════
PROHIBICIONES ABSOLUTAS:
═══════════════════════════════════════════════════════════════════
NO inventes consorciados no listados
NO asumas porcentajes de participacion
NO deduzcas naturaleza sin informacion especifica
NO mapees conceptos a categorias tributarias (solo extrae literal)
NO calcules valores no mostrados
NO asumas que consorciados tienen misma naturaleza

═══════════════════════════════════════════════════════════════════
FORMATO DE RESPUESTA (JSON ESTRICTO):
═══════════════════════════════════════════════════════════════════

FORMATO SI ES CONSORCIO/UNION TEMPORAL:
{{
    "es_consorcio": true,
    "nombre_consorcio": "Nombre del Consorcio/Union Temporal",
    "conceptos_literales": [
        {{
            "nombre_concepto": "Texto LITERAL extraido de la factura ",
            "base_gravable": numero extraido de la factura o 0.0
        }}
    ],
    "consorciados": [
        {{
            "nit": "numero identificacion",
            "nombre": "razon social completa",
            "porcentaje_participacion": numero o null,
            "tiene_rut_individual": boolean,
            "naturaleza_tributaria": {{
                "es_persona_natural": true | false | null,
                "regimen_tributario": "SIMPLE" | "ORDINARIO" | "ESPECIAL" | null,
                "es_autorretenedor": true | false | null
            }}
        }}
    ],
    "valor_total": numero encontrado o 0.0,
    "observaciones": ["Lista de observaciones"]
}}

FORMATO SI NO ES CONSORCIO:
{{
    "es_consorcio": false,
    "nombre_consorcio": null,
    "conceptos_literales": [],
    "consorciados": [],
    "valor_total": 0.0,
    "observaciones": ["No se identifico como consorcio o union temporal"]
}}

    """


def PROMPT_MATCHING_CONCEPTOS(conceptos_literales: List[Dict[str, any]], conceptos_dict: dict) -> str:
    """
    Genera el prompt para SEGUNDA LLAMADA: Matching de conceptos literales con base de datos.
    Solo hace matching, no extrae ni calcula nada.

    Args:
        conceptos_literales: Lista de conceptos literales extraidos (con nombre_concepto y base_gravable)
        conceptos_dict: Diccionario de conceptos validos (formato: {descripcion: index})

    Returns:
        str: Prompt formateado para hacer matching

    Nota:
        La tarifa_retencion NO se incluye aqui porque se obtiene despues de la base de datos
        usando el concepto_index. El diccionario solo tiene {descripcion: index}.
    """

    # Convertir lista de conceptos literales a formato legible
    conceptos_a_mapear = []
    for idx, concepto in enumerate(conceptos_literales, 1):
        nombre = concepto.get("nombre_concepto", "")
        base = concepto.get("base_gravable", 0.0)
        conceptos_a_mapear.append(f"{idx}. \"{nombre}\" (Base: ${base:,.2f})")

    conceptos_texto = "\n".join(conceptos_a_mapear)

    return f"""
Eres un experto en clasificacion tributaria colombiana para FIDUCIARIA FIDUCOLDEX.
Tu UNICA funcion es MAPEAR conceptos literales a conceptos tributarios validos.

═══════════════════════════════════════════════════════════════════
TAREA ESPECIFICA:
═══════════════════════════════════════════════════════════════════

Dado un concepto literal extraido de una factura, debes:
1. Identificar el concepto tributario MAS ESPECIFICO que aplica
2. Obtener su concepto_index del diccionario
3. Si NO hay coincidencia clara → usar "CONCEPTO_NO_IDENTIFICADO" con concepto_index: 0

IMPORTANTE: NO incluyas tarifa_retencion en tu respuesta.
La tarifa se obtendra despues consultando la base de datos con el concepto_index.

═══════════════════════════════════════════════════════════════════
CONCEPTOS A MAPEAR (EXTRAIDOS DE LA FACTURA):
═══════════════════════════════════════════════════════════════════

{conceptos_texto}

═══════════════════════════════════════════════════════════════════
CONCEPTOS TRIBUTARIOS VALIDOS (USA SOLO ESTOS):
═══════════════════════════════════════════════════════════════════

IMPORTANTE: Este diccionario tiene formato {{descripcion: index}}
Debes buscar la descripcion que mejor coincida y usar su index.

{json.dumps(conceptos_dict, indent=2, ensure_ascii=False)}

═══════════════════════════════════════════════════════════════════
REGLAS DE MATCHING ESTRICTAS:
═══════════════════════════════════════════════════════════════════

CRITERIOS DE COINCIDENCIA (en orden de prioridad):

1. COINCIDENCIA EXACTA:
   - Si el concepto literal coincide palabra por palabra → usar ese concepto

2. COINCIDENCIA POR PALABRAS CLAVE:
   Ejemplos de palabras clave que indican conceptos especificos:

   "honorarios" → Buscar en conceptos de honorarios profesionales
   "arrendamiento" → Buscar en conceptos de arrendamiento
   "servicios" → Buscar en conceptos de servicios
   "consultoria" → Servicios generales o servicios tecnicos
   "transporte" → Servicios de transporte
   "licencias", "software" → Licenciamiento de software
   "publicidad", "marketing" → Servicios de publicidad
   "construccion", "obra" → Servicios de construccion
   "mantenimiento" → Servicios de mantenimiento
   "capacitacion", "formacion" → Servicios de capacitacion
   "interventoria" → Servicios de interventoria

3. COINCIDENCIA POR CATEGORIA:
   - Si el concepto literal describe una categoria amplia → usar el concepto generico
   - Ejemplo: "Servicios varios" → "Servicios generales (declarantes)"

4. NO HAY COINCIDENCIA:
   - Si NO encuentras ninguna coincidencia razonable → "CONCEPTO_NO_IDENTIFICADO"
   - concepto_index: 0

═══════════════════════════════════════════════════════════════════
PROHIBICIONES ABSOLUTAS:
═══════════════════════════════════════════════════════════════════
NO inventes conceptos que no esten en el diccionario
NO modifiques los nombres de los conceptos del diccionario
NO incluyas tarifa_retencion (se obtiene de la base de datos)
NO mapees conceptos ambiguos sin justificacion clara
Si tienes duda → usar "CONCEPTO_NO_IDENTIFICADO"

═══════════════════════════════════════════════════════════════════
FORMATO DE RESPUESTA (JSON ESTRICTO):
═══════════════════════════════════════════════════════════════════

Retorna un JSON con esta estructura EXACTA:

{{
    "conceptos_mapeados": [
        {{
            "nombre_concepto": "Texto literal del concepto (igual al input)",
            "concepto": "Nombre EXACTO del concepto del diccionario o CONCEPTO_NO_IDENTIFICADO",
            "concepto_index": numero del index del diccionario o 0,
            "justificacion": "Breve explicacion del matching (opcional)"
        }}
    ]
}}

IMPORTANTE:
- La lista de conceptos_mapeados debe tener el MISMO ORDEN que los conceptos a mapear
- Debe haber EXACTAMENTE UN resultado por cada concepto de entrada
- El campo "nombre_concepto" debe ser IDENTICO al concepto literal de entrada
- NO incluir tarifa_retencion (se obtendra de la base de datos usando concepto_index)

EJEMPLO DE RESPUESTA:
{{
    "conceptos_mapeados": [
        {{
            "nombre_concepto": "Servicios de consultoria especializada",
            "concepto": "Servicios generales (declarantes)",
            "concepto_index": 1,
            "justificacion": "Consultoria se clasifica como servicios generales"
        }},
        {{
            "nombre_concepto": "Arrendamiento oficina Bogota",
            "concepto": "Arrendamiento de bienes inmuebles",
            "concepto_index": 5,
            "justificacion": "Coincidencia exacta con categoria arrendamiento"
        }}
    ]
}}

    """


def PROMPT_ANALISIS_FACTURA_EXTRANJERA(factura_texto: str, rut_texto: str, anexos_texto: str,
                                       cotizaciones_texto: str, anexo_contrato: str,
                                       conceptos_extranjeros_simplificado: dict,
                                       nombres_archivos_directos: List[str] = None,
                                       proveedor: str = None) -> str:
    """
    Genera prompt para análisis de factura extranjera - SOLO EXTRACCIÓN (sin cálculos).

    RESPONSABILIDAD: Gemini solo identifica y mapea conceptos.
    Los cálculos, validaciones y tarifas se manejan en Python (liquidador.py).

    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        conceptos_extranjeros_simplificado: Diccionario {index: nombre_concepto}
        nombres_archivos_directos: Lista de nombres de archivos directos
        proveedor: Nombre del proveedor extranjero

    Returns:
        str: Prompt formateado para enviar a Gemini
    """

    # Contexto de proveedor
    contexto_proveedor = ""
    if proveedor:
        contexto_proveedor = f"""
═══════════════════════════════════════════════════════════════════
INFORMACIÓN DEL PROVEEDOR ESPERADO
═══════════════════════════════════════════════════════════════════

**PROVEEDOR:** {proveedor}

VALIDACIONES:
- Verifica coherencia entre nombre en FACTURA y proveedor esperado
- Si hay discrepancias, repórtalas en "observaciones"

"""

    return f"""
    Eres un experto contador colombiano especializado en EXTRACCIÓN DE DATOS para pagos al exterior.
{contexto_proveedor}

    DICCIONARIO DE CONCEPTOS (index: nombre):
    {json.dumps(conceptos_extranjeros_simplificado, indent=2, ensure_ascii=False)}

    DOCUMENTOS DISPONIBLES:

    FACTURA (DOCUMENTO PRINCIPAL):
    {factura_texto}

    RUT (si está disponible):
    {rut_texto if rut_texto else "NO DISPONIBLE"}

    ANEXOS:
    {anexos_texto if anexos_texto else "NO DISPONIBLES"}

    COTIZACIONES:
    {cotizaciones_texto if cotizaciones_texto else "NO DISPONIBLES"}

    ANEXO CONCEPTO CONTRATO:
    {anexo_contrato if anexo_contrato else "NO DISPONIBLES"}

    ═══════════════════════════════════════════════════════════════════
    INSTRUCCIONES - SOLO EXTRACCIÓN E IDENTIFICACIÓN
    ═══════════════════════════════════════════════════════════════════

    TU ÚNICA RESPONSABILIDAD: Extraer datos e identificar conceptos.

    NO hagas cálculos, NO apliques tarifas, NO determines si aplica retención.
    Eso lo hará Python después con validaciones manuales.

    1. **IDENTIFICAR PAÍS DEL PROVEEDOR**:
       - Busca TEXTUALMENTE en la FACTURA el país del proveedor
       - Busca en: dirección, domicilio, sede, país de origen
       - Si lo encuentras, guarda en "pais_proveedor" en minúsculas, sin tildes y traducido al español
       - Ejemplo: "Estados Unidos" → "estados unidos"
       - Guarda el TEXTO LITERAL extraido del documento en "pais_proveedor_literal"

       - Si no encuentras, deja vacío ""

    2. **IDENTIFICAR CONCEPTOS FACTURADOS**:
       - Extrae el TEXTO LITERAL del concepto/servicio facturado
       - Ejemplo: "Servicios profesionales de consultoría"
       - Guarda en "concepto_facturado"

    3. **MAPEAR CON DICCIONARIO**:
       - Relaciona el concepto_facturado con el diccionario recibido
       - Usa el NOMBRE EXACTO que aparece en el diccionario
       - Guarda en "concepto" y su "concepto_index"
       - Si NO encuentras coincidencia: concepto="" y concepto_index=0

    4. **EXTRAER BASE GRAVABLE**:
       - Por cada concepto, extrae el valor base
       - Si hay múltiples conceptos, sepáralos individualmente

    5. **EXTRAER VALOR TOTAL**:
       - Extrae el valor total de la factura sin IVA
       - Si no puedes determinarlo, usa 0.0

    6. **OBSERVACIONES**:
       - Reporta cualquier inconsistencia o dato faltante
       - NO hagas interpretaciones fiscales

    IMPORTANTE:
    - EL NOMBRE DEL PAIS DEBE ESTAR EN ESPAÑOL, minúsculas y sin tildes en "pais_proveedor"

    EJEMPLOS:

    Ejemplo 1:
    - Factura dice: "Servicios de consultoría técnica - $5,000 USD"
    - País en factura: "Estados Unidos"
    - En diccionario encuentras: index 101 → "Servicios técnicos y de consultoría"
    - Respuesta:
      {{
        "pais_proveedor": "estados unidos",
        "pais_proveedor_literal": "United States",
        "concepto_facturado": "Servicios de consultoría técnica",
        "concepto": "Servicios técnicos y de consultoría",
        "concepto_index": 101,
        "base_gravable": 5000.0
      }}

    Ejemplo 2 - No se encuentra concepto:
    - Factura dice: "Regalías por marca"
    - No hay coincidencia en diccionario
    - Respuesta:
      {{
        "pais_proveedor": "españa",
        "pais_proveedor_literal": "Spain",
        "concepto_facturado": "Regalías por marca",
        "concepto": "",
        "concepto_index": 0,
        "base_gravable": 10000.0
      }}

    RESPONDE ÚNICAMENTE EN FORMATO JSON VÁLIDO SIN TEXTO ADICIONAL:
    {{
        "pais_proveedor": "string o empty string",
        "conceptos_identificados": [
            {{
                "concepto_facturado": "Texto literal de la factura",
                "concepto": "Nombre del diccionario o empty string",
                "concepto_index": 123,
                "base_gravable": 0.0
            }}
        ],
        "valor_total": 0.0,
        "observaciones": ["observación 1"]
    }}
    """
