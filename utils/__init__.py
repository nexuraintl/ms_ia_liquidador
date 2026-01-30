# Módulo utils - Utilidades del sistema PRELIQUIDADOR
# SRP: Módulo dedicado a funciones utilitarias y helpers

from .mockups import (
    crear_respuesta_negocio_no_parametrizado,
    crear_respuesta_error_validacion
)
from .error_handlers import (
    registrar_exception_handler,
    validation_exception_handler,
    extraer_informacion_errores
)
from .utils_archivos import (obtener_nombre_archivo,
                             procesar_archivos_para_gemini)

__all__ = [
    'crear_respuesta_negocio_no_parametrizado',
    'crear_respuesta_error_validacion',
    'registrar_exception_handler',
    'validation_exception_handler',
    'extraer_informacion_errores',
    'obtener_nombre_archivo',
    'procesar_archivos_para_gemini'
    ]
