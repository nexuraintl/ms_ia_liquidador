"""
MODELOS MODULE - DOMAIN LAYER
==============================

Modulo de modelos de datos (Domain Layer) para el sistema de liquidacion.

PRINCIPIOS SOLID APLICADOS:
- SRP: Modulo dedicado exclusivamente a definiciones de modelos
- OCP: Modelos extensibles y reutilizables
- Domain Layer: Entidades de dominio sin logica de negocio

UBICACION EN CLEAN ARCHITECTURE:
- Domain Layer: Entities & Value Objects
- Sin dependencias de infraestructura
- Reutilizable en todos los modulos (Liquidador, Clasificador, etc.)

ORGANIZACION DE EXPORTS:
- Seccion 1: Modelos para Retencion General (3 modelos)
- Seccion 2: Modelos para Articulo 383 (9 modelos)
- Seccion 3: Modelos Agregadores (2 modelos)

Autor: Sistema Preliquidador
Version: 3.0 - Clean Architecture
"""

# ===============================
# SECCION 1: MODELOS PARA RETENCION GENERAL
# ===============================

from .modelos import (
    # Modelos de conceptos y detalles
    ConceptoIdentificado,
    DetalleConcepto,
    NaturalezaTercero,
)

# ===============================
# SECCION 2: MODELOS PARA ARTICULO 383 - DEDUCCIONES PERSONALES
# ===============================

from .modelos import (
    # Modelos de condiciones y conceptos Art 383
    ConceptoIdentificadoArt383,
    CondicionesArticulo383,

    # Modelos de deducciones especificas
    InteresesVivienda,
    DependientesEconomicos,
    MedicinaPrepagada,
    AFCInfo,
    PlanillaSeguridadSocial,

    # Modelos contenedores Art 383
    DeduccionesArticulo383,
    InformacionArticulo383,
)

# ===============================
# SECCION 3: MODELOS AGREGADORES - ENTRADA/SALIDA
# ===============================

from .modelos import (
    # Modelos principales de entrada/salida
    AnalisisFactura,
    ResultadoLiquidacion,
)

# ===============================
# EXPORTS PUBLICOS DEL MODULO
# ===============================

__all__ = [
    # Seccion 1: Retencion General
    "ConceptoIdentificado",
    "DetalleConcepto",
    "NaturalezaTercero",

    # Seccion 2: Articulo 383 - Deducciones
    "ConceptoIdentificadoArt383",
    "CondicionesArticulo383",
    "InteresesVivienda",
    "DependientesEconomicos",
    "MedicinaPrepagada",
    "AFCInfo",
    "PlanillaSeguridadSocial",
    "DeduccionesArticulo383",
    "InformacionArticulo383",

    # Seccion 3: Agregadores
    "AnalisisFactura",
    "ResultadoLiquidacion",
]

# ===============================
# METADATA DEL MODULO
# ===============================

__version__ = "3.0.0"
__author__ = "Sistema Preliquidador"
__architecture__ = "Clean Architecture - Domain Layer"
__total_modelos__ = 14

# Log de inicializacion
import logging
logger = logging.getLogger(__name__)
logger.info(f"Modulo de modelos inicializado - Version {__version__} - Total modelos: {__total_modelos__}")
