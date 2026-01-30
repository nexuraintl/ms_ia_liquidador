"""
PROMPTS PARA ANALISIS ICA (INDUSTRIA Y COMERCIO)
================================================

Prompts especializados para identificar ubicaciones y actividades
sujetas a retención de ICA según normativa colombiana.

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo generación de prompts ICA
- OCP: Abierto para extensión - nuevos prompts sin modificar existentes
- DIP: Funciones puras sin dependencias externas

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

import json
from typing import List, Dict, Any

# Importar función para generar sección de archivos directos
from prompts.prompt_clasificador import _generar_seccion_archivos_directos


def crear_prompt_identificacion_ubicaciones(
    ubicaciones_bd: List[Dict[str, Any]],
    textos_documentos: Dict[str, str],
    nombres_archivos_directos: List[str] = None
) -> str:
    """
    Crea prompt para que Gemini identifique ubicaciones donde se ejecuta la actividad.

    RESPONSABILIDAD (SRP):
    - Solo genera el prompt de identificación de ubicaciones
    - No procesa respuestas ni valida datos

    Args:
        ubicaciones_bd: Lista de ubicaciones de la base de datos
                       [{"codigo_ubicacion": 1, "nombre_ubicacion": "BOGOTA D.C.",
                         "nombre_departamento": "BOGOTA D.C."}, ...]
        textos_documentos: Diccionario con textos de documentos adjuntos
        nombres_archivos_directos: Lista de nombres de archivos directos (para multimodalidad)

    Returns:
        str: Prompt estructurado para Gemini (mostrará formato "CIUDAD (DEPARTAMENTO)")
    """

    # Formatear ubicaciones de la base de datos
    ubicaciones_formateadas = "\n".join([
        f"- Código {ub['codigo_ubicacion']}: {ub['nombre_ubicacion']}" +
        (f" ({ub['nombre_departamento']})" if ub.get('nombre_departamento') else "")
        for ub in ubicaciones_bd
    ])

    # Formatear documentos
    docs_formateados = ""
    for nombre, contenido in textos_documentos.items():
        docs_formateados += f"\n{'='*80}\n"
        docs_formateados += f"ARCHIVO: {nombre}\n"
        docs_formateados += f"{'='*80}\n"
        docs_formateados += f"{contenido}\n"

    return f"""
ROL: Eres un ANALISTA EXPERTO en retención de ICA (Industria y Comercio) en Colombia.
Tu función es IDENTIFICAR las ubicaciones donde se ejecuta la actividad facturada.

REGLA FUNDAMENTAL:
- SOLO usa información que puedas CITAR TEXTUALMENTE de los documentos
- PROHIBIDO deducir o suponer ubicaciones
- Si no encuentras evidencia clara, marca codigo_ubicacion = 0

═══════════════════════════════════════════════════════════════════════
PASO 1: UBICACIONES PARAMETRIZADAS EN BASE DE DATOS
═══════════════════════════════════════════════════════════════════════

{ubicaciones_formateadas}

IMPORTANTE: Solo estas ubicaciones están parametrizadas en el sistema.

═══════════════════════════════════════════════════════════════════════
PASO 2: DOCUMENTOS ADJUNTOS A ANALIZAR
═══════════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}

{docs_formateados}

═══════════════════════════════════════════════════════════════════════
PASO 3: INSTRUCCIONES DE IDENTIFICACIÓN
═══════════════════════════════════════════════════════════════════════

BUSCAR EN LA FACTURA:
1. Actividad facturada
2. Ubicación textual de la actividad facturada.


UBICACIONES POR ACTIVIDAD FACTURADA:

TRANSPORTE :

- Si la actividad facturada es Transporte, entonces la ubicación que tienes que extraer es la ubicación en donde se entrega el bien, mercancía o persona.  Busca palabras clave similares a las siguientes:

 "Destino", "Punto de fin", "Entrega en", "Lugar de entrega" , "Direccion de descarga"
 
 IMPORTANTE TRANSPORTE: Si la actividad facturada es transporte y NO se encuentra la ubicacion de entrega entonces asigna : - nombre_ubicacion = "" , codigo_ubicacion = 0, texto_identificador = "", porcentaje_ejecucion = 0.0

