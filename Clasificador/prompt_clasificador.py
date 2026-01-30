"""
PROMPTS PARA CLASIFICACIÓN DE DOCUMENTOS
========================================

Plantillas de prompts utilizadas por el clasificador de documentos.
"""

import json
from typing import Dict



def PROMPT_CLASIFICACION(textos_archivos: Dict[str, str]) -> str:
    """
    Genera el prompt para clasificar documentos fiscales colombianos.
    
    Args:
        textos_archivos: Diccionario con nombre_archivo -> texto_extraido
        
    Returns:
        str: Prompt formateado para enviar a Gemini
    """
    
    return f"""
Eres un experto en documentos fiscales colombianos. Tu tarea es clasificar cada uno de los siguientes documentos en una de estas categorías exactas:
- FACTURA
- RUT  
- COTIZACION
- ANEXO
- ANEXO CONCEPTO DE CONTRATO

INSTRUCCIONES:
1. Analiza cada documento y clasifícalo en UNA sola categoría
2. Una FACTURA contiene información de facturación, valores, impuestos, datos del proveedor
3. Un RUT es el Registro Único Tributario que contiene información fiscal del tercero
4. Una COTIZACION es una propuesta comercial o presupuesto
5. ANEXO es cualquier otro documento de soporte
6. El anexo concepto de contrato, contiene SOLO informacion del contrato, como el OBJETO
7. EL DOCUMENTO "SOPORTE EN ADQUISICIONES EFECTUADAS A NO OBLIGADOS A FACTURAR" ES EQUIVALENTE A UNA "FACTURA"

**DETECCIÓN DE FACTURACIÓN EXTRANJERA:**
8. Verifica si se trata de FACTURACIÓN EXTRANJERA analizando:
   - Si el proveedor tiene domicilio o dirección fuera de Colombia
   - Si aparecen monedas extranjeras (USD, EUR, etc.)
   - Si el NIT/RUT es de otro país
   - Si menciona "no residente" o "no domiciliado en Colombia"
   - Si la factura viene de empresas extranjeras

**DETECCIÓN DE CONSORCIOS:**
9. Verifica si se trata de un CONSORCIO analizando:
   - Si en la factura aparece la palabra "CONSORCIO" en el nombre del proveedor
   - Si menciona "consorciados" o "miembros del consorcio"
   - Si aparecen porcentajes de participación entre empresas
   - Si hay múltiples NITs/empresas trabajando en conjunto

DOCUMENTOS A CLASIFICAR:
{json.dumps(textos_archivos, indent=2, ensure_ascii=False)}

RESPONDE ÚNICAMENTE EN FORMATO JSON VÁLIDO SIN TEXTO ADICIONAL:
{{
    "clasificacion": {{
        "nombre_archivo_1": "CATEGORIA",
        "nombre_archivo_2": "CATEGORIA"
    }},
    "es_facturacion_extranjera": true/false,
    "indicadores_extranjera": ["razón 1", "razón 2"],
    "es_consorcio": true/false,
    "indicadores_consorcio": ["razón 1", "razón 2"]
}}
"""

