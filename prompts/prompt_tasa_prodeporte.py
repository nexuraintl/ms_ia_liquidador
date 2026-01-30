"""
PROMPT PARA ANALISIS DE TASA PRODEPORTE
========================================

Prompt especializado para extracción de datos de Tasa Prodeporte.

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo prompts de Tasa Prodeporte
- OCP: Abierto para extensión
- DIP: Funciones puras

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

from typing import List

# Import de función auxiliar compartida
from .prompt_clasificador import _generar_seccion_archivos_directos


def PROMPT_ANALISIS_TASA_PRODEPORTE(factura_texto: str, anexos_texto: str, observaciones_texto: str = "", nombres_archivos_directos: list[str] = None) -> str:
    """
    Prompt para extracción de datos de Tasa Prodeporte.

    Gemini SOLO extrae datos, NO calcula ni valida.
    Python realiza todas las validaciones y cálculos.

    Args:
        factura_texto: Texto extraído de la factura
        anexos_texto: Texto de anexos adicionales
        observaciones_texto: Observaciones del usuario
        nombres_archivos_directos: Lista de nombres de archivos directos

    Returns:
        str: Prompt formateado para Gemini
    """
    return f"""
ANALISIS DE TASA PRODEPORTE - SOLO EXTRACCION DE DATOS

Tu responsabilidad es UNICAMENTE extraer informacion de los documentos.
NO debes calcular ningun impuesto, solo identificar datos.

═══════════════════════════════════════════════════════════════════════
DOCUMENTOS A ANALIZAR
═══════════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}

FACTURA:
{factura_texto}

OBSERVACIONES DEL USUARIO:
{observaciones_texto if observaciones_texto else "NO DISPONIBLES"}

ANEXOS:
{anexos_texto if anexos_texto else "NO DISPONIBLES"}

═══════════════════════════════════════════════════════════════════════
TAREAS DE EXTRACCION
═══════════════════════════════════════════════════════════════════════

1. VALORES DE FACTURA (extraer de la factura):
   - factura_con_iva: Valor total con IVA incluido
   - factura_sin_iva: Valor total sin IVA (subtotal)
   - iva: Valor del IVA



2. MENCION DE TASA PRODEPORTE (analizar SOLO las observaciones):
   - aplica_tasa_prodeporte: true, si encuentras mencion de " validar tasa prodeporte",
     "aplicar tasa prodeporte", "revisar tasa pro deporte" o similares que indiquen la aplicacion de la tasa prodeporte.
   - aplica_tasa_prodeporte: false, si no  encuentras mencion de tasa prodeporte o si encuentras " no aplicar tasa prodeporte" o similares que indiquen que NO se debe aplicar.
   - texto_mencion_tasa: Copia textualmente el fragmento donde identificaste la mencion de si aplica o no aplica .
     Debe ser el texto LITERAL de las observaciones. Si no encuentras mencion, string vacio "".

3. MUNICIPIO/DEPARTAMENTO (analizar SOLO las observaciones):
   - municipio_identificado: Nombre del municipio o departamento mencionado
   - texto_municipio: Copia textualmente el fragmento donde identificaste el municipio.
     Debe ser el texto LITERAL de las observaciones. Si no encuentras, string vacio "".

═══════════════════════════════════════════════════════════════════════
FORMATO DE RESPUESTA JSON
═══════════════════════════════════════════════════════════════════════

{{
    "factura_con_iva": 0.0,
    "factura_sin_iva": 0.0,
    "iva": 0.0,
    "aplica_tasa_prodeporte": false,
    "texto_mencion_tasa": "",
    "municipio_identificado": "",
    "texto_municipio": ""
}}

═══════════════════════════════════════════════════════════════════════
REGLAS IMPORTANTES
═══════════════════════════════════════════════════════════════════════

• Si NO encuentras un valor, ESTRICTAMENTE SOLO usa 0.0 para numeros y "" para textos
• Los textos copiados deben ser LITERALES, sin interpretacion
• NO inventes informacion que no este en los documentos
• Si un campo no aplica o no lo encuentras, dejalo vacio o en 0
• Para valores monetarios, extrae solo numeros (sin simbolos $ ni comas)
• Revisa la estructura del JSON cuidadosamente antes de responder
    """
