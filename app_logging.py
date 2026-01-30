"""
CONFIGURACION DE LOGGING - INFRASTRUCTURE LAYER
================================================

Modulo de infraestructura para configurar el sistema de logging de la aplicacion.

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad unica de configurar logging del sistema
- Infrastructure Layer: Configuracion de preocupaciones transversales

UBICACION EN CLEAN ARCHITECTURE:
- Infrastructure Layer: Frameworks & Drivers
- No contiene logica de negocio
- Configuracion pura de sistema

Autor: Sistema Preliquidador
Version: 3.0 - Clean Architecture
"""

import logging
import sys
from typing import Optional


def configurar_logging(nivel: str = "INFO") -> None:
    """
    Configura el logging profesional para la aplicacion.

    CARACTERISTICAS:
    - Elimina handlers existentes para evitar duplicacion
    - Establece un formato claro con timestamp
    - Envia logs a la consola (stdout)
    - Configura nivel de logging configurable

    PRINCIPIOS SOLID:
    - SRP: Solo configura logging, no hace nada mas
    - OCP: Extensible mediante parametro de nivel

    Args:
        nivel: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                Default: "INFO"

    Returns:
        None

    Example:
        >>> configurar_logging()  # Usa INFO por defecto
        >>> configurar_logging("DEBUG")  # Modo debug
    """
    # Evitar duplicacion de logs por el reloader de uvicorn
    if logging.getLogger().hasHandlers():
        logging.getLogger().handlers.clear()
        print(" Logging CORREGIDO - Handlers duplicados eliminados")

    # Configurar el formato del log
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Configurar un handler para la consola
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    # Configurar el logger raiz
    root_logger = logging.getLogger()

    # Mapear nivel de string a constante de logging
    nivel_logging = getattr(logging, nivel.upper(), logging.INFO)
    root_logger.setLevel(nivel_logging)
    root_logger.addHandler(stream_handler)

    # Log inicial de confirmacion
    logger = logging.getLogger(__name__)
    logger.info(f"Sistema de logging configurado - Nivel: {nivel.upper()}")


def obtener_logger(nombre: str) -> logging.Logger:
    """
    Funcion de utilidad para obtener un logger configurado.

    PRINCIPIO SRP: Solo retorna un logger, no configura.

    Args:
        nombre: Nombre del logger (generalmente __name__ del modulo)

    Returns:
        Logger configurado

    Example:
        >>> logger = obtener_logger(__name__)
        >>> logger.info("Mensaje de log")
    """
    return logging.getLogger(nombre)


# Metadata del modulo
__version__ = "3.0.0"
__architecture__ = "Clean Architecture - Infrastructure Layer"