def PROMPT_ANALISIS_FACTURA(factura_texto: str, rut_texto: str, anexos_texto: str, 
                            cotizaciones_texto: str, anexo_contrato: str, conceptos_dict: dict) -> str:
    """
    Genera el prompt para analizar factura y extraer información de retención.
    
    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        conceptos_dict: Diccionario de conceptos con tarifas y bases mínimas
        
    Returns:
        str: Prompt formateado para enviar a Gemini
    """
    
    # Importar constantes del Artículo 383
    from config import obtener_constantes_articulo_383
    constantes_art383 = obtener_constantes_articulo_383()
    
    return f"""
    Eres un experto contador colombiano especializado en retención en la fuente que trabaja para la FIDUCIARIA FIDUCOLDEX (las FIDUCIARIA Tiene varios NITS administrados), tu trabajo es aplicar las retenciones a las empresas (terceros) que emiten las FACTURAS. 
    
    CONCEPTOS DE RETEFUENTE QUE DEBES IDENTIFICAR (con base mínima y tarifa exacta):
    {json.dumps(conceptos_dict, indent=2, ensure_ascii=False)}
    
    **ARTÍCULO 383 - PERSONAS NATURALES (TARIFAS PROGRESIVAS):**
    UVT 2025: ${constantes_art383['uvt_2025']:,}
    SMMLV 2025: ${constantes_art383['smmlv_2025']:,}
    
    Conceptos que aplican para Art. 383:
    {json.dumps(constantes_art383['conceptos_aplicables'], indent=2, ensure_ascii=False)}
    
    Tarifas progresivas Art. 383:
    {json.dumps(constantes_art383['tarifas'], indent=2, ensure_ascii=False)}
    
    Límites de deducciones Art. 383:
    {json.dumps(constantes_art383['limites_deducciones'], indent=2, ensure_ascii=False)}
    
    DOCUMENTOS DISPONIBLES:
    
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
    
    INSTRUCCIONES CRÍTICAS:
    1.  **ESTRATEGIA DE ANÁLISIS**:
       - Primero revisa la FACTURA para identificar conceptos
       - Si la FACTURA solo muestra valores generales SIN DETALLE, revisa los ANEXOS y COTIZACIONES
       - Los ANEXOS frecuentemente contienen el desglose detallado de cada concepto
       - Las COTIZACIONES pueden mostrar la descripción específica de servicios/productos
       - El objeto del contrato te puede ayudar a identificar cuales son los servicios que   se están prestando o cobrando en la factura.
       -Para identificar la naturaleza del tercero, siempre revisa en el siguiente orden primero el RUT, despues la factura, despues los ANEXOS
    
    2.  **IDENTIFICACIÓN DE CONCEPTOS**:
       - Usa el NOMBRE EXACTO del concepto como aparece en el diccionario
       - Si encuentras servicios específicos en anexos, mapea al concepto más cercano del diccionario
       - Si hay valores distribuidos por concepto en anexos, especifica la base_gravable para cada uno
       - Si solo hay un valor total, usa ese valor para el concepto identificado
    
    3.  **VALIDACIONES**:
       - Verifica que el valor supere la base mínima del concepto
       - NO inventes o modifiques nombres de conceptos
       - Si hay dudas entre conceptos similares, elige el más específico
    
    4.  **NATURALEZA DEL TERCERO - CRÍTICO PARA RETENCIÓN**:
       - Busca esta información principalmente en el RUT (si esta disponible VERIFICALO EN LA SECCION RESPONSABILIDADES, CALIDADES Y ATRIBUTOS DEL RUT), si NO se adjunto el RUT verifica la naturaleza en la FACTURA o en los ANEXOS. 
       - ¿Es persona natural o jurídica?
       - ¿Es declarante de renta?
       - ¿Qué régimen tributario? (Simple/Ordinario/Especial) 
       - ¿Es autorretenedor?
       - **¿Es responsable de IVA?** (CRÍTICO: Si NO es responsable de IVA, NO se le aplica retención en la fuente)
       
       **IMPORTANTE SOBRE AUTORRETENDOR**
       -Si en el RUT NO MENCIONA que el contribuyente ES AUTORRETENDOR, ese contribuyente NO es AUTORRETENDEDOR.
       
       **IMPORTANTE SOBRE RÉGIMEN TRIBUTARIO:**
       - **Régimen Simple**: Personas naturales con ingresos bajos, NO aplica retención en la fuente
       - **Régimen Ordinario**:  SÍ aplica retención en la fuente
       - **Régimen Especial**: Entidades sin ánimo de lucro, fundaciones, universidades, etc. SÍ aplica retención (igual que ordinario)
       
       **IDENTIFICADORES EN EL RUT - USA EL VALOR EXACTO:**
       - Busca "RÉGIMEN SIMPLE" o "SIMPLE" → regimen_tributario: "SIMPLE"
       - Busca "RÉGIMEN ORDINARIO" o "ORDINARIO" → regimen_tributario: "ORDINARIO"
       - Busca "RÉGIMEN ESPECIAL" o "ESPECIAL" o "SIN ÁNIMO DE LUCRO" →   regimen_tributario: "ESPECIAL"
       - BUSCA "Persona natural o sucesión ilíquida" → "es_persona_natural": true
       - BUSCA "Persona natural" → "es_persona_natural": true
       - BUSCA "49 - No responsable de IVA" → "es_responsable_iva": false
       
       **IMPORTANTE:** NO generalices. Si encuentras "RÉGIMEN ESPECIAL" usa "ESPECIAL", NO "ORDINARIO".
       Aunque el tratamiento tributario sea igual, debes mantener la diferenciación específica.
       
       **IMPORTANTE SOBRE RESPONSABLE DE IVA:**
       - Si en el RUT aparece "NO RESPONSABLE DE IVA" o "NO RESPONSABLE DEL RÉGIMEN COMÚN DEL IVA", marca es_responsable_iva: false
       - Si aparece "RESPONSABLE DE IVA" o "RESPONSABLE DEL RÉGIMEN COMÚN DEL IVA", marca es_responsable_iva: true
       - Si no encuentras información clara sobre IVA, marca como null
       - En personas naturales, busca si están en régimen simple (no responsables de retencion en la fuente) o común (responsables de retencion en la fuente)
    
    5.  **ARTÍCULO 383 - VALIDACIÓN PARA PERSONAS NATURALES**:
        SOLO aplica si se cumplen TODAS estas condiciones:
        
        **CONDICIONES OBLIGATORIAS:**
        - El tercero es PERSONA NATURAL
        - El concepto corresponde a: honorarios, prestación de servicios, diseños, comisiones, viáticos
        - Conceptos aplicables exactos: {constantes_art383['conceptos_aplicables']}
        
        **DETECCIÓN DE PRIMER PAGO** (BUSCAR EN FACTURA Y ANEXOS):
        Identifica si es el primer pago del contrato buscando indicadores como:
        - "primer pago", "pago inicial", "anticipo", "pago adelantado"
        - "primera cuota", "entrega inicial", "adelanto"
        - Numeración de facturas: 001, 01, #1
        - "inicio de contrato", "pago de arranque"
        - Sinónimos o variaciones de estos términos
        
        **SOPORTES OBLIGATORIOS A BUSCAR EN LOS ANEXOS:**
        a) Planilla de aportes a salud y pensión (máximo 2 meses antigüedad):
           - **PRIMER PAGO**: NO es obligatoria, pero verificar si está presente
           - **PAGOS POSTERIORES**: SÍ es obligatoria
           - Debe ser sobre el 40% del valor del ingreso
           - Si el ingreso NO supera $1,423,500 (SMMLV), esta condición no cuenta
           
        b) Cuenta de cobro (honorarios, comisiones, prestación de servicios) - SIEMPRE OBLIGATORIA
        
        **LÓGICA DE VALIDACIÓN DE PLANILLA:**
        - Si es PRIMER PAGO y tiene planilla: perfecto, continuar
        - Si es PRIMER PAGO y NO tiene planilla: agregar observación pero continuar con Art. 383
        - Si NO es primer pago y NO tiene planilla: NO aplicar Art. 383, usar tarifa convencional
        
        **DEDUCCIONES PERMITIDAS A IDENTIFICAR EN ANEXOS:**
        Si hay soportes válidos, busca estas deducciones:
        
        - **Intereses por vivienda**: Hasta 100 UVT/mes (${constantes_art383['uvt_2025'] * 100:,}/mes)
           Soporte: Certificación entidad financiera con nombre del tercero
           
        - **Dependientes económicos**: Hasta 10% del ingreso o 32 UVT/mes (${constantes_art383['uvt_2025'] * 32:,}/mes)
           Soporte: Declaración juramentada del beneficiario
           
        - **Medicina prepagada**: Hasta 16 UVT/mes (${constantes_art383['uvt_2025'] * 16:,}/mes)
           Soporte: Certificación EPS o entidad medicina prepagada
           
        - **Rentas exentas (AFC, pensiones voluntarias)**: Hasta 25% del ingreso mensual sin exceder 3,800 UVT/año
           Soporte: Planilla de aportes (máximo 2 meses antigüedad)
           Si ingreso NO supera $1,423,500, esta deducción no cuenta
        
        **CÁLCULO BASE GRAVABLE ART. 383:**
        Base gravable = Ingreso bruto - Aportes seguridad social (40%) - Deducciones soportadas
        
        IMPORTANTE: Deducciones NO PUEDEN superar 40% del ingreso bruto
        
        **TARIFA A APLICAR SEGÚN BASE GRAVABLE EN UVT:**
        - 0 a 95 UVT: 0%
        - 95 a 150 UVT: 19%
        - 150 a 360 UVT: 28%
        - 360 a 640 UVT: 33%
        - 640 a 945 UVT: 35%
        - 945 a 2300 UVT: 37%
        - 2300 UVT en adelante: 39%
        
    6.  **VALORES MONETARIOS**:
       - Extrae valores totales de la factura
       - Si hay desglose en anexos, suma los valores por concepto
       - Identifica IVA si está presente
    
    EJEMPLOS DE USO DE ANEXOS:
    - Factura: "Servicios profesionales $5,000,000"
    - Anexo: "Detalle: Asesoría legal $3,000,000 + Consultoria técnica $2,000,000"
    - Resultado: Identificar "Honorarios y comisiones por servicios" con base en el detalle del anexo
    
    IMPORTANTE:
    - Si NO puedes identificar un concepto específico, indica "CONCEPTO_NO_IDENTIFICADO"
    - Si la facturación es fuera de Colombia, marca es_facturacion_exterior: true
    - Si no puedes determinar la naturaleza del tercero, marca como null
    - Para regimen_tributario usa EXACTAMENTE: "SIMPLE", "ORDINARIO" o "ESPECIAL" según lo que encuentres en el RUT
    - NO generalices régimen especial como ordinario - mantén la diferenciación específica
    - Para Art. 383: Si faltan soportes obligatorios, aplicar tarifa convencional
    - EL DOCUMENTO " SOPORTE EN ADQUISICIONES EFECTUADAS A NO OBLIGADOS A FACTURAR " ES EQUIVALENTE A UNA " FACTURA ".
    
    RESPONDE ÚNICAMENTE EN FORMATO JSON VÁLIDO SIN TEXTO ADICIONAL:
    {{
        "conceptos_identificados": [
            {{
                "concepto": "nombre exacto del concepto o CONCEPTO_NO_IDENTIFICADO",
                "tarifa_retencion": 0.0,
                "base_gravable": 0.0
            }}
        ],
        "naturaleza_tercero": {{
            "es_persona_natural": false,
            "es_declarante": true,
            "regimen_tributario": "ESPECIAL",  // USA EXACTAMENTE lo que encuentres: "SIMPLE", "ORDINARIO" o "ESPECIAL"
            "es_autorretenedor": false,
            "es_responsable_iva": true
        }},
        "articulo_383": {{
            "aplica": false,
            "condiciones_cumplidas": {{
                "es_persona_natural": false,
                "concepto_aplicable": false,
                "es_primer_pago": false,
                "planilla_seguridad_social": false,
                "cuenta_cobro": false
            }},
            "deducciones_identificadas": {{
                "intereses_vivienda": {{
                    "valor": 0.0,
                    "tiene_soporte": false,
                    "limite_aplicable": 0.0
                }},
                "dependientes_economicos": {{
                    "valor": 0.0,
                    "tiene_soporte": false,
                    "limite_aplicable": 0.0
                }},
                "medicina_prepagada": {{
                    "valor": 0.0,
                    "tiene_soporte": false,
                    "limite_aplicable": 0.0
                }},
                "rentas_exentas": {{
                    "valor": 0.0,
                    "tiene_soporte": false,
                    "limite_aplicable": 0.0
                }}
            }},
            "calculo": {{
                "ingreso_bruto": 0.0,
                "aportes_seguridad_social": 0.0,
                "total_deducciones": 0.0,
                "deducciones_limitadas": 0.0,
                "base_gravable_final": 0.0,
                "base_gravable_uvt": 0.0,
                "tarifa_aplicada": 0.0,
                "valor_retencion_art383": 0.0
            }}
        }},
        "es_facturacion_exterior": false,
        "valor_total": 0.0,
        "iva": 0.0,
        "observaciones": ["observación 1", "observación 2"]
    }}
    """