TELEVISION E INTERNET POR SUSCIPCION Y TELEFONIA FIJA :

- Si la actividad facturada esta relacionada con servicios de televisión e internet por suscripción y telefonía fija. La ubicación seleccionada será el lugar en el que se encuentre el suscriptor del servicio según el Contrato. Busca palabras clave similares a las siguientes:

 "Dirección del suscriptor:", "Domicilio del servicio:"
 "Dirección de instalación:", "Punto de servicio:"
 "Ubicación del contrato:", "Dirección de facturación:"

 IMPORTANTE SERVICIOS TELEVISION E INTERNET : Si la actividad facturada es televisión e internet por suscripción y telefonía fija y NO se encuentra la ubicacion en la que se encuentre el suscriptor del servicio entonces asigna : - nombre_ubicacion = "" , codigo_ubicacion = 0, texto_identificador = "", porcentaje_ejecucion = 0.0

SERVICIOS DE TELEFONIA MOVIL -NAVEGACION MOVIL -DATOS MOVILES :

- Si la actividad facturada es servicio de telefonia movil, navegacion movil o servicio de datos moviles la ubicacion seleccionada sera la del lugar donde se encuentre el suscriptor del servicio segun el contrato o en el documento de actualizacion. Busca palabras clave similares a las siguientes:

 "Dirección del titular:", "Domicilio registrado:"

 IMPORTANTE TELEFONICA MOVIL - NAVEGACION MOVIL - DATOS MOVILES : Si la actividad facturada es de telefonia movil, navegacion movil o servicio de datos moviles y NO se encuentra la ubicacion en la que se encuentre el suscriptor del servicio entonces asigna : - nombre_ubicacion = "" , codigo_ubicacion = 0, texto_identificador = "", porcentaje_ejecucion = 0.0

COMPRAS GENERICAS DE BIENES O PRODUCTOS : 

- Si la actividad facturada es una compra generica de algun producto o bien, la ubicacion seleccionada sera la ubicacion del proovedor o vendedor del bien o producto, la cual esta indicada en la FACTURA.

 IMPORTANTE COMPRAS: Si la actividad facturada es una compra generica y NO se encuentra la ubicacion de proveedor o vendedor del bien o producto entonces asigna : - nombre_ubicacion = "" , codigo_ubicacion = 0, texto_identificador = "", porcentaje_ejecucion = 0.0

SERVICIOS GENERICOS :

- Si la actividad facturada es un servicio generico no clasifificado en las actividades anteriores, la ubicacion seleccionada sera el lugar en donde se preste el servicio segun lo indicado en el contrato o en la factura. Busca palabras clave similares a las siguientes: 

" Servicios prestados en ", " Lugar de ejecución: ", " Prestación del servicio en ",
" Ejecución en ", " Realizado en ", "ejecutado en ", "Municipio de Prestación del Servicio: 

 IMPORTANTE SERVICIOS GENERICOS: Si la actividad facturada es una Servicio prestado  y NO se encuentra el lugar en donde se preste el servicio entonces asigna : - nombre_ubicacion = "" , codigo_ubicacion = 0, texto_identificador = "", porcentaje_ejecucion = 0.0


IMPORTANTE ACTIVIDAD FACTURADA:
- menciona en observaciones que se identifico la ubicacion (x) correspondiente a la actividad facturada (y).

═══════════════════════════════════════════════════════════════════════
PASO 4: MATCHING CON BASE DE DATOS (OBLIGATORIO)
═══════════════════════════════════════════════════════════════════════

- Buscar la ubicación identificada en la lista de la base de datos :
 - Si la encuentras en la base de datos : copiar EXACTAMENTE codigo_ubicacion y nombre_ubicacion
 - Si NO la encuentras en la base de datos : codigo_ubicacion = 0, nombre_ubicacion = "NOMBRE EN MAYUSCULAS SIN ACENTOS"
 

VALIDACIONES OBLIGATORIAS:


* Revisa la actividad facturada antes de proceder a identificar ubicaciones.

Si encuentras UNA sola ubicación:
- porcentaje_ejecucion = 100 (siempre, aunque no aparezca en documentos)

- texto_identificador = "CITA TEXTUAL del documento donde identificaste la ubicación"

