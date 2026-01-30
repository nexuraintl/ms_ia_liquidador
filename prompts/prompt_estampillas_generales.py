"""
PROMPT PARA ANALISIS DE ESTAMPILLAS GENERALES
==============================================

Prompt especializado para identificación de 6 estampillas generales:
- Procultura
- Bienestar
- Adulto Mayor
- Prouniversidad Pedagógica
- Francisco José de Caldas
- Prodeporte

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo prompts de estampillas generales
- OCP: Abierto para extensión
- DIP: Funciones puras

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

from typing import List

# Import de función auxiliar compartida
from .prompt_clasificador import _generar_seccion_archivos_directos


def PROMPT_ANALISIS_ESTAMPILLAS_GENERALES(factura_texto: str, rut_texto: str, anexos_texto: str,
                                             cotizaciones_texto: str, anexo_contrato: str, nombres_archivos_directos: list[str] = None) -> str:
    """
     NUEVO PROMPT: Análisis de 6 Estampillas Generales

    Analiza documentos para identificar información de estampillas:
    - Procultura
    - Bienestar
    - Adulto Mayor
    - Prouniversidad Pedagógica
    - Francisco José de Caldas
    - Prodeporte

    Estas estampillas aplican para TODOS los NITs administrativos.
    Solo identifica información sin realizar cálculos.

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

    return f"""
Eres un experto contador colombiano especializado en ESTAMPILLAS GENERALES que trabaja para la FIDUCIARIA FIDUCOLDEX.
Tu tarea es identificar información sobre 6 estampillas específicas en los documentos adjuntos.

 ESTAMPILLAS A IDENTIFICAR:
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
1.  **PROCULTURA** - Estampilla Pro Cultura
2.  **BIENESTAR** - Estampilla Pro Bienestar
3.  **ADULTO MAYOR** - Estampilla Pro Adulto Mayor
4.  **PROUNIVERSIDAD PEDAGÓGICA** - Estampilla Pro Universidad Pedagógica
5.  **FRANCISCO JOSÉ DE CALDAS** - Estampilla Francisco José de Caldas
6.  **PRODEPORTE** - Estampilla Pro Deporte

 ESTRATEGIA DE ANÁLISIS SECUENCIAL:
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

 **ANÁLISIS ACUMULATIVO** - Revisar TODOS los documentos en este orden:
1.  **FACTURA PRINCIPAL** - Buscar desglose de estampillas
2.  **ANEXOS** - Información adicional sobre estampillas
3.  **ANEXO CONTRATO** - Referencias a estampillas aplicables
4.  **RUT** - Validación del tercero

 **IMPORTANTE**: Revisar TODOS los documentos y consolidar información encontrada

DOCUMENTOS DISPONIBLES:
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

{_generar_seccion_archivos_directos(nombres_archivos_directos)}


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
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

1.  **IDENTIFICACIÓN DE ESTAMPILLAS**:
   • Busca menciones EXACTAS de los nombres de las estampillas
   • Identifica variaciones comunes:
   
     - "Estampilla Pro Cultura" / "Estampilla ProCultura"/ ESTAMPILLA PROCULTURA
     
     - "Estampilla Pro Bienestar" /  "Estampilla Bienestar"
     
     - "Estampilla Adulto Mayor" / "Pro Adulto Mayor" / "Estampilla Adulto Mayor / Estampilla para el Bienestar Adulto Mayor"
     
     - "Estampilla Pro Universidad Pedagógica"
     
     -  "Estampilla FJDC" / Estampilla Francisco José de Caldas
     
     - "Estampilla Pro Deporte" /  "Estampilla ProDeporte"
     
    • ESTAMPILLA BIENESTAR ES DIFERENTE A ESTAMPILLA PARA EL BIENESTAR DEL ADULTO MAYOR

2.  **EXTRACCIÓN DE INFORMACIÓN**:
   Para cada estampilla, extrae SOLO LOS VALORES ENCONTRADOS:
   • **Porcentaje** (ej: 1.5, 2.0, 0.5, 1.1) → Si NO encuentras, usar 0
   • **Valor a deducir** en pesos colombianos → Si NO encuentras, usar 0
   • **valor_base** (base gravable de la estampilla en pesos colombianos) → Si NO encuentras, usar 0
   • **Texto de referencia** donde se encontró la información → null si no hay
   • **observaciones** → null (el sistema asignará observaciones después)

3.  **CONSOLIDACIÓN ACUMULATIVA**:
   • Si FACTURA tiene info de 3 estampillas Y ANEXOS tienen info de 2 adicionales
   • RESULTADO: Mostrar las 6 estampillas consolidadas
   • Si hay duplicados, priorizar información más detallada y completa

4.  **MANEJO DE VALORES NO ENCONTRADOS**:
   • Si NO encuentras porcentaje → porcentaje: 0
   • Si NO encuentras valor → valor: 0
   • Si NO encuentras valor_base → valor_base: 0
   • Si NO encuentras texto_referencia → texto_referencia: null
   • SIEMPRE usa observaciones: null (el sistema asignará observaciones después)

EJEMPLOS DE IDENTIFICACIÓN:
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

 **EJEMPLO 1 - INFORMACIÓN COMPLETA ENCONTRADA**:
Factura: "Estampilla Pro Cultura 1.5% = $150,000 sobre base de $10,000,000"
Resultado: {{
  "nombre_estampilla": "Procultura",
  "porcentaje": 1.5,
  "valor_base": 10000000,
  "valor": 150000,
  "texto_referencia": "Factura línea 15: Estampilla Pro Cultura 1.5% = $150,000",
  "observaciones": null
}}

 **EJEMPLO 2 - INFORMACIÓN PARCIAL**:
Anexo: "Aplica estampilla Pro Bienestar al 2%"
Resultado: {{
  "nombre_estampilla": "Bienestar",
  "porcentaje": 2.0,
  "valor_base": 0,
  "valor": 0,
  "texto_referencia": "Anexo página 2: Aplica estampilla Pro Bienestar al 2%",
  "observaciones": null
}}

 **EJEMPLO 3 - NO IDENTIFICADA**:
Sin información en documentos
Resultado: {{
  "nombre_estampilla": "Prodeporte",
  "porcentaje": 0,
  "valor_base": 0,
  "valor": 0,
  "texto_referencia": null,
  "observaciones": null
}}

IMPORTANTE:
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
• NO realizar cálculos, solo identificar información que aparece en los documentos
• Si una estampilla se menciona múltiples veces, consolidar la información más completa
• Priorizar información de FACTURA, luego ANEXOS, luego ANEXO CONTRATO
• Si no encuentras información de alguna estampilla, usar 0 para valores numéricos
• SIEMPRE devolver las 6 estampillas aunque no tengan información
• NO CONFUNDAS ESTAMPILLA BIENESTAR CON ESTAMPILLA PRO BIENESTAR DEL ADULTO MAYOR

RESPONDE ÚNICAMENTE EN FORMATO JSON VÁLIDO SIN TEXTO ADICIONAL:
{{
    "estampillas_generales": [
        {{
            "nombre_estampilla": "Procultura",
            "porcentaje": 1.5,
            "valor_base": 10000000,
            "valor": 150000,
            "texto_referencia": "Factura línea 15: Estampilla Pro Cultura 1.5% = $150,000",
            "observaciones": null
        }},
        {{
            "nombre_estampilla": "Bienestar",
            "porcentaje": 2.0,
            "valor_base": 0,
            "valor": 0,
            "texto_referencia": "Anexo página 2: Aplica estampilla Pro Bienestar 2%",
            "observaciones": null
        }},
        {{
            "nombre_estampilla": "Adulto Mayor",
            "porcentaje": 0,
            "valor_base": 0,
            "valor": 0,
            "texto_referencia": null,
            "observaciones": null
        }},
        {{
            "nombre_estampilla": "Prouniversidad Pedagógica",
            "porcentaje": 0,
            "valor_base": 0,
            "valor": 0,
            "texto_referencia": null,
            "observaciones": null
        }},
        {{
            "nombre_estampilla": "Francisco José de Caldas",
            "porcentaje": 0,
            "valor_base": 0,
            "valor": 0,
            "texto_referencia": null,
            "observaciones": null
        }},
        {{
            "nombre_estampilla": "Prodeporte",
            "porcentaje": 0,
            "valor_base": 0,
            "valor": 0,
            "texto_referencia": null,
            "observaciones": null
        }}
    ]
}}

 **CRÍTICO - CONDICIONES EXACTAS**:
• SIEMPRE incluir las 6 estampillas en el resultado (aunque no tengan información)
• Usar 0 (cero) para valores numéricos no encontrados (porcentaje, valor_base, valor)
• Usar null solo para texto_referencia y observaciones cuando no haya información
• Consolidar información de TODOS los documentos de forma acumulativa
• Especificar claramente dónde se encontró cada información
• NO INVENTAR VALORES, SOLO UTILIZAR LA INFORMACIÓN PRESENTE EN LOS DOCUMENTOS
• Tu trabajo es SOLO extraer datos, NO validar ni asignar estados
• ESTA TOTALMENTE PROHIVIDO INVENTAR INFORMACIÓN QUE NO ESTÉ PRESENTE EN LOS DOCUMENTOS, SI NO RECIBES LA INFORMACIÓN, DEBES ASIGNAR LOS VALORES POR DEFECTO INDICADOS ANTERIORMENTE
    """