def PROMPT_ANALISIS_CONSORCIO(factura_texto: str, rut_texto: str, anexos_texto: str, 
                              cotizaciones_texto: str, anexo_contrato: str, conceptos_dict: dict) -> str:
    """
    Genera el prompt optimizado para analizar consorcios.
    
    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        conceptos_dict: Diccionario de conceptos con tarifas y bases mínimas
        
    Returns:
        str: Prompt formateado para enviar a Gemini
    """
    
    # Importar constantes del Artículo 383
    from config import obtener_constantes_articulo_383
    constantes_art383 = obtener_constantes_articulo_383()
    
    # Limitar conceptos a los más relevantes para reducir tokens
    conceptos_simplificados = {k: v for i, (k, v) in enumerate(conceptos_dict.items()) if i < 20}
    
    return f"""
      Eres un experto contador colombiano especializado en retención en la fuente que trabaja para la FIDUCIARIA FIDUCOLDEX (las FIDUCIARIA Tiene varios NITS administrados), tu trabajo es aplicar las retenciones a las empresas (terceros) que emiten las FACTURAS.
    ANALIZA ESTE CONSORCIO Y CALCULA RETENCIONES POR CONSORCIADO.
    
    CONCEPTOS RETEFUENTE (usa NOMBRE EXACTO):
    {json.dumps(conceptos_simplificados, indent=1, ensure_ascii=False)}
    
    **ARTÍCULO 383 - PERSONAS NATURALES (TARIFAS PROGRESIVAS):**
    UVT 2025: ${constantes_art383['uvt_2025']:,}
    SMMLV 2025: ${constantes_art383['smmlv_2025']:,}
    
    Conceptos que aplican para Art. 383:
    {json.dumps(constantes_art383['conceptos_aplicables'], indent=1, ensure_ascii=False)}
    
    Tarifas progresivas Art. 383:
    {json.dumps(constantes_art383['tarifas'], indent=1, ensure_ascii=False)}
    
    Límites de deducciones Art. 383:
    {json.dumps(constantes_art383['limites_deducciones'], indent=1, ensure_ascii=False)}
    
    FACTURA:
    {factura_texto}
    
    RUT:
    {rut_texto if rut_texto else "NO DISPONIBLE"}
    
    ANEXOS:
    {anexos_texto if anexos_texto else "NO DISPONIBLES"}
    
    INSTRUCCIONES:
    1. EXTRAE: nombre, NIT y % de cada consorciado (busca formato NIT_%, ej: 900123456_15.5%). en la factura principalmente si ahi no esta la informacion revisa los anexos.
    2. IDENTIFICA: concepto de retefuente del servicio (usa nombre EXACTO del diccionario)
    2.1 VALIDA : el valor total del concepto facturado por el CONSORCIO, debe superar la base minima.(La base minima NO SE ANALIZA POR CONSORCIADO)
    3. CALCULA: valor_proporcional = valor_total * (porcentaje/100)
    4. VALIDA por consorciado: responsable IVA, autorretenedor, régimen
    5. **ARTÍCULO 383 POR CONSORCIADO**: Para cada consorciado que sea PERSONA NATURAL, valida Art. 383
    6. APLICA: retención = valor_proporcional * tarifa (Art. 383 o convencional según validaciones)
    7.**RETENCIÓN EN LA FUENTE:**
    - Identifica información sobre retención en la fuente en los ANEXOS. (En ocasiones los anexos solo dicen APLICA o No aplica)
   
     **ESTRATEGIA DE ANÁLISIS**
   
      - Primero revisa la FACTURA para identificar conceptos
       - Si la FACTURA solo muestra valores generales SIN DETALLE, revisa los ANEXOS y COTIZACIONES
       - Los ANEXOS frecuentemente contienen el desglose detallado de cada concepto
       - Las COTIZACIONES pueden mostrar la descripción específica de servicios/productos
       - El objeto del contrato te puede ayudar a identificar cuales son los servicios que  se están prestando o cobrando en la factura
       
   **NATURALEZA DEL TERCERO - CRÍTICO PARA RETENCIÓN (POR CADA CONSORCIADO):**
       - Busca esta información principalmente en el RUT (si esta disponible VERIFICALO EN LA SECCION RESPONSABILIDADES, CALIDADES Y ATRIBUTOS DEL RUT), si NO se adjunto el RUT verifica la naturaleza en la FACTURA o en los ANEXOS. 
       - ¿Es persona natural o jurídica?
       - ¿Es declarante de renta?
       - ¿Qué régimen tributario? (Simple/Ordinario/Especial) 
       - ¿Es autorretenedor?
       - **¿Es responsable de IVA?** (CRÍTICO: Si NO es responsable de IVA, NO se le aplica retención en la fuente)
       
    **ARTÍCULO 383 - VALIDACIÓN POR CONSORCIADO (SOLO PERSONAS NATURALES):**
        Para cada consorciado que sea PERSONA NATURAL, valida si aplica Art. 383:
        
        **CONDICIONES OBLIGATORIAS:**
        - El consorciado es PERSONA NATURAL
        - El concepto corresponde a: honorarios, prestación de servicios, diseños, comisiones, viáticos
        - Conceptos aplicables exactos: {constantes_art383['conceptos_aplicables']}
        
        **DETECCIÓN DE PRIMER PAGO** (BUSCAR EN FACTURA Y ANEXOS):
        Identifica si es el primer pago del contrato buscando indicadores como:
        - "primer pago", "pago inicial", "anticipo", "pago adelantado"
        - "primera cuota", "entrega inicial", "adelanto"
        - Numeración de facturas: 001, 01, #1
        - "inicio de contrato", "pago de arranque"
        - Sinónimos o variaciones de estos términos
        
        **SOPORTES OBLIGATORIOS A BUSCAR EN LOS ANEXOS:**
        a) Planilla de aportes a salud y pensión (máximo 2 meses antigüedad):
           - **PRIMER PAGO**: NO es obligatoria, pero verificar si está presente
           - **PAGOS POSTERIORES**: SÍ es obligatoria
           - Debe ser sobre el 40% del valor del ingreso
           - Si el ingreso NO supera $1,423,500 (SMMLV), esta condición no cuenta
           
        b) Cuenta de cobro (honorarios, comisiones, prestación de servicios) - SIEMPRE OBLIGATORIA
        
        **LÓGICA DE VALIDACIÓN DE PLANILLA POR CONSORCIADO:**
        - Si es PRIMER PAGO y tiene planilla: perfecto, continuar con Art. 383
        - Si es PRIMER PAGO y NO tiene planilla: agregar observación pero continuar con Art. 383
        - Si NO es primer pago y NO tiene planilla: NO aplicar Art. 383, usar tarifa convencional
        
        **DEDUCCIONES PERMITIDAS A IDENTIFICAR EN ANEXOS (POR CONSORCIADO):**
        Si hay soportes válidos, busca estas deducciones:
        
        - **Intereses por vivienda**: Hasta 100 UVT/mes (${constantes_art383['uvt_2025'] * 100:,}/mes)
           Soporte: Certificación entidad financiera con nombre del consorciado
           
        - **Dependientes económicos**: Hasta 10% del ingreso o 32 UVT/mes (${constantes_art383['uvt_2025'] * 32:,}/mes)
           Soporte: Declaración juramentada del beneficiario
           
        - **Medicina prepagada**: Hasta 16 UVT/mes (${constantes_art383['uvt_2025'] * 16:,}/mes)
           Soporte: Certificación EPS o entidad medicina prepagada
           
        - **Rentas exentas (AFC, pensiones voluntarias)**: Hasta 25% del ingreso mensual sin exceder 3,800 UVT/año
           Soporte: Planilla de aportes (máximo 2 meses antigüedad)
           Si ingreso NO supera $1,423,500, esta deducción no cuenta
        
        **CÁLCULO BASE GRAVABLE ART. 383 POR CONSORCIADO:**
        Base gravable = Valor proporcional - Aportes seguridad social (40%) - Deducciones soportadas
        
        IMPORTANTE: Deducciones NO PUEDEN superar 40% del valor proporcional
        
        **TARIFA A APLICAR SEGÚN BASE GRAVABLE EN UVT:**
        - 0 a 95 UVT: 0%
        - 95 a 150 UVT: 19%
        - 150 a 360 UVT: 28%
        - 360 a 640 UVT: 33%
        - 640 a 945 UVT: 35%
        - 945 a 2300 UVT: 37%
        - 2300 UVT en adelante: 39%
    
    REGLAS:
    - NO retención si: NO responsable IVA, autorretenedor, régimen SIMPLE, o valor concepto del consorcio (en general) < base mínima
    - Para personas naturales: Aplicar Art. 383 si cumple condiciones, sino tarifa convencional
    - Para personas jurídicas: Siempre tarifa convencional
    - Normaliza porcentajes a 100% si necesario
    - ANALIZA E IDENTIFICA TODOS LOS CONSORCIADOS QUE VEAS. NO PONGAS "// ... (rest of the consorciados)" PARA SIMPLIFICAR TU RESPUESTA
    - Devuélveme el JSON completo y válido (sin truncar), aunque sea largo
    - ES CRÍTICO QUE SOLO RESPONDAS CON EL JSON, NO HAGAS COMENTARIOS EXTRAS
    
     IMPORTANTE:
    - Si NO puedes identificar un concepto específico, indica "CONCEPTO_NO_IDENTIFICADO"
    - Si la facturación es fuera de Colombia, marca es_facturacion_exterior: true
    - Si no puedes determinar la naturaleza del tercero, marca como null
    - Para regimen_tributario usa EXACTAMENTE: "SIMPLE", "ORDINARIO" o "ESPECIAL" según lo que encuentres en el RUT
    - NO generalices régimen especial como ordinario - mantén la diferenciación específica
    
    RESPONDE SOLO JSON:
    {{
        "es_consorcio": true,
        "consorcio_info": {{
            "nombre_consorcio": "string",
            "nit_consorcio": "string",
            "total_consorciados": 0
        }},
        "consorciados": [{{
            "nombre": "string",
            "nit": "string",
            "porcentaje_participacion": 0.0,
            "valor_proporcional": 0.0,
            "naturaleza_tercero": {{
                "es_persona_natural": false,
                "es_declarante": true,
                "regimen_tributario": "ORDINARIO",
                "es_autorretenedor": false,
                "es_responsable_iva": true
            }},
            "articulo_383": {{
                "aplica": false,
                "condiciones_cumplidas": {{
                    "es_persona_natural": false,
                    "concepto_aplicable": false,
                    "es_primer_pago": false,
                    "planilla_seguridad_social": false,
                    "cuenta_cobro": false
                }},
                "deducciones_identificadas": {{
                    "intereses_vivienda": {{
                        "valor": 0.0,
                        "tiene_soporte": false,
                        "limite_aplicable": 0.0
                    }},
                    "dependientes_economicos": {{
                        "valor": 0.0,
                        "tiene_soporte": false,
                        "limite_aplicable": 0.0
                    }},
                    "medicina_prepagada": {{
                        "valor": 0.0,
                        "tiene_soporte": false,
                        "limite_aplicable": 0.0
                    }},
                    "rentas_exentas": {{
                        "valor": 0.0,
                        "tiene_soporte": false,
                        "limite_aplicable": 0.0
                    }}
                }},
                "calculo": {{
                    "ingreso_bruto": 0.0,
                    "aportes_seguridad_social": 0.0,
                    "total_deducciones": 0.0,
                    "deducciones_limitadas": 0.0,
                    "base_gravable_final": 0.0,
                    "base_gravable_uvt": 0.0,
                    "tarifa_aplicada": 0.0,
                    "valor_retencion_art383": 0.0
                }}
            }},
            "aplica_retencion": true,
            "valor_retencion": 0.0,
            "tarifa_aplicada": 0.0,
            "tipo_calculo": "CONVENCIONAL",
            "razon_no_retencion": null
        }}],
        "conceptos_identificados": [{{
            "concepto": "string",
            "tarifa_retencion": 0.0,
            "base_gravable": 0.0,
            "base_minima": 0.0
        }}],
        "resumen_retencion": {{
            "valor_total_factura": 0.0,
            "iva_total": 0.0,
            "total_retenciones": 0.0,
            "consorciados_con_retencion": 0,
            "consorciados_sin_retencion": 0,
            "consorciados_art383": 0,
            "consorciados_convencional": 0,
            "suma_porcentajes_original": 0.0,
            "porcentajes_normalizados": false
        }},
        "es_facturacion_exterior": false,
        "observaciones": []
    }}
    """