Si encuentras MULTIPLES ubicaciones:
- Para CADA ubicación extraer el porcentaje de ejecución (formato 70 si aparece 70%)
- Si NO aparece el porcentaje explícitamente: porcentaje_ejecucion = 0.0
- Para cada una validar si está en la base de datos
- texto_identificador = "CITA TEXTUAL del documento donde identificaste CADA ubicación"

VALIDACION CRITICA:
- La suma de porcentajes_ejecucion debe ser 100% (si hay múltiples ubicaciones)

Si NO encuentras ubicación:
- nombre_ubicacion = ""
- codigo_ubicacion = 0
- texto_identificador = ""
- porcentaje_ejecucion = 0.0

Agrega las observaciones que consideres relevantes en el campo "observaciones" del JSON.

═══════════════════════════════════════════════════════════════════════
PASO 5: FORMATO DE RESPUESTA JSON (OBLIGATORIO)
═══════════════════════════════════════════════════════════════════════

Debes responder UNICAMENTE con un JSON válido siguiendo esta estructura EXACTA:

{{
  "ubicaciones": [
    {{
      "nombre_ubicacion": "NOMBRE EXACTO como aparece en BD (SIN MAYUSCULAS SIN ACENTOS si no está en BD)",
      "codigo_ubicacion": 1,
      "texto_identificador": "CITA TEXTUAL del documento",
      "porcentaje_ejecucion": 100.0
    }},
    {{
      "nombre_ubicacion": "SEGUNDA UBICACION (solo si aplica)",
      "codigo_ubicacion": 2,
      "texto_identificador": "CITA TEXTUAL del documento",
      "porcentaje_ejecucion": 0.0
    }}
  ],
  "observaciones": "Cualquier observación relevante"
}}

EJEMPLO 1 - Una ubicación encontrada en BD:
{{
  "ubicaciones": [
    {{
      "nombre_ubicacion": "BOGOTA D.C.",
      "codigo_ubicacion": 1,
      "texto_identificador": "Lugar de ejecución: Bogotá D.C., Carrera 7 # 12-34",
      "porcentaje_ejecucion": 100.0
    }}
  ],
  "observaciones": "Cualquier observación relevante"
}}

EJEMPLO 2 - Múltiples ubicaciones con porcentajes:
{{
  "ubicaciones": [
    {{
      "nombre_ubicacion": "BOGOTA D.C.",
      "codigo_ubicacion": 1,
      "texto_identificador": "Ejecución en Bogotá: 60% del contrato",
      "porcentaje_ejecucion": 60.0
    }},
    {{
      "nombre_ubicacion": "MEDELLIN",
      "codigo_ubicacion": 5,
      "texto_identificador": "Ejecución en Medellín: 40% del contrato",
      "porcentaje_ejecucion": 40.0
    }}
  ],
  "observaciones": "Cualquier observación relevante"
}}

EJEMPLO 3 - Ubicación NO encontrada en BD:
{{
  "ubicaciones": [
    {{
      "nombre_ubicacion": "zipaquira",
      "codigo_ubicacion": 0,
      "texto_identificador": "Servicio prestado en el municipio de Zipaquirá",
      "porcentaje_ejecucion": 100.0
    }}
  ],
  "observaciones": "Cualquier observación relevante"
}}

EJEMPLO 4 - NO se encontró ubicación:
{{
  "ubicaciones": [
    {{
      "nombre_ubicacion": "",
      "codigo_ubicacion": 0,
      "texto_identificador": "",
      "porcentaje_ejecucion": 0.0
    }}
  ],
  "observaciones": "No se encontró ubicación en los documentos proporcionados o no se encontrar documentos"
}}

