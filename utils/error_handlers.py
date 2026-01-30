"""
MÓDULO ERROR_HANDLERS - MANEJO DE ERRORES DE VALIDACIÓN FASTAPI

SRP: Responsabilidad única de interceptar y transformar errores de validación
OCP: Extensible para nuevos tipos de errores sin modificar código existente
DIP: Depende de abstracciones (mockups.py) no de implementaciones concretas

Autor: Sistema PRELIQUIDADOR
Versión: 3.0
"""

from datetime import datetime
from typing import Dict, List, Any
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging

# DIP: Importar función de mockups (abstracción)
from utils.mockups import crear_respuesta_error_validacion

logger = logging.getLogger(__name__)


# ============================================
# EXCEPTION HANDLER PRINCIPAL (SRP)
# ============================================

async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Exception handler para errores de validación de Pydantic en FastAPI.

    PRINCIPIOS SOLID:
    - SRP: Solo maneja RequestValidationError, delega construcción de respuesta
    - DIP: Depende de crear_respuesta_error_validacion (abstracción)
    - OCP: No requiere modificación para nuevos campos validados

    Flujo:
    1. Intercepta RequestValidationError (422)
    2. Extrae información detallada del error
    3. Delega a mockups.py la creación de estructura de respuesta
    4. Retorna 200 OK con estructura estándar del sistema

    Args:
        request: Request object de FastAPI
        exc: RequestValidationError con detalles de validación

    Returns:
        JSONResponse: 200 OK con estructura mockup estándar
    """
    # Extraer información del error de validación
    errores_detallados = extraer_informacion_errores(exc)

    # Log para debugging
    logger.warning(f"Error de validación detectado en {request.url.path}")
    logger.warning(f"Errores: {errores_detallados}")

    # DIP: Delegar construcción de respuesta a mockups.py
    respuesta_mockup = crear_respuesta_error_validacion(
        errores_validacion=errores_detallados,
        url_request=str(request.url),
        metodo_http=request.method
    )

    # Retornar 200 OK (no 422) con estructura estándar
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=respuesta_mockup
    )


# ============================================
# FUNCIONES AUXILIARES (SRP)
# ============================================

def extraer_informacion_errores(exc: RequestValidationError) -> List[Dict[str, Any]]:
    """
    Extrae información detallada de errores de validación Pydantic.

    SRP: Responsabilidad única de transformar ValidationError → estructura legible

    Args:
        exc: RequestValidationError de FastAPI

    Returns:
        List[Dict]: Lista de errores con formato estructurado

    Example:
        >>> errores = extraer_informacion_errores(exc)
        >>> errores[0]
        {
            "campo": "codigo_del_negocio",
            "tipo_error": "type_error.integer",
            "mensaje": "value is not a valid integer",
            "valor_recibido": "abc",
            "ubicacion": ["body", "codigo_del_negocio"]
        }
    """
    errores_estructurados = []

    for error in exc.errors():
        error_info = {
            "campo": ".".join(str(loc) for loc in error.get("loc", [])),
            "tipo_error": error.get("type", "unknown"),
            "mensaje": error.get("msg", "Error de validación"),
            "ubicacion": list(error.get("loc", [])),
            "input_recibido": error.get("input", None)
        }

        errores_estructurados.append(error_info)

    return errores_estructurados


def generar_mensaje_error_usuario(errores: List[Dict[str, Any]]) -> str:
    """
    Genera mensaje amigable para el usuario basado en errores de validación.

    SRP: Responsabilidad única de crear mensajes legibles para usuarios

    Args:
        errores: Lista de errores estructurados

    Returns:
        str: Mensaje amigable para el usuario

    Example:
        >>> mensaje = generar_mensaje_error_usuario(errores)
        >>> mensaje
        "Error en parámetro 'codigo_del_negocio': debe ser un número entero, recibió 'abc'"
    """
    if not errores:
        return "Error de validación en los parámetros de entrada"

    mensajes = []
    for error in errores:
        campo = error["campo"].replace("body.", "")
        tipo = error["tipo_error"]
        input_val = error.get("input_recibido", "valor inválido")

        # Mapear tipos de error a mensajes amigables
        if "integer" in tipo:
            msg = f"El parámetro '{campo}' debe ser un número entero, se recibió '{input_val}'"
        elif "string" in tipo:
            msg = f"El parámetro '{campo}' debe ser texto, se recibió '{input_val}'"
        elif "missing" in tipo:
            msg = f"Falta el parámetro obligatorio '{campo}'"
        else:
            msg = f"Error en parámetro '{campo}': {error['mensaje']}"

        mensajes.append(msg)

    return " | ".join(mensajes)


# ============================================
# FUNCIÓN DE REGISTRO (SRP)
# ============================================

def registrar_exception_handler(app) -> None:
    """
    Registra el exception handler en la aplicación FastAPI.

    SRP: Responsabilidad única de configurar el handler en la app
    DIP: Recibe app como dependencia inyectada

    Usage (en main.py):
        >>> from utils.error_handlers import registrar_exception_handler
        >>> app = FastAPI()
        >>> registrar_exception_handler(app)

    Args:
        app: Instancia de FastAPI
    """
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler
    )
    logger.info("✓ Exception handler de validación registrado correctamente")
