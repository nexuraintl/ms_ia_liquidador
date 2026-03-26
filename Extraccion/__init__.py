"""
EXTRACCIÓN DE DOCUMENTOS
=======================

Módulo para extraer texto de diferentes tipos de archivos.
Maneja PDFs, imágenes (OCR), Excel, Word y otros formatos.
"""

from .extractor import ProcesadorArchivos, preprocesar_excel_limpio
from .extractor_adjuntos import ExtractorAdjuntos, AdjuntoExtraido
from .extractor_zip import ExtractorZip

__all__ = ['ProcesadorArchivos', 'preprocesar_excel_limpio', 'ExtractorAdjuntos', 'AdjuntoExtraido', 'ExtractorZip']