IMPORTANTE:
- Responde SOLO con el JSON, sin texto adicional
- NO agregues comentarios fuera del JSON
- Valida que sea JSON válido antes de responder
"""


def crear_prompt_relacionar_actividades(
    ubicaciones_identificadas: List[Dict[str, Any]],
    actividades_bd_por_ubicacion: Dict[str, List[Dict[str, Any]]],
    textos_documentos: Dict[str, str],
    nombres_archivos_directos: List[str] = None
) -> str:
    """
    Crea prompt para que Gemini relacione actividades facturadas con actividades de BD.

    RESPONSABILIDAD (SRP):
    - Solo genera el prompt de relación de actividades
    - No procesa respuestas ni calcula tarifas

    Args:
        ubicaciones_identificadas: Ubicaciones identificadas en llamada anterior
                                  [{"nombre_ubicacion": "BOGOTA", "codigo_ubicacion": 1}, ...]
        actividades_bd_por_ubicacion: Actividades de BD agrupadas por ubicación
                                      {"1": [{"codigo_actividad": 10, "descripcion": "..."}, ...]}
        textos_documentos: Diccionario con textos de documentos (especialmente FACTURA)
        nombres_archivos_directos: Lista de nombres de archivos directos (para multimodalidad)

    Returns:
        str: Prompt estructurado para Gemini
    """

    # Formatear ubicaciones identificadas
    ubicaciones_str = "\n".join([
        f"- {ub['nombre_ubicacion']} (Código: {ub['codigo_ubicacion']})"
        for ub in ubicaciones_identificadas
    ])

    # Formatear actividades por ubicación
    actividades_str = ""
    for cod_ubicacion, actividades in actividades_bd_por_ubicacion.items():
        ubicacion_nombre = next(
            (u['nombre_ubicacion'] for u in ubicaciones_identificadas
             if str(u['codigo_ubicacion']) == str(cod_ubicacion)),
            f"Código {cod_ubicacion}"
        )
        actividades_str += f"\n{'='*80}\n"
        actividades_str += f"ACTIVIDADES PARA: {ubicacion_nombre} (Código: {cod_ubicacion})\n"
        actividades_str += f"{'='*80}\n"

        for act in actividades:
            actividades_str += f"\nCódigo Actividad: {act['codigo_actividad']}\n"
            actividades_str += f"Descripción: {act['descripcion_actividad']}\n"
            actividades_str += f"Tipo: {act['tipo_actividad']}\n"
            actividades_str += f"Tarifa ICA: {act['porcentaje_ica']}%\n"
            actividades_str += f"-" * 40 + "\n"

    # Formatear documentos (enfocado en FACTURA)
    docs_formateados = ""
    for nombre, contenido in textos_documentos.items():
        docs_formateados += f"\n{'='*80}\n"
        docs_formateados += f"ARCHIVO: {nombre}\n"
        docs_formateados += f"{'='*80}\n"
        docs_formateados += f"{contenido}\n"

    return f"""
ROL: Eres un ANALISTA EXPERTO en clasificación de actividades económicas para ICA en Colombia.
Tu función es RELACIONAR actividades facturadas con actividades parametrizadas en base de datos e identificar si el proovedor es autorretenedor de ICA.

REGLA FUNDAMENTAL:
- TuS UNICOS trabajos es IDENTIFICAR , RELACIONAR conceptos e identificar si el proovedor es autorretenedor de ICA.
- NO calculas tarifas, NO validas normativa, NO haces cálculos
- SOLO relacionas actividades de la FACTURA con actividades de la BASE DE DATOS y revisas si el proovedor es autorretenedor de ICA en el RUT

═══════════════════════════════════════════════════════════════════════
PASO 1: UBICACIONES IDENTIFICADAS (PASO ANTERIOR)
═══════════════════════════════════════════════════════════════════════

{ubicaciones_str}

═══════════════════════════════════════════════════════════════════════
PASO 2: ACTIVIDADES PARAMETRIZADAS EN BASE DE DATOS POR UBICACION
═══════════════════════════════════════════════════════════════════════
REVISA TODAS las actividades disponibles:

{actividades_str}

═══════════════════════════════════════════════════════════════════════
PASO 3: DOCUMENTOS A ANALIZAR (ENFOQUE EN FACTURA y RUT)
═══════════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}

{docs_formateados}

═══════════════════════════════════════════════════════════════════════
PASO 4: INSTRUCCIONES DE RELACION
═══════════════════════════════════════════════════════════════════════

PROCESO OBLIGATORIO:

1. EXTRAER de la FACTURA:
   - TODAS las actividades facturadas (TEXTUALES, tal como aparecen en la factura)
   - El valor de la FACTURA SIN IVA (valor único para todas las actividades)