def PROMPT_ANALISIS_FACTURA_EXTRANJERA(factura_texto: str, rut_texto: str, anexos_texto: str, 
                                       cotizaciones_texto: str, anexo_contrato: str, 
                                       conceptos_extranjeros_dict: dict, paises_convenio: list, 
                                       preguntas_fuente: list) -> str:
    """
    Genera el prompt para analizar factura extranjera y determinar retenciones.
    
    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        conceptos_extranjeros_dict: Diccionario de conceptos extranjeros con tarifas
        paises_convenio: Lista de países con convenio de doble tributación
        preguntas_fuente: Lista de preguntas para determinar fuente nacional
        
    Returns:
        str: Prompt formateado para enviar a Gemini
    """
    
    return f"""
    Eres un experto contador colombiano especializado en retención en la fuente para PAGOS AL EXTERIOR.
    
    CONCEPTOS DE RETEFUENTE PARA PAGOS AL EXTERIOR (con tarifas normal y convenio):
    {json.dumps(conceptos_extranjeros_dict, indent=2, ensure_ascii=False)}
    
    PAÍSES CON CONVENIO DE DOBLE TRIBUTACIÓN:
    {json.dumps(paises_convenio, indent=2, ensure_ascii=False)}
    
    DOCUMENTOS DISPONIBLES:
    
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
    
    INSTRUCCIONES CRÍTICAS PARA FACTURACIÓN EXTRANJERA:
    
    1. **VALIDACIÓN DE FUENTE NACIONAL** (RESPONDE SÍ/NO A CADA PREGUNTA):
    {chr(10).join([f'   - {pregunta}' for pregunta in preguntas_fuente])}
    
       **IMPORTANTE**: Si CUALQUIERA de estas respuestas es SÍ, se considera FUENTE NACIONAL
       y debe aplicarse la tarifa correspondiente. Si TODAS son NO, es fuente extranjera.
    
    2. **IDENTIFICACIÓN DEL PAÍS DE ORIGEN**:
       - Identifica el país donde está domiciliado el proveedor
       - Verifica si está en la lista de países con convenio
       - Incluye Comunidad Andina: Perú, Ecuador, Bolivia
    
    3. **IDENTIFICACIÓN DE CONCEPTOS**:
       - Usa el NOMBRE EXACTO del concepto como aparece en el diccionario de conceptos extranjeros
       - Si encuentras servicios específicos, mapea al concepto más cercano
       - NO inventes o modifiques nombres de conceptos
       - Si no encuentras coincidencia exacta: "CONCEPTO_NO_IDENTIFICADO"
    
    4. **APLICACIÓN DE TARIFAS**:
       - Si el país TIENE convenio: usa "tarifa_convenio"
       - Si el país NO TIENE convenio: usa "tarifa_normal"
       - Las bases mínimas para conceptos extranjeros son 0 (sin base mínima)
    
    5. **VALORES MONETARIOS**:
       - Extrae valores en la moneda original
       - Si hay conversión a pesos, especifica la tasa de cambio
       - Identifica si hay IVA aplicado
    
    EJEMPLOS DE ANÁLISIS:
    
    Ejemplo 1 - Fuente Nacional:
    - Servicio: "Consultoría técnica para proyecto en Bogotá"
    - Pregunta "uso en Colombia": SÍ → ES FUENTE NACIONAL
    - Resultado: Aplicar retención según normativa colombiana
    
    Ejemplo 2 - Fuente Extranjera con Convenio:
    - Servicio: "Licencia de software usado en España"
    - Todas las preguntas: NO → ES FUENTE EXTRANJERA
    - País: España (TIENE convenio)
    - Resultado: Aplicar tarifa_convenio del concepto correspondiente
    
    Ejemplo 3 - Fuente Extranjera sin Convenio:
    - Servicio: "Honorarios por servicios en Estados Unidos"
    - Todas las preguntas: NO → ES FUENTE EXTRANJERA
    - País: Estados Unidos (NO TIENE convenio)
    - Resultado: Aplicar tarifa_normal del concepto correspondiente
    
    IMPORTANTE:
    - Si NO puedes identificar un concepto específico, indica "CONCEPTO_NO_IDENTIFICADO"
    - Si no puedes determinar el país, marca como null
    - Especifica claramente si aplica retención y por qué
    - Para conceptos extranjeros NO hay base mínima (base_pesos = 0)
    
    RESPONDE ÚNICAMENTE EN FORMATO JSON VÁLIDO SIN TEXTO ADICIONAL:
    {{
        "es_facturacion_extranjera": true,
        "pais_proveedor": "string o null",
        "tiene_convenio_doble_tributacion": false,
        "validacion_fuente_nacional": {{
            "pregunta_1_uso_beneficio_colombia": false,
            "pregunta_2_actividad_en_colombia": false,
            "pregunta_3_asistencia_tecnica_colombia": false,
            "pregunta_4_bien_ubicado_colombia": false,
            "es_fuente_nacional": false,
            "justificacion": "string"
        }},
        "conceptos_identificados": [
            {{
                "concepto": "nombre exacto del concepto o CONCEPTO_NO_IDENTIFICADO",
                "tarifa_normal": 0.0,
                "tarifa_convenio": 0.0,
                "tarifa_aplicada": 0.0,
                "base_gravable": 0.0
            }}
        ],
        "calculo_retencion": {{
            "aplica_retencion": false,
            "valor_retencion": 0.0,
            "tarifa_aplicada_porcentaje": 0.0,
            "razon_aplicacion": "string"
        }},
        "valor_total": 0.0,
        "moneda_original": "string",
        "tasa_cambio": null,
        "iva": 0.0,
        "observaciones": ["observación 1", "observación 2"]
    }}
    """

