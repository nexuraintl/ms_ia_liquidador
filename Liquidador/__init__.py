"""
LIQUIDADOR DE RETENCIÓN Y ESTAMPILLAS
====================================

Módulo para calcular retenciones en la fuente y estampillas según normativa colombiana.
Maneja análisis con Gemini y aplica tarifas exactas.

Módulos disponibles:
- LiquidadorRetencion: Retención en la fuente
- LiquidadorEstampilla: Estampilla pro universidad nacional
"""

from .liquidador import LiquidadorRetencion
from .liquidador_estampilla import LiquidadorEstampilla

__all__ = ['LiquidadorRetencion', 'LiquidadorEstampilla']