2. RELACIONAR TODAS las actividades facturadas EN CONJUNTO con actividades de la BD:
   - Analizar TODAS las actividades facturadas como un grupo
   - Relacionarlas con actividades de la base de datos
   - MAPEA EL CONJUNTO de actividades facturadas con LAS ACTIVIDAD MAS PRECISA DE LA BASE DE DATOS POR UBICACION
   - PUEDE HABER múltiples actividades relacionadas SOLO si son de DIFERENTES ubicaciones
   - Para la MISMA ubicación, SOLO PUEDE HABER UNA actividad relacionada
   

3. IMPORTANTE:
   - Si no encuentras actividades facturadas claras marca -> actividades facturadas : []
   - Si encuentras múltiples actividades relacionadas, DEBEN ser de DIFERENTES ubicaciones (codigo_ubicacion diferente)
   - NUNCA dos actividades relacionadas con el mismo codigo_ubicacion
   - Si NO encuentras ninguna relación, dejar actividades_relacionadas con: nombre_act_rel = "", codigo_actividad = 0, codigo_ubicacion = 0
   
4.EXTRAER DEL RUT (Formulario de Registro Unico Tributario):
    -  Busca literalmente en el RUT "AUTORRETENEDOR DE ICA", Si encuentras en el RUT que el proovedor es AUTORRETENEDOR DE ICA , marca el parametro "autorretenedor_ica": true en el JSON de respuesta, de lo contrario marca "autorretenedor_ica": false

═══════════════════════════════════════════════════════════════════════
PASO 5: FORMATO DE RESPUESTA JSON (OBLIGATORIO)
═══════════════════════════════════════════════════════════════════════

Debes responder UNICAMENTE con un JSON válido siguiendo esta estructura EXACTA:

{{
  "actividades_facturadas": ["ACTIVIDAD 1 TEXTUAL de la FACTURA", "ACTIVIDAD 2 TEXTUAL de la FACTURA"],
  "actividades_relacionadas": [
    {{
      "nombre_act_rel": "DESCRIPCION TEXTUAL de BD para ubicación 1",
      "codigo_actividad": 10,
      "codigo_ubicacion": 1
    }},
    {{
      "nombre_act_rel": "DESCRIPCION TEXTUAL de BD para ubicación 2",
      "codigo_actividad": 15,
      "codigo_ubicacion": 2
    }}
  ],
  "valor_factura_sin_iva": 1000000.0,
  "autorretenedor_ica": true | false
}}

EJEMPLO 1 - Una actividad, una ubicación no autorretenedor de ica :
{{
  "actividades_facturadas": ["Servicios de consultoría en sistemas y soporte técnico"],
  "actividades_relacionadas": [
    {{
      "nombre_act_rel": "Servicios de consultoría en informática",
      "codigo_actividad": 620100,
      "codigo_ubicacion": 1
    }}
  ],
  "valor_factura_sin_iva": 5000000.0,
  "autorretenedor_ica": false
}}

EJEMPLO 2 - Múltiples actividades facturadas, múltiples ubicaciones, no autorretenedor de ica :
{{
  "actividades_facturadas": ["Servicios de ingeniería civil", "Diseño arquitectónico", "Supervisión técnica"],
  "actividades_relacionadas": [
    {{
      "nombre_act_rel": "Servicios de ingeniería y arquitectura",
      "codigo_actividad": 711000,
      "codigo_ubicacion": 1
    }},
    {{
      "nombre_act_rel": "Servicios de ingeniería y arquitectura",
      "codigo_actividad": 711000,
      "codigo_ubicacion": 5
    }}
  ],
  "valor_factura_sin_iva": 10000000.0,
  "autorretenedor_ica": false
}}

EJEMPLO 3 - Múltiples actividades, una ubicación, autorretenedor de ica :
{{
  "actividades_facturadas": ["Servicios de consultoría empresarial", "Servicios de capacitación", "Asesoría administrativa"],
  "actividades_relacionadas": [
    {{
      "nombre_act_rel": "Servicios de consultoría empresarial",
      "codigo_actividad": 702000,
      "codigo_ubicacion": 1
    }}
  ],
  "valor_factura_sin_iva": 5000000.0,
  "autorenedor_ica": true
}}

EJEMPLO 4 - NO se pudo relacionar, no autorenedor de ica :
{{
  "actividades_facturadas": ["Servicios varios no especificados", "Otros servicios"],
  "actividades_relacionadas": [
    {{
      "nombre_act_rel": "",
      "codigo_actividad": 0,
      "codigo_ubicacion": 0
    }}
  ],
  "valor_factura_sin_iva": 1000000.0,
  "autorretenedor_ica": false
}}