def PROMPT_ANALISIS_CONSORCIO_EXTRANJERO(factura_texto: str, rut_texto: str, anexos_texto: str, 
                                         cotizaciones_texto: str, anexo_contrato: str, 
                                         conceptos_extranjeros_dict: dict, paises_convenio: list, 
                                         preguntas_fuente: list) -> str:
    """
    Genera el prompt optimizado para analizar consorcios con facturación extranjera.
    
    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        conceptos_extranjeros_dict: Diccionario de conceptos extranjeros con tarifas
        paises_convenio: Lista de países con convenio de doble tributación
        preguntas_fuente: Lista de preguntas para determinar fuente nacional
        
    Returns:
        str: Prompt formateado para enviar a Gemini
    """
    
    # Limitar conceptos para reducir tokens
    conceptos_limitados = dict(list(conceptos_extranjeros_dict.items())[:5])
    
    return f"""
    ANALIZA ESTE CONSORCIO CON FACTURACIÓN EXTRANJERA Y CALCULA RETENCIONES POR CONSORCIADO.
    
    CONCEPTOS RETEFUENTE EXTRANJEROS (usa NOMBRE EXACTO):
    {json.dumps(conceptos_limitados, indent=1, ensure_ascii=False)}
    
    PAÍSES CON CONVENIO: {paises_convenio}
    
    FACTURA:
    {factura_texto}
    
    RUT:
    {rut_texto if rut_texto else "NO DISPONIBLE"}
    
    ANEXOS:
    {anexos_texto if anexos_texto else "NO DISPONIBLES"}
    
    INSTRUCCIONES PARA CONSORCIO EXTRANJERO:
    
    1. **VALIDACIÓN DE FUENTE NACIONAL** (SÍ/NO):
    {chr(10).join([f'   - {pregunta}' for pregunta in preguntas_fuente])}
    
    2. **EXTRACCIÓN**: nombre, NIT y % de cada consorciado
    3. **IDENTIFICACIÓN**: concepto extranjero + país proveedor
    4. **APLICACIÓN DE TARIFA**: convenio o normal según país
    5. **CÁLCULO**: valor_proporcional = valor_total * (porcentaje/100)
    6. **RETENCIÓN**: valor_retencion = valor_proporcional * tarifa_aplicada
    
    REGLAS ESPECIALES EXTRANJERAS:
    - Si es fuente nacional: aplicar normativa colombiana estándar
    - Si es fuente extranjera: aplicar tarifas de pagos al exterior
    - No hay base mínima para conceptos extranjeros
    - Verificar convenio por país del proveedor
    
    RESPONDE SOLO JSON COMPLETO:
    {{
        "es_consorcio": true,
        "es_facturacion_extranjera": true,
        "pais_proveedor": "string",
        "tiene_convenio_doble_tributacion": false,
        "validacion_fuente_nacional": {{
            "pregunta_1_uso_beneficio_colombia": false,
            "pregunta_2_actividad_en_colombia": false,
            "pregunta_3_asistencia_tecnica_colombia": false,
            "pregunta_4_bien_ubicado_colombia": false,
            "es_fuente_nacional": false,
            "justificacion": "string"
        }},
        "consorcio_info": {{
            "nombre_consorcio": "string",
            "nit_consorcio": "string",
            "total_consorciados": 0
        }},
        "consorciados": [{{
            "nombre": "string",
            "nit": "string",
            "porcentaje_participacion": 0.0,
            "valor_proporcional": 0.0,
            "aplica_retencion": true,
            "valor_retencion": 0.0,
            "tarifa_aplicada": 0.0,
            "razon_tarifa": "convenio/normal"
        }}],
        "conceptos_identificados": [{{
            "concepto": "string",
            "tarifa_normal": 0.0,
            "tarifa_convenio": 0.0,
            "tarifa_aplicada": 0.0,
            "base_gravable": 0.0
        }}],
        "resumen_retencion": {{
            "valor_total_factura": 0.0,
            "iva_total": 0.0,
            "total_retenciones": 0.0,
            "consorciados_con_retencion": 0,
            "consorciados_sin_retencion": 0
        }},
        "observaciones": []
    }}
    """
def PROMPT_ANALISIS_ESTAMPILLA(factura_texto: str, rut_texto: str, anexos_texto: str, 
                               cotizaciones_texto: str, anexo_contrato: str, configuracion_estampilla: dict) -> str:
    """
    Genera el prompt para analizar contratos de estampilla pro universidad nacional.
    
    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        configuracion_estampilla: Configuración de estampilla desde config.py
        
    Returns:
        str: Prompt formateado para enviar a Gemini
    """
    
    return f"""
Eres un experto contador colombiano especializado en ESTAMPILLA PRO UNIVERSIDAD NACIONAL.


CONFIGURACIÓN DE ESTAMPILLA UNIVERSIDAD NACIONAL:

NITs VÁLIDOS (solo estos NITs aplican estampilla):
{json.dumps(configuracion_estampilla['nits_validos'], indent=2, ensure_ascii=False)}

TERCEROS QUE ADMINISTRAN RECURSOS PÚBLICOS:
{json.dumps(configuracion_estampilla['terceros_recursos_publicos'], indent=2, ensure_ascii=False)}

OBJETOS DE CONTRATO QUE APLICAN:
{json.dumps(configuracion_estampilla['objetos_contrato'], indent=2, ensure_ascii=False)}

RANGOS UVT Y TARIFAS:
{json.dumps(configuracion_estampilla['rangos_uvt'], indent=2, ensure_ascii=False)}

UVT 2025: ${configuracion_estampilla['uvt_2025']:,}

DOCUMENTOS DISPONIBLES:

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

INSTRUCCIONES CRÍTICAS:

1. **IDENTIFICACIÓN DEL TERCERO**:
   - Busca el nombre exacto del tercero/beneficiario en la factura
   - Verifica si aparece en la lista de terceros que administran recursos públicos
   - Busca indicadores de consorcio (palabra "CONSORCIO" en el nombre)
   - Si es consorcio, identifica consorciados y porcentajes de participación

2. **OBJETO DEL CONTRATO**:
   - Analiza la descripción del servicio/producto en la factura
   - Revisa anexos y cotizaciones para detalles del objeto
   - Clasifica según los tipos: contrato_obra, interventoria, servicios_conexos_obra
   - Busca palabras clave específicas para cada tipo

3. **VALOR DEL CONTRATO**:
   - Identifica el valor total del contrato (puede ser diferente al valor de la factura)
   - Si solo aparece un porcentaje (ej: "20% del contrato por $50,000,000"), calcula el va   lor total
   - Convierte a UVT: valor_pesos / {configuracion_estampilla['uvt_2025']}
   - Si no puedes identificar el valor, marca como null

4. **VALIDACIONES**:
   - ¿El tercero administra recursos públicos?
   - ¿El objeto es obra, interventoría o servicios conexos?
   - ¿Se puede identificar el valor del contrato?
   - ¿Hay información suficiente para aplicar estampilla?

RESPONDE ÚNICAMENTE EN FORMATO JSON VÁLIDO SIN TEXTO ADICIONAL:
{{
    "tercero_identificado": {{
        "nombre": "NOMBRE EXACTO DEL TERCERO",
        "es_consorcio": true/false,
        "administra_recursos_publicos": true/false,
        "consorciados": [
            {{
                "nombre": "NOMBRE CONSORCIADO",
                "participacion_porcentaje": 0.0
            }}
        ]
    }},
    "objeto_contrato": {{
        "tipo": "contrato_obra" | "interventoria" | "servicios_conexos_obra" | "no_identificado",
        "aplica_estampilla": true/false,
        "palabras_clave_encontradas": ["palabra1", "palabra2"],
        "descripcion": "DESCRIPCIÓN DEL OBJETO DEL CONTRATO"
    }},
    "valor_contrato": {{
        "valor_total_pesos": 0.0,
        "valor_total_uvt": 0.0,
        "metodo_identificacion": "directo" | "porcentaje_calculado" | "no_identificado",
        "texto_referencia": "TEXTO DE DONDE SE EXTRAJO EL VALOR"
    }},
    "observaciones": [
        "Observación 1",
        "Observación 2"
    ]
}}
"""

