"""
CLASIFICADOR DE DOCUMENTOS
========================

Módulo para clasificar documentos fiscales usando Google Gemini AI.
Maneja la primera llamada a Gemini para categorizar documentos.

ARQUITECTURA SOLID v3.1:
- ProcesadorGemini: Clasificador general y funciones compartidas
- ClasificadorRetefuente: Clasificador especializado en retención en la fuente (SRP)
"""

from .clasificador import ProcesadorGemini
from .clasificador_retefuente import ClasificadorRetefuente
from prompts.prompt_clasificador import PROMPT_CLASIFICACION
from prompts.prompt_retefuente import PROMPT_ANALISIS_FACTURA
from .clasificador_tp import ClasificadorTasaProdeporte
from .clasificador_estampillas_g import ClasificadorEstampillasGenerales
from .clasificador_iva import ClasificadorIva
from  .clasificador_obra_uni import ClasificadorObraUni
from .gemini_files_manager import GeminiFilesManager, FileUploadResult

__all__ = [
    'ProcesadorGemini',
    'ClasificadorRetefuente',
    'PROMPT_CLASIFICACION',
    'PROMPT_ANALISIS_FACTURA',
    'ProcesadorConsorcios',
    'ClasificadorTasaProdeporte',
    'ClasificadorEstampillasGenerales',
    'ClasificadorIva',
    'ClasificadorObraUni',
    'GeminiFilesManager',
    'FileUploadResult'
]
