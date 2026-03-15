"""
DATABASE MODULE - CLEAN ARCHITECTURE
====================================

Módulo de base de datos implementando principios SOLID y Clean Architecture.

ARQUITECTURA EN CAPAS:
- Data Access Layer: database.py (Strategy Pattern)
- Business Logic Layer: database_service.py (Service Pattern)

PRINCIPIOS SOLID APLICADOS:
- SRP: Cada clase tiene una responsabilidad específica
- OCP: Abierto para extensión, cerrado para modificación
- LSP: Las implementaciones pueden sustituirse sin alterar funcionalidad
- ISP: Interfaces específicas para cada responsabilidad
- DIP: Dependencias hacia abstracciones, no hacia concreciones

PATRONES DE DISEÑO:
- Strategy Pattern: Para diferentes implementaciones de base de datos
- Service Pattern: Para lógica de negocio de datos
- Factory Pattern: Para creación de servicios
- Dependency Injection: Para inversión de dependencias

Autor: Sistema Preliquidador
Versión: 3.0 - SOLID Architecture
"""

# ===============================
# DATA ACCESS LAYER EXPORTS
# ===============================

from .database import (
    # Interfaces y abstracciones
    DatabaseInterface,

    # Implementaciones concretas
    SupabaseDatabase,
    NexuraAPIDatabase,
    DatabaseWithFallback,

    # Context manager (Strategy Pattern)
    DatabaseManager,

    # Funciones de utilidad
    ejecutar_pruebas_completas
)

# ===============================
# BUSINESS LOGIC LAYER EXPORTS
# ===============================

from .database_service import (
    # Interfaces de servicios
    IBusinessDataService,

    # Implementación de servicios
    BusinessDataService,

    # Factory para creación
    BusinessDataServiceFactory,

    # Funciones de conveniencia
    crear_business_service,

    # Mock para testing
    MockBusinessDataService
)

# ===============================
# INFRASTRUCTURE SETUP EXPORTS
# ===============================

from .setup import (
    # Inicialización de infraestructura
    inicializar_database_manager,

    # Obtener UVT desde API externa
    obtener_uvt_desde_api,

    # Verificación de conexión
    verificar_conexion_database
)

# ===============================
# MODULE METADATA
# ===============================

__version__ = "3.0.0"
__author__ = "Sistema Preliquidador"
__architecture__ = "SOLID + Clean Architecture"

# Lista de componentes principales exportados
__all__ = [
    # Data Access Layer
    "DatabaseInterface",
    "SupabaseDatabase",
    "NexuraAPIDatabase",
    "DatabaseWithFallback",
    "DatabaseManager",
    "ejecutar_pruebas_completas",

    # Business Logic Layer
    "IBusinessDataService",
    "BusinessDataService",
    "BusinessDataServiceFactory",
    "crear_business_service",
    "MockBusinessDataService",

    # Infrastructure Setup
    "inicializar_database_manager",
    "obtener_uvt_desde_api",
    "verificar_conexion_database",
]

# ===============================
# FACTORY FUNCTIONS FOR EASY USAGE
# ===============================

def crear_database_stack_completo(supabase_url: str = None, supabase_key: str = None):
    """
    Factory function para crear stack completo de base de datos.

    PRINCIPIOS APLICADOS:
    - Factory Pattern: Simplifica creación de objetos complejos
    - DIP: Permite inyección de credenciales

    Args:
        supabase_url: URL de Supabase (opcional, usa env var si no se proporciona)
        supabase_key: Key de Supabase (opcional, usa env var si no se proporciona)

    Returns:
        tuple: (database_manager, business_service)
    """
    import os

    # Usar parámetros o variables de entorno
    url = supabase_url or os.getenv("SUPABASE_URL")
    key = supabase_key or os.getenv("SUPABASE_KEY")

    if not url or not key:
        # Crear solo business service sin database (graceful degradation)
        business_service = crear_business_service(None)
        return None, business_service

    # Crear stack completo
    supabase_db = SupabaseDatabase(url, key)
    database_manager = DatabaseManager(supabase_db)
    business_service = crear_business_service(database_manager)

    return database_manager, business_service


# ===============================
# MODULE INITIALIZATION LOG
# ===============================

import logging
logger = logging.getLogger(__name__)
logger.info(f"📦 Database module inicializado - Versión {__version__} - Arquitectura: {__architecture__}")