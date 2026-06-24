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
   Número de factura o documento equivalente
   Fecha de emisión/venta
   Valores monetarios (subtotal, total, impuestos)
   Datos del vendedor/proveedor y comprador
   Descripción de bienes o servicios vendidos
   
   SE PUEDE CLASIFICAR COMO FACTURA TAMBIÉN:
   • "SOPORTE EN ADQUISICIONES EFECTUADAS A NO OBLIGADOS A FACTURAR"
   • "CUENTA DE COBRO"
   • "DOCUMENTO EQUIVALENTE"
   • Cualquier documento con estructura de venta/cobro

2. **RUT** - Registro Único Tributario que contiene:
   Número de identificación tributaria (NIT)
   Razón social
   Responsabilidades tributarias
   Actividades económicas CIIU

4. **ANEXO_CONTRATO** - Documento que contiene ESPECÍFICAMENTE:
   Objeto del contrato
   Obligaciones contractuales
   Términos y condiciones del contrato

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


def PROMPT_CLASIFICACION_LOTE(textos_preprocesados: Dict[str, str], nombres_archivos_directos: List[str], proveedor: str = None) -> str:
    """
    Genera el prompt para clasificar un lote de documentos y determinar su relevancia.
    Soporta hasta 10 documentos.
    
    JSON de salida esperado:
    {
        "clasificacion": {
            "nombre_archivo_1": {
                "motivo": "razonamiento breve de la funcion del documento",
                "tipo": "FACTURA|RUT|CONTRATO|COTIZACION|ANEXO|DESCARTABLE",
                "relevante": true/false
            },
            ...
        },
        "factura_identificada": true/false,
        "rut_identificado": true/false
    }

    Nota: el prompt usa un encuadre de juicio fiscal (analista experto) en lugar de
    extraccion literal, conservando los guardrails duros (precedencia de FACTURA,
    coherencia DESCARTABLE->relevante=false, territorial ICA). El campo "motivo" es
    aditivo (CoT ligero) y los consumidores downstream solo leen "tipo"/"relevante".
    """
    todos_los_archivos = nombres_archivos_directos + list(textos_preprocesados.keys())
    total_archivos = len(todos_los_archivos)

    contexto_proveedor = ""
    if proveedor:
        contexto_proveedor = f"\n**PROVEEDOR ESPERADO:** {proveedor}\n"

    return f"""
ROL: Eres un ANALISTA FISCAL EXPERTO en documentos colombianos. Para cada documento de un lote
decides DOS cosas usando tu criterio profesional: (1) su TIPO según la FUNCIÓN que cumple, y
(2) si es RELEVANTE para liquidar impuestos. Razonas sobre el PROPÓSITO del documento; no haces
simple coincidencia de palabras.
{contexto_proveedor}

GROUNDING (no alucinar, pero sí razonar):
• No inventes DATOS que no estén en el documento (cifras, NITs, nombres, fechas, conceptos).
• SÍ usa tu juicio para inferir la FUNCIÓN del documento y su RELEVANCIA fiscal, aunque no haya
  una frase literal que lo diga. Esta tarea es de criterio, no de copiar texto.
• Clasifica el documento COMPLETO, no página por página.
• Los ejemplos de abajo son ANCLAS DE CALIBRACIÓN, no una lista cerrada: para casos no listados,
  razona POR ANALOGÍA con el principio que ilustran.
• Ante duda sobre el TIPO, elige el que mejor describe su función PRINCIPAL. Ante duda sobre
  RELEVANCIA, aplica el PRINCIPIO RECTOR del PASO 2.

═══════════════════════════════════════════════════════════════════════
PASO 1: TIPO DE DOCUMENTO (POR FUNCIÓN)
═══════════════════════════════════════════════════════════════════════

Debes clasificar EXACTAMENTE {total_archivos} documento(s) en UNA de estas categorías:

1. **FACTURA** - El documento que ES el cobro en sí mismo. Para serlo DEBE contener su detalle:
   Número de factura o documento equivalente y fecha
   Valores monetarios DETALLADOS: subtotal, IVA y/o total (OBLIGATORIO)
   Datos de vendedor/proveedor y comprador
   Descripción/ítems de los bienes o servicios (OBLIGATORIO)
   Cuentan también como FACTURA (si muestran valores e ítems): "SOPORTE EN ADQUISICIONES
   EFECTUADAS A NO OBLIGADOS A FACTURAR", "CUENTA DE COBRO", "DOCUMENTO EQUIVALENTE", o cualquier
   estructura de venta/cobro con su detalle.

   NO es FACTURA un documento que solo MENCIONA, ANUNCIA o ENLAZA a una factura sin traer su
   detalle monetario ni los ítems. Ejemplos de calibración:
   • Correo de notificación de la DIAN (remitente tipo "facturacionelectronica@dian.gov.co")
     que dice "Pulse el link para ver el documento" o solo cita el número y un adjunto .zip.
   • CORREO-TRANSPORTE: cualquier correo (.msg/.eml) cuyo cuerpo solo saluda, anuncia o adjunta
     la factura, sin contener él mismo subtotal/IVA/total e ítems. El correo NO es la factura;
     la FACTURA es el adjunto (PDF/XML) que sí trae el detalle. El correo es ANEXO si aporta
     contexto fiscal (NIT, contrato, distribución territorial) o DESCARTABLE si es solo envío.

2. **RUT** - Registro Único Tributario: NIT, razón social, responsabilidades tributarias,
   actividades económicas CIIU.

3. **CONTRATO** - Objeto del contrato, obligaciones contractuales, términos y condiciones.

4. **COTIZACION** - Oferta comercial o presupuesto que no constituye un cobro/factura definitiva.

5. **ANEXO** - Otro documento de soporte con contenido fiscal/contractual útil (certificaciones,
   planillas PILA, anexos de distribución territorial, soportes con datos del cobro, etc.).

6. **DESCARTABLE** - Documento sin función fiscal: sin datos tributarios legibles o que es solo
   ruido/decoración. Ejemplos de calibración:
   • Imágenes/pantallazos SIN datos fiscales legibles: firma de correo, logo, icono, banner,
     sello, separador. Aplica sin importar el nombre del archivo (p. ej. assets tipo
     "Outlook-*.png", "image00X.png"). Si la imagen no contiene cifras, NIT ni texto tributario
     legible, es DESCARTABLE — y trata IGUAL a archivos del mismo tipo (sé consistente).
   • Correos de notificación/transaccionales que solo anuncian o enlazan una factura adjunta.
   • Entregables/datos operativos del servicio facturado (ver PASO 2), aunque tengan muchas cifras.

REGLA DURA DE PRECEDENCIA (no negociable):
• Si DENTRO de un documento aparece una FACTURA, cuenta de cobro o documento equivalente CON sus
  valores e ítems, aunque venga mezclada con anexos, RUT, datos, soportes o ruido, clasifica ESE
  documento OBLIGATORIAMENTE como FACTURA.
• La presencia de una factura/cobro real PREVALECE sobre cualquier otra clasificación
  (DESCARTABLE, ANEXO, CONTRATO, COTIZACION). Aplica haya uno o varios archivos.

═══════════════════════════════════════════════════════════════════════
PASO 2: RELEVANCIA PARA LIQUIDACIÓN
═══════════════════════════════════════════════════════════════════════
Para cada documento indica "relevante" (true/false).

PRINCIPIO RECTOR (tu norte): un documento es relevante si aporta información de naturaleza
TRIBUTARIA, CONTABLE o DEL COBRO que alguna liquidación de impuestos/retenciones podría usar.
NO es relevante el PRODUCTO del trabajo facturado, ni un asset decorativo sin datos. Tener muchas
cifras NO implica relevancia; no tener datos fiscales legibles ⇒ no es relevante. No necesitamos
pruebas de que se ejecutó lo facturado, solo lo que permite el análisis tributario.

PRUEBA DECISIVA (aplícala ante la duda): pregúntate qué DESCRIBE el documento.
• Describe el COBRO o la relación tributaria (factura, contrato, régimen/NIT/RUT del PROVEEDOR,
  retenciones, conceptos facturados, o la distribución de la EJECUCIÓN del servicio por municipio)
  → relevante.
• Describe el RESULTADO ENTREGADO al cliente (registros, beneficiarios, clientes, padrones, datos
  procesados/normalizados, bases de datos) → es el PRODUCTO del trabajo → DESCARTABLE, AUNQUE
  contenga NITs, montos, ciudades o miles de filas. Esos NITs/cifras/ciudades son CONTENIDO del
  entregable, no la relación de cobro del proveedor.

INVARIANTE DE COHERENCIA: si el tipo es DESCARTABLE, "relevante" DEBE ser false, sin excepción.
Y si un documento es relevante para algún impuesto, NO lo marques DESCARTABLE.

Anclas de calibración (representativas, NO exhaustivas — razona por analogía):

• NO RELEVANTE (relevante = false):
  - Imágenes/pantallazos sin datos fiscales: firmas, logos, iconos, banners, sellos.
  - Correos de cuerpo vacío o que solo anuncian/enlazan a una factura adjunta.
  - Excel sin cifras fiscales o vacíos.
  - Entregables, productos o pruebas de ejecución del servicio facturado, AUNQUE tengan muchísimas
    cifras: bases de datos, volcados o muestras de datos, listados de registros (hojas con columnas
    tipo id, nombre, teléfono, correo, organización, beneficiario), informes de resultados o data
    procesada/normalizada entregada al cliente.
    Pista de nombre: archivos llamados "Bases", "Base de datos", "BD", "padrón", "listado", "data"
    o "registros" suelen ser entregables → DESCARTABLE, salvo que la PRUEBA DECISIVA indique lo contrario.
    EXCEPCIÓN ACOTADA (insumo de ICA): consérvalo SOLO si declara cómo se DISTRIBUYE LA EJECUCIÓN
    DEL SERVICIO/CONTRATO del proveedor entre municipios (p. ej. "el servicio se prestó 60% en
    Bogotá, 40% en Cali", "municipios donde se ejecutó el contrato", tabla de municipios con % de
    ejecución del contrato). NO aplica a un dato geográfico que sea CONTENIDO del entregable (una
    columna de ciudad/departamento de los registros, beneficiarios o clientes): eso sigue siendo
    entregable → DESCARTABLE.
  - Cotizaciones informativas que no acompañan a un cobro real.

• RELEVANTE (relevante = true):
  - Facturas, cuentas de cobro, soportes a no obligados.
  - RUTs.
  - Contratos.
  - Planillas de seguridad social (PILA) — SIEMPRE relevantes.
  - Certificados de deducción del Artículo 383 o de retención — SIEMPRE relevantes.
  - Cualquier documento con valores, fechas, conceptos facturados o NIT/RUT DEL PROVEEDOR/COMPRADOR
    o del contrato, aplicables al análisis tributario. (NO cuentan los NITs/valores que aparezcan
    como dato DENTRO de un entregable o base de datos.)
  - Distribución de la EJECUCIÓN del servicio del proveedor (insumo de ICA): documento, correo o
    anexo que declara en qué municipios el PROVEEDOR ejecutó o prestó el servicio/contrato, o los
    porcentajes de ejecución por municipio (p. ej. "% de ejecución del contrato por ciudad",
    "distribución del servicio por municipio", tabla de municipios con % de ejecución). Determinan
    en qué municipios se distribuye el ICA: SIEMPRE relevantes (tipo ANEXO + relevante=true, NUNCA
    DESCARTABLE). OJO: NO es esto una columna geográfica de los registros/beneficiarios dentro de un
    entregable (eso es DESCARTABLE).
  - Regla para Excel/anexo: es relevante SOLO si aporta naturaleza tributaria o del cobro (valores
    de factura, subtotal, IVA, base gravable, retenciones, conceptos facturados, NIT/RUT del
    proveedor/comprador, datos del contrato, PILA, certificados de deducción) o la distribución de la
    ejecución del servicio por municipio para ICA. Una tabla de datos operativos/del negocio del
    cliente, sin esa naturaleza fiscal, es DESCARTABLE.

**factura_identificada = true** si en ESTE lote encuentras alguna FACTURA o equivalente.
**rut_identificado = true** si en ESTE lote encuentras algún RUT.

═══════════════════════════════════════════════════════════════════════
DOCUMENTOS A ANALIZAR EN ESTE LOTE
═══════════════════════════════════════════════════════════════════════

REGLA DE IDENTIDAD DE LOS ADJUNTOS (crítica):
• Cada archivo adjunto va precedido por un marcador de texto con su nombre, así:
  "===== DOCUMENTO ADJUNTO: <nombre> =====". Todo el contenido entre un marcador y el
  siguiente pertenece EXCLUSIVAMENTE a ese archivo.
• Cada archivo es un DOCUMENTO INDEPENDIENTE y COMPLETO. NO asumas que varios archivos son
  páginas del mismo documento, ni propagues el contenido de un archivo a otro.
• Clasifica cada archivo por SU PROPIO contenido (el que aparece bajo su marcador), aunque otro
  archivo del lote luzca similar. Un PDF puede tener varias páginas internas; eso NO convierte a
  los demás archivos en páginas suyas.

**ARCHIVOS DIRECTOS:**
{_formatear_archivos_directos(nombres_archivos_directos)}

**TEXTOS PREPROCESADOS:**
{_formatear_textos_preprocesados(textos_preprocesados)}

═══════════════════════════════════════════════════════════════════════
FORMATO DE RESPUESTA OBLIGATORIO (JSON ESTRICTO)
═══════════════════════════════════════════════════════════════════════

Para cada documento, escribe PRIMERO "motivo" (máx. 15 palabras: la función del documento y por
qué ese tipo/relevancia) y LUEGO "tipo" y "relevante". Razonar el motivo antes de etiquetar es
obligatorio.

{{
    "clasificacion": {{
        "nombre_archivo_1": {{
            "motivo": "razonamiento breve de la función del documento",
            "tipo": "FACTURA|RUT|CONTRATO|COTIZACION|ANEXO|DESCARTABLE",
            "relevante": true/false
        }},
        "nombre_archivo_2": {{
            "motivo": "razonamiento breve de la función del documento",
            "tipo": "FACTURA|RUT|CONTRATO|COTIZACION|ANEXO|DESCARTABLE",
            "relevante": true/false
        }}
    }},
    "factura_identificada": true/false,
    "rut_identificado": true/false
}}

RECORDATORIOS FINALES:
• Clasifica TODOS los documentos del lote.
• REGLA DURA DE PRECEDENCIA: un documento con una factura real (valores e ítems) es FACTURA, por
  encima de cualquier otra clasificación.
• INVARIANTE: tipo DESCARTABLE ⇒ relevante=false.
• Trata de forma CONSISTENTE a los archivos de la misma naturaleza dentro del lote.
• Devuelve un JSON válido.
"""


def PROMPT_ANALISIS_GLOBAL(textos_preprocesados: Dict[str, str], nombres_archivos_directos: List[str], proveedor: str = None) -> str:
    """
    Genera el prompt para el análisis global de los documentos ya filtrados.
    Extrae flags de consorcio, ubicación del proveedor y fuente de ingreso.
    
    JSON de salida esperado:
    {
        "es_consorcio": true/false,
        "indicadores_consorcio": ["cita textual exacta"],
        "ubicacion_proveedor": "Texto exacto de la ubicación o vacío",
        "es_fuera_colombia": true/false,
        "analisis_fuente_ingreso": {
            "servicio_uso_colombia": true/false/null,
            "evidencias_uso_encontradas": ["cita textual"],
            "ejecutado_en_colombia": true/false/null,
            "evidencias_ejecucion_encontradas": ["cita textual"],
            "asistencia_tecnica_colombia": true/false/null,
            "evidencias_asistencia_encontradas": ["cita textual"],
            "bien_ubicado_colombia": true/false/null,
            "evidencias_bien_encontradas": ["cita textual"]
        }
    }
    """
    todos_los_archivos = nombres_archivos_directos + list(textos_preprocesados.keys())
    total_archivos = len(todos_los_archivos)

    contexto_proveedor = ""
    if proveedor:
        contexto_proveedor = f"""
═══════════════════════════════════════════════════════════════════════
INFORMACIÓN DEL PROVEEDOR (CONTEXTO DE VALIDACIÓN)
═══════════════════════════════════════════════════════════════════════

**PROVEEDOR ESPERADO:** {proveedor}

INSTRUCCIONES DE VALIDACIÓN CONTRA RUT:
• Verifica que el nombre/razón social del proveedor en la FACTURA coincida con el RUT
• NIT en la FACTURA vs NIT en el RUT
• Si es CONSORCIO o UNIÓN TEMPORAL:
  - Identifica los miembros del consorcio
  - Verifica los porcentajes de participación
  - Reporta discrepancias
"""

    return f"""
ROL: Eres un ANALISTA FISCAL de documentos colombianos.
Tu función es analizar el conjunto de documentos relevantes y extraer flags y datos de negocio consolidados de forma literal.
{contexto_proveedor}

 REGLA FUNDAMENTAL ANTI-ALUCINACIÓN:
• PROHIBIDO deducir, interpretar o suponer información
• SOLO usa texto que puedas CITAR LITERALMENTE del documento
• Si no encuentras evidencia textual explícita → marca como false/null/vacío

═══════════════════════════════════════════════════════════════════════
PASO 1: DETECCIÓN DE CONSORCIO
═══════════════════════════════════════════════════════════════════════
**es_consorcio = true** SOLO SI encuentras TEXTUALMENTE:
• La palabra "CONSORCIO" en el nombre/razón social del proveedor
• La palabra "UNIÓN TEMPORAL" en el nombre/razón social
• Texto explícito: "consorciados", "miembros del consorcio"
• Porcentajes de participación: "Empresa A: 60%, Empresa B: 40%"

Si no encuentras estas palabras EXACTAS o evidencia → es_consorcio = false

═══════════════════════════════════════════════════════════════════════
PASO 2: DETERMINACIÓN DE UBICACION DEL PROVEEDOR 
═══════════════════════════════════════════════════════════════════════
Para determinar si el proveedor está fuera de Colombia, extrae la ubicación del proveedor buscando TEXTUALMENTE en la FACTURA.
Buscar texto similar a Direccion, Ciudad, Pais, Domicilio, Sede Principal, Sucursal, Oficina, Establecimiento.

"ubicacion_proveedor": "Texto exacto de la ubicación extraído de la factura" o ""

Si la ubicación indica que el proveedor está fuera de Colombia: "es_fuera_colombia": true
Si la ubicación indica que el proveedor está en Colombia: "es_fuera_colombia": false

═══════════════════════════════════════════════════════════════════════
PASO 3: DETERMINACIÓN DE FUENTE DE INGRESO (NACIONAL vs EXTRANJERA)
═══════════════════════════════════════════════════════════════════════
Responde estas preguntas basándote SOLO en texto explícito de todos los documentos:

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
DOCUMENTOS RELEVANTES A ANALIZAR
═══════════════════════════════════════════════════════════════════════

**ARCHIVOS DIRECTOS:**
{_generar_seccion_archivos_directos(nombres_archivos_directos)}

**TEXTOS PREPROCESADOS:**
{_formatear_textos_preprocesados(textos_preprocesados)}

═══════════════════════════════════════════════════════════════════════
FORMATO DE RESPUESTA OBLIGATORIO (JSON ESTRICTO)
═══════════════════════════════════════════════════════════════════════

{{
    "es_consorcio": true/false,
    "indicadores_consorcio": ["cita textual exacta"],
    "ubicacion_proveedor": "Texto exacto de la ubicación extraido de la factura o vacío",
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
"""