def PROMPT_ANALISIS_OBRA_PUBLICA_ESTAMPILLA_INTEGRADO(factura_texto: str, rut_texto: str, anexos_texto: str, 
                                                       cotizaciones_texto: str, anexo_contrato: str, 
                                                       nit_administrativo: str) -> str:
    """
    🚀 PROMPT INTEGRADO OPTIMIZADO - OBRA PÚBLICA + ESTAMPILLA UNIVERSIDAD
    
    Analiza documentos para detectar y calcular AMBOS impuestos simultáneamente:
    - Estampilla Pro Universidad Nacional (tarifas por rangos UVT)
    - Contribución a Obra Pública del 5% (tarifa fija)
    
    Desde 2025, ambos impuestos aplican para los MISMOS NITs administrativos.
    
    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        nit_administrativo: NIT de la entidad administrativa
        
    Returns:
        str: Prompt optimizado para análisis integrado con Gemini
    """
    
    # Importar configuración desde config.py
    from config import (
        UVT_2025,
        NITS_ESTAMPILLA_UNIVERSIDAD,
        TERCEROS_RECURSOS_PUBLICOS,
        OBJETOS_CONTRATO_ESTAMPILLA,
        OBJETOS_CONTRATO_OBRA_PUBLICA,
        RANGOS_ESTAMPILLA_UNIVERSIDAD,
        obtener_configuracion_impuestos_integrada
    )
    
    config_integrada = obtener_configuracion_impuestos_integrada()
    
    return f"""
🏛️ ANÁLISIS INTEGRADO: ESTAMPILLA PRO UNIVERSIDAD NACIONAL + CONTRIBUCIÓN OBRA PÚBLICA 5%
==================================================================================

Eres un experto contador colombiano especializado en IMPUESTOS ESPECIALES INTEGRADOS que trabaja para la FIDUCIARIA FIDUCOLDEX (las FIDUCIARIA Tiene varios NITS administrados), tu trabajo es aplicar las retenciones a las empresas (terceros) que emiten las FACTURAS.
DESDE 2025, ambos impuestos aplican para los MISMOS NITs administrativos.

CONFIGURACIÓN ACTUAL:
🔹 NIT Administrativo: {nit_administrativo} 
🔹 UVT 2025: ${UVT_2025:,} pesos colombianos
🔹 NITs válidos (Solo estos Nits aplican AMBOS impuestos): {list(NITS_ESTAMPILLA_UNIVERSIDAD.keys())} 

TERCEROS QUE ADMINISTRAN RECURSOS PÚBLICOS (COMPARTIDO):
{chr(10).join([f"  ✓ {tercero}" for tercero in TERCEROS_RECURSOS_PUBLICOS.keys()])}

IMPUESTO 1 - ESTAMPILLA PRO UNIVERSIDAD NACIONAL:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 OBJETOS QUE APLICAN:
  a) CONTRATO DE OBRA: construcción, mantenimiento, instalación
  b) INTERVENTORÍA: interventoría, interventoria  
  c) SERVICIOS CONEXOS: estudios, asesorías técnicas, gerencia de obra/proyectos, diseño.
  
💰 TARIFAS POR RANGOS UVT:
{chr(10).join([f"  • {rango['desde_uvt']:,} a {rango['hasta_uvt']:,} UVT: {rango['tarifa']*100}%" if rango['hasta_uvt'] != float('inf') else f"  • Más de {rango['desde_uvt']:,} UVT: {rango['tarifa']*100}%" for rango in RANGOS_ESTAMPILLA_UNIVERSIDAD])}

IMPUESTO 2 - CONTRIBUCIÓN A OBRA PÚBLICA 5%:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 OBJETOS QUE APLICAN:
  SOLO CONTRATO DE OBRA: construcción, mantenimiento, instalación
  ⚠️ NO aplica para interventoría ni servicios conexos
  
💰 TARIFA FIJA: 5% del valor de la factura sin IVA

DOCUMENTOS DISPONIBLES:
━━━━━━━━━━━━━━━━━━━━━━━━

FACTURA PRINCIPAL:
{factura_texto}

RUT DEL TERCERO:
{rut_texto if rut_texto else "NO DISPONIBLE"}

ANEXOS ADICIONALES:
{anexos_texto if anexos_texto else "NO DISPONIBLES"}

COTIZACIONES:
{cotizaciones_texto if cotizaciones_texto else "NO DISPONIBLES"}

ANEXO CONCEPTO CONTRATO:
{anexo_contrato if anexo_contrato else "NO DISPONIBLES"}

INSTRUCCIONES CRÍTICAS:
━━━━━━━━━━━━━━━━━━━━━━━━

1.  DETECCIÓN AUTOMÁTICA DE IMPUESTOS:
   • Analiza si el objeto del contrato aplica para ESTAMPILLA (obra + interventoría + servicios conexos)
   • Analiza si el objeto del contrato aplica para OBRA PÚBLICA (SOLO obra)
   • Marca qué impuestos aplican según la lógica

2.  IDENTIFICACIÓN DEL TERCERO:
   • Busca el nombre EXACTO del tercero/beneficiario en la FACTURA
   • Verifica si administra recursos públicos (lista TERCEROS QUE ADMINISTRAN RECURSOS PÚBLICOS (COMPARTIDO):), sino administra recursos publicos NO se liquidan ninguno de los dos impuestos 
   • Si es consorcio, identifica consorciados y porcentajes
   • CRÍTICO: Nombres deben coincidir EXACTAMENTE con la lista

3.  ANÁLISIS DEL OBJETO DEL CONTRATO:

   Identifica si el tipo de contrato se clasifica en SOLO UNO de estos tipos:
   Busca palabras clave:
   • Obra: {OBJETOS_CONTRATO_ESTAMPILLA['contrato_obra']['palabras_clave']}
   • Interventoría: {OBJETOS_CONTRATO_ESTAMPILLA['interventoria']['palabras_clave']}
   • Servicios conexos: estudios, asesorías, gerencia, diseño, planos.
   si no clasifica en alguno de estos tipos, NO aplican los dos impuestos.

4.  IDENTIFICACIÓN DE VALORES CRÍTICOS:

   • Para ESTAMPILLA: 
     - Valor TOTAL del CONTRATO (determina tarifa UVT) 
     **De Algunas FACTURAS puedes identificar eL porcentaje del VALOR DEL CONTRATO, EJEMPLO factura : segundo pago del 20% del contrato por 50,000,000, con ese porcentaje OBLIGATORIAMENTE CALCULA el valor total del contrato total contrato calculado  = 50,000,000/0.2  =  $250,000,000)**
     
      ⚠️ Si NO se identifica valor del contrato → "Preliquidación sin finalizar"
      
     - Valor de la FACTURA sin IVA (para cálculo final)
      FÓRMULA: Estampilla = Valor factura (sin IVA) x Porcentaje tarifa aplicable
      

   • Para OBRA PÚBLICA: 
     - Valor de la FACTURA sin IVA (para cálculo directo)
     ⚠️ FÓRMULA: Contribución = Valor factura (sin IVA) x 5%
     ⚠️ Si NO se identifica valor de factura → "Preliquidación sin finalizar"
     
   • Para CONSORCIOS: 
     - Identificar porcentaje de participación de cada consorciado
     - Fórmula: Impuesto = Valor factura sin IVA x Tarifa x % participación

5. 🏢 MANEJO DE CONSORCIOS:
   • Si el tercero incluye "CONSORCIO" o "UNIÓN TEMPORAL"
   • Busca participación de cada consorciado
   • Normaliza porcentajes si no suman 100%

ESTRATEGIA DE ANÁLISIS:
━━━━━━━━━━━━━━━━━━━━━━
1. Revisar FACTURA para información básica
2. Si la factura es general, revisar ANEXOS para detalles
3. COTIZACIONES pueden tener descripción específica
4. ANEXO CONTRATO tiene el objeto exacto del contrato
5. RUT puede tener información del tercero

LÓGICA DE DETECCIÓN Y ESTADOS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Si es  OBRA → Aplican AMBOS impuestos (estampilla + obra pública)
• Si es INTERVENTORÍA → Aplica SOLO estampilla
• Si es SERVICIOS CONEXOS → Aplica SOLO estampilla
• Si NO se identifica objeto → Ningún impuesto aplica, estado: "Preliquidación sin finalizar"
• Si NO se identifica valor → Estado: "Preliquidación sin finalizar"

🗒 ESTADOS REQUERIDOS:
• "Preliquidado" → Cuando todos los requisitos se cumplen
• "No aplica el impuesto" → Cuando tercero o objeto no aplican
• "Preliquidación sin finalizar" → Cuando falta información crítica

RESPONDE ÚNICAMENTE EN FORMATO JSON SIN TEXTO ADICIONAL:
{{
    "deteccion_automatica": {{
        "aplica_estampilla_universidad": true/false,
        "aplica_contribucion_obra_publica": true/false,
        "procesamiento_paralelo": true/false,
        "razon_deteccion": "Explicación de por qué aplican o no"
    }},
    "tercero_identificado": {{
        "nombre": "NOMBRE EXACTO DEL TERCERO",
        "es_consorcio": true/false,
        "administra_recursos_publicos": true/false,
        "consorciados": [
            {{
                "nombre": "NOMBRE CONSORCIADO",
                "porcentaje_participacion": 0.0
            }}
        ]
    }},
    "objeto_contrato": {{
        "descripcion_identificada": "DESCRIPCIÓN DEL OBJETO",
        "clasificacion_estampilla": "contrato_obra|interventoria|servicios_conexos_obra|no_identificado",
        "clasificacion_obra_publica": "contrato_obra|no_aplica",
        "palabras_clave_estampilla": ["palabra1", "palabra2"],
        "palabras_clave_obra_publica": ["palabra1", "palabra2"]
    }},
    "valores_identificados": {{
        "estampilla_universidad": {{
            "valor_contrato_pesos": 0.0,  // Valor TOTAL del contrato (determina tarifa UVT)
            "valor_contrato_uvt": 0.0,    // valor_contrato_pesos / {UVT_2025}
            "valor_factura_sin_iva": 0.0, // Valor de la FACTURA sin IVA (para cálculo final)
            "metodo_identificacion": "directo|porcentaje_calculado|no_identificado",
            "texto_referencia": "TEXTO DONDE SE ENCONTRÓ"
        }},
        "contribucion_obra_publica": {{
            "valor_factura_sin_iva": 0.0, // Valor de la FACTURA sin IVA
            "metodo_identificacion": "directo|calculado|no_identificado",
            "texto_referencia": "TEXTO DONDE SE ENCONTRÓ"
        }}
    }},
    "observaciones": [
        "Observación 1",
        "Observación 2"
    ]
}}

🔥 CRÍTICO - CONDICIONES EXACTAS: 
• ESTAMPILLA: Si NO se identifica objeto del contrato → "Preliquidación sin finalizar"
• ESTAMPILLA: Si NO se identifica valor del contrato → "Preliquidación sin finalizar"
• OBRA PÚBLICA: Si NO se identifica objeto (solo obra) → "Preliquidación sin finalizar"
• OBRA PÚBLICA: Si NO se identifica valor factura → "Preliquidación sin finalizar"
• Solo marca como válido si el tercero aparece EXACTAMENTE en la lista
• Para obra pública, SOLO aplica si es contrato de obra (no interventoría)
• Para estampilla, aplica para obra + interventoría + servicios conexos
• Si hay dudas sobre valores, especifica en observaciones
• CONSORCIOS: Fórmula = Valor factura sin IVA x Tarifa x % participación
• Si encuentras UN PORCENTAJE del VALOR del contrato en la FACTURA, OBLIGATORIAMENTE CALCULA el valor total del contrato COMO EL SIGUIENTE EJEMPLO -> FACTURA MENCIONA : 20% del contrato por $50,000,000 -> CALCULA -> total contrato = 50,000,000/0.2  =  $250,000,000)
    """

# ===============================
# ✅ NUEVO PROMPT: ANÁLISIS DE IVA Y RETEIVA
# ===============================