EJEMPLO 5 - NO se pudo identificar la actividad facturada, no autorenedor de ica :
{{
  "actividades_facturadas": [],
  "actividades_relacionadas": [
    {{
      "nombre_act_rel": "",
      "codigo_actividad": 0,
      "codigo_ubicacion": 0
    }}
  ],
  "valor_factura_sin_iva": 1000000.0,
  "autorretenedor_ica": false
}}

IMPORTANTE:
- Responde SOLO con el JSON, sin texto adicional
- NO agregues comentarios fuera del JSON
- Valida que sea JSON válido antes de responder
- actividades_facturadas es una LISTA SIMPLE de strings (textos de la factura)
- actividades_relacionadas es una LISTA UNICA (no anidada)
- SOLO puede haber múltiples actividades relacionadas si tienen DIFERENTE codigo_ubicacion
- valor_factura_sin_iva es el valor total de la factura SIN IVA
"""


def limpiar_json_gemini(respuesta_gemini: str) -> str:
    """
    Limpia la respuesta de Gemini para extraer solo el JSON válido.

    RESPONSABILIDAD (SRP):
    - Solo limpia y extrae JSON de respuestas de Gemini
    - No procesa ni valida el contenido del JSON

    Args:
        respuesta_gemini: Respuesta cruda de Gemini

    Returns:
        str: JSON limpio y válido
    """
    # Eliminar bloques de código markdown
    respuesta_limpia = respuesta_gemini.strip()

    if respuesta_limpia.startswith("```json"):
        respuesta_limpia = respuesta_limpia[7:]
    elif respuesta_limpia.startswith("```"):
        respuesta_limpia = respuesta_limpia[3:]

    if respuesta_limpia.endswith("```"):
        respuesta_limpia = respuesta_limpia[:-3]

    return respuesta_limpia.strip()


def validar_estructura_ubicaciones(data: Dict[str, Any]) -> bool:
    """
    Valida que el JSON de ubicaciones tenga la estructura correcta.

    RESPONSABILIDAD (SRP):
    - Solo valida estructura de JSON de ubicaciones
    - No valida lógica de negocio

    Args:
        data: Diccionario parseado de JSON

    Returns:
        bool: True si la estructura es válida
    """
    if "ubicaciones" not in data:
        return False

    if not isinstance(data["ubicaciones"], list):
        return False

    if len(data["ubicaciones"]) == 0:
        return False

    campos_requeridos = ["nombre_ubicacion", "codigo_ubicacion", "texto_identificador", "porcentaje_ejecucion"]

    for ubicacion in data["ubicaciones"]:
        for campo in campos_requeridos:
            if campo not in ubicacion:
                return False

    return True


def validar_estructura_actividades(data: Dict[str, Any]) -> bool:
    """
    Valida que el JSON de actividades tenga la estructura correcta (NUEVO FORMATO v3.0).

    RESPONSABILIDAD (SRP):
    - Solo valida estructura de JSON de actividades
    - No valida lógica de negocio

    Args:
        data: Diccionario parseado de JSON

    Returns:
        bool: True si la estructura es válida
    """
    # Validar campos principales
    if "actividades_facturadas" not in data:
        return False
    if "actividades_relacionadas" not in data:
        return False
    if "valor_factura_sin_iva" not in data:
        return False
    if "autorretenedor_ica" not in data:
        return False

    # Validar actividades_facturadas (lista simple de strings)
    if not isinstance(data["actividades_facturadas"], list):
        return False

    # Validar actividades_relacionadas (lista de objetos)
    if not isinstance(data["actividades_relacionadas"], list):
        return False

    for rel in data["actividades_relacionadas"]:
        if "nombre_act_rel" not in rel:
            return False
        if "codigo_actividad" not in rel:
            return False
        if "codigo_ubicacion" not in rel:
            return False

    # Validar valor_factura_sin_iva es numérico
    if not isinstance(data["valor_factura_sin_iva"], (int, float)):
        return False
      
    if not isinstance(data["autorretenedor_ica"], bool):   
        return False

    return True
