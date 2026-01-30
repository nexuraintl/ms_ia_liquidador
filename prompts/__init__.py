"""
MÓDULO DE PROMPTS
=================

Contiene todos los prompts para interacciones con Google Gemini AI.

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad única - solo definición de prompts
- OCP: Abierto para extensión - nuevos prompts sin modificar existentes
- DIP: Sin dependencias externas, funciones puras

Autor: Sistema Preliquidador
Arquitectura: SOLID + Clean Architecture
"""

# Prompts clasificador general
from .prompt_clasificador import PROMPT_CLASIFICACION

# Prompts retefuente
from .prompt_retefuente import (
    PROMPT_ANALISIS_FACTURA,
    PROMPT_ANALISIS_ART_383,
    PROMPT_EXTRACCION_CONSORCIO,
    PROMPT_MATCHING_CONCEPTOS,
    PROMPT_ANALISIS_FACTURA_EXTRANJERA
)

# Prompts ICA
from .prompt_ica import (
    crear_prompt_identificacion_ubicaciones,
    crear_prompt_relacionar_actividades,
    limpiar_json_gemini,
    validar_estructura_ubicaciones,
    validar_estructura_actividades
)

# Prompts Timbre
from .prompt_timbre import (
    PROMPT_ANALISIS_TIMBRE_OBSERVACIONES,
    PROMPT_EXTRACCION_CONTRATO_TIMBRE
)

# Prompts especializados de impuestos
from .prompt_estampilla_obra_publica import PROMPT_ANALISIS_OBRA_PUBLICA_ESTAMPILLA_INTEGRADO
from .prompt_iva import PROMPT_ANALISIS_IVA
from .prompt_estampillas_generales import PROMPT_ANALISIS_ESTAMPILLAS_GENERALES
from .prompt_tasa_prodeporte import PROMPT_ANALISIS_TASA_PRODEPORTE

__all__ = [
    # Clasificador general
    'PROMPT_CLASIFICACION',
    # Retefuente
    'PROMPT_ANALISIS_FACTURA',
    'PROMPT_ANALISIS_ART_383',
    'PROMPT_EXTRACCION_CONSORCIO',
    'PROMPT_MATCHING_CONCEPTOS',
    'PROMPT_ANALISIS_FACTURA_EXTRANJERA',
    # ICA
    'crear_prompt_identificacion_ubicaciones',
    'crear_prompt_relacionar_actividades',
    'limpiar_json_gemini',
    'validar_estructura_ubicaciones',
    'validar_estructura_actividades',
    # Timbre
    'PROMPT_ANALISIS_TIMBRE_OBSERVACIONES',
    'PROMPT_EXTRACCION_CONTRATO_TIMBRE',
    # Impuestos especializados
    'PROMPT_ANALISIS_OBRA_PUBLICA_ESTAMPILLA_INTEGRADO',
    'PROMPT_ANALISIS_IVA',
    'PROMPT_ANALISIS_ESTAMPILLAS_GENERALES',
    'PROMPT_ANALISIS_TASA_PRODEPORTE'
]