def PROMPT_ANALISIS_IVA(factura_texto: str, rut_texto: str, anexos_texto: str, 
                        cotizaciones_texto: str, anexo_contrato: str) -> str:
    """
    Genera el prompt para análisis especializado de IVA y ReteIVA.
    
    Args:
        factura_texto: Texto extraído de la factura principal
        rut_texto: Texto del RUT (si está disponible)
        anexos_texto: Texto de anexos adicionales
        cotizaciones_texto: Texto de cotizaciones
        anexo_contrato: Texto del anexo de concepto de contrato
        
    Returns:
        str: Prompt formateado para enviar a Gemini
    """
    # Importar configuraciones de IVA
    from config import obtener_configuracion_iva
    # Obtener configuración de IVA
    config_iva = obtener_configuracion_iva()
    
    return f"""
Eres un experto contador colombiano especializado en IVA y ReteIVA que trabaja para FIDUCIARIA FIDUCOLDEX.
Tu tarea es analizar documentos para determinar:

1. 💰 IDENTIFICACIÓN Y EXTRACCIÓN DEL IVA
2. 📝 VALIDACIÓN DE RESPONSABILIDAD DE IVA EN EL RUT
3. 🌍 DETERMINACIÓN DE FUENTE DE INGRESO (NACIONAL/EXTRANJERA)
4. 📊 CÁLCULO DE RETEIVA

CONFIGURACIÓN DE BIENES Y SERVICIOS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BIENES QUE NO CAUSAN IVA:
{json.dumps(config_iva['bienes_no_causan_iva'], indent=2, ensure_ascii=False)}

BIENES EXENTOS DE IVA:
{json.dumps(config_iva['bienes_exentos_iva'], indent=2, ensure_ascii=False)}

SERVICIOS EXCLUIDOS DE IVA:
{json.dumps(config_iva['servicios_excluidos_iva'], indent=2, ensure_ascii=False)}

CONFIGURACIÓN RETEIVA:
{json.dumps(config_iva['config_reteiva'], indent=2, ensure_ascii=False)}

DOCUMENTOS DISPONIBLES:
━━━━━━━━━━━━━━━━━━━━━━━━

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

INSTRUCCIONES CRÍTICAS:
━━━━━━━━━━━━━━━━━━━━━━━━━

1. 💰 **IDENTIFICACIÓN DEL IVA EN LA FACTURA**:
   • Analiza el texto de la factura para identificar si menciona IVA
   
   • **ESCENARIO 1**: La factura menciona la totalidad del IVA → Extraer porcentaje y valor
   • **ESCENARIO 2**: La factura menciona IVA de varios conceptos → Sumar todos los IVAs
   • **ESCENARIO 3**: La factura menciona IVA del 0% o no menciona IVA → Validar exención/exclusión

2. 📝 **VALIDACIÓN DE RESPONSABILIDAD DE IVA EN EL RUT**:
   • Buscar en "RESPONSABILIDADES, CALIDADES Y ATRIBUTOS"
   • Código 48: "Impuesto sobre las ventas – IVA" → ES RESPONSABLE DE IVA
   • Código 49: "No responsable de IVA" → NO ES RESPONSABLE DE IVA
   • Código 53: "Persona Jurídica No Responsable de IVA" → NO ES RESPONSABLE DE IVA
   
   **SI EL TERCERO NO ES RESPONSABLE DE IVA**:
   • NO SE CALCULA RETEIVA, NI IVA
   • Especificar: "Según el RUT el tercero NO ES RESPONSABLE DE IVA"
   
   **SI EL RUT NO ESTA DISPONIBLE, O SI NO SE PUEDE IDENTIFICAR LA RESPONSABILIDAD EN EL RUT**:
    • Revisa los anexos y cotizaciones para identificar si el tercero es responsable de IVA   
    
   **SI NO SE PUEDE IDENTIFICAR RESPONSABILIDAD**:
   • Especificar: "No se identificó la responsabilidad (RUT no disponible/no menciona)"
   • NO se puede liquidar

3. 🔍 **VALIDACIÓN DE CONCEPTOS EXENTOS/EXCLUIDOS**:

   **IMPORTANTE** : LA VALIDACION DE CONCEPTOS SOLO LA REALIZAS SI IDENTIFICAS EN LA FACTURA QUE EL IVA ES DEL 0% O NO MENCIONA IVA
   
   SI EL IVA ES DEL 0% O NO MENCIONA IVA:
   • Identificar el CONCEPTO O BIEN FACTURADO
   • Validar contra las listas de bienes/servicios exentos/excluidos
   
   **SI LUEGO DE VALIDAR EL CONCEPTO NO DEBE APLICAR IVA**:
   • Mensaje: "NO APLICA IVA, EL VALOR DEL IVA = 0"
   • Observaciones: Explicar por qué no aplica IVA
   
   **SI EL CONCEPTO SÍ DEBE APLICAR IVA** (pero la factura muestra 0%):
   • Mensaje: "Preliquidación Sin Finalizar"
   • Observaciones: Explicar por qué SÍ aplica IVA

4. 🌍 **DETERMINACIÓN DE FUENTE DE INGRESO**:
   Validar si es FUENTE NACIONAL o EXTRANJERA:
   
   **PREGUNTAS DE VALIDACIÓN**:
   • ¿El servicio tiene uso o beneficio económico en Colombia?
   • ¿La actividad (servicio) se ejecutó total o parcialmente en Colombia?
   • ¿El servicio corresponde a asistencia técnica, consultoría o know-how usado en Colombia?
   • ¿El bien vendido o utilizado está ubicado en Colombia?
   
   **REGLA**: Si CUALQUIERA es SÍ → FUENTE NACIONAL | Si TODAS son NO → FUENTE EXTRANJERA

5. 📉 **VALIDACIÓN ESPECIAL PARA FACTURACIÓN EXTRANJERA**:
   • Si es fuente extranjera, el IVA debe ser del 19%
   • Si aparece IVA diferente al 19% EN LA FACTURA → "Liquidación sin finalizar"
   • Observaciones: Mencionar la inconsistencia

6. 🎆 **CASO ESPECIAL - INCONSISTENCIA RUT vs FACTURA**:
   • Si RUT o los ANEXOS dicen "NO responsable de IVA" pero la factura muestra IVA:
   • Resultado: "Preliquidación sin finalizar"
   • Observaciones: "En el RUT/ANEXOS se identificó que el tercero no es responsable de IVA según el RUT aunque la factura muestra un IVA"

7. 📊 **CÁLCULO DE RETEIVA**:
   • **Fuente Nacional**: ReteIVA = Valor IVA x 15%
   • **Fuente Extranjera**: ReteIVA = Valor IVA x 100%
   • GEMINI solo debe analizar el porcentaje, el cálculo manual se hace en liquidador_iva.py

ESTADOS POSIBLES:
━━━━━━━━━━━━━━━━━━
• **"Preliquidado"** → Todos los requisitos se cumplen
• **"NO APLICA IVA, EL VALOR DEL IVA = 0"** → Tercero no responsable o concepto exento
• **"Preliquidación Sin Finalizar"** → Inconsistencias o falta información

RESPONDE ÚNICAMENTE EN FORMATO JSON VÁLIDO SIN TEXTO ADICIONAL:
{{
    "analisis_iva": {{
        "iva_identificado": {{
            "tiene_iva": true/false,
            "valor_iva_total": 0.0,
            "porcentaje_iva": 0.0,
            "detalle_conceptos_iva": [
                {{
                    "concepto": "Nombre del concepto",
                    "valor_iva": 0.0,
                    "porcentaje": 0.0
                }}
            ],
            "metodo_identificacion": "total_factura|suma_conceptos|iva_cero|no_mencionado"
        }},
        "responsabilidad_iva_rut": {{
            "rut_disponible": true/false,
            "es_responsable_iva": true/false/null,
            "codigo_encontrado": "48|49|53|no_encontrado",
            "texto_referencia": "Texto del RUT donde se encontró"
        }},
        "concepto_facturado": {{
            "descripcion": "Descripción del concepto/bien facturado",
            "aplica_iva": true/false,
            "razon_exencion_exclusion": "Explicación si no aplica IVA",
            "categoria": "no_causa_iva|exento|excluido|gravado"
        }}
    }},
    "analisis_fuente_ingreso": {{
        "validaciones_fuente": {{
            "uso_beneficio_colombia": true/false,
            "ejecutado_en_colombia": true/false,
            "asistencia_tecnica_colombia": true/false,
            "bien_ubicado_colombia": true/false
        }},
        "es_fuente_nacional": true/false,
        "validacion_iva_extranjero": {{
            "es_extranjero": true/false,
            "iva_esperado_19": true/false,
            "iva_encontrado": 0.0
        }}
    }},
    "calculo_reteiva": {{
        "aplica_reteiva": true/false,
        "porcentaje_reteiva": "15%|100%",
        "tarifa_decimal": 0.15,
        "valor_reteiva_calculado": 0.0,
        "metodo_calculo": "fuente_nacional|fuente_extranjera"
    }},
    "estado_liquidacion": {{
        "estado": "Preliquidado|NO APLICA IVA, EL VALOR DEL IVA = 0|Preliquidación Sin Finalizar",
        "observaciones": [
            "Observación 1",
            "Observación 2"
        ]
    }}
}}

🔥 CRÍTICO: 
• Si tercero no responsable de IVA → "NO APLICA IVA, EL VALOR DEL IVA = 0"
• Si concepto exento/excluido y factura muestra IVA=0 → "NO APLICA IVA, EL VALOR DEL IVA = 0"
• Si concepto gravado pero factura muestra IVA=0 → "Preliquidación Sin Finalizar"
• Si es extranjero y IVA ≠ 19% → "Preliquidación Sin Finalizar"
• Solo proceder con ReteIVA si el IVA fue identificado correctamente

    """

if __name__ == '__main__':
    
   
    import sys
    import os
    # Asegurar que el directorio raíz esté en sys.path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    # Llamada correcta: la función acepta 5 argumentos
    prompt = PROMPT_ANALISIS_IVA("hola", "rut", "anexo", "cotizacion", "anexo")
    print(prompt)
