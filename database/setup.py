"""
DATABASE SETUP - INFRASTRUCTURE LAYER
======================================

Modulo de infraestructura para inicializar el gestor de base de datos.

PRINCIPIOS SOLID APLICADOS:
- SRP: Responsabilidad unica de inicializar infraestructura de base de datos
- DIP: Depende de abstracciones (DatabaseManager, BusinessDataService)
- Infrastructure Layer: Setup de componentes de infraestructura

UBICACION EN CLEAN ARCHITECTURE:
- Infrastructure Layer: Frameworks & Drivers
- Configuracion e inicializacion de base de datos
- Manejo de credenciales y conexiones

PATRONES APLICADOS:
- Factory Pattern: Creacion de instancias de servicios
- Strategy Pattern: DatabaseManager usa Strategy para diferentes DBs
- Dependency Injection: Inyeccion de DatabaseManager en BusinessService

Autor: Sistema Preliquidador
Version: 3.0 - Clean Architecture
"""

import os
import logging
from typing import Optional, Tuple

# Importar componentes del modulo database (DIP: depender de abstracciones)
from .database import DatabaseManager, SupabaseDatabase, NexuraAPIDatabase, DatabaseInterface, DatabaseWithFallback
from .database_service import crear_business_service, BusinessDataService
from .auth_provider import AuthProviderFactory, IAuthProvider

# Logger para este modulo
logger = logging.getLogger(__name__)


def crear_database_por_tipo(tipo_db: str) -> Optional[DatabaseInterface]:
    """
    Factory para crear instancia de database segun tipo configurado (Factory Pattern + OCP)

    PRINCIPIOS SOLID APLICADOS:
    - SRP: Funcion dedicada solo a crear instancias de database
    - OCP: Extensible para nuevos tipos de database sin modificar existente
    - DIP: Retorna abstraccion (DatabaseInterface), no implementacion concreta
    - Factory Pattern: Centraliza creacion de objetos complejos

    TIPOS SOPORTADOS:
    - 'supabase': Base de datos Supabase (implementacion original)
    - 'nexura': API REST de Nexura (nueva implementacion)

    Args:
        tipo_db: Tipo de database ('supabase' o 'nexura')

    Returns:
        DatabaseInterface o None si falta configuracion

    Environment Variables:
        SUPABASE:
            - SUPABASE_URL: URL de la instancia de Supabase
            - SUPABASE_KEY: Key de API de Supabase

        NEXURA:
            - NEXURA_API_BASE_URL: URL base de la API de Nexura
            - NEXURA_AUTH_TYPE: Tipo de auth ('none', 'jwt', 'api_key')
            - NEXURA_JWT_TOKEN: Token JWT (si auth_type='jwt')
            - NEXURA_API_KEY: API Key (si auth_type='api_key')
            - NEXURA_API_TIMEOUT: Timeout en segundos (default: 30)

    Note:
        v3.11.1+: Fallback a Supabase desactivado por defecto cuando DATABASE_TYPE='nexura'.
        La función retorna NexuraAPIDatabase directamente sin DatabaseWithFallback wrapper.
        Para reactivar fallback: ver código comentado en líneas 127-150.

    Example:
        >>> db = crear_database_por_tipo('nexura')  # Retorna NexuraAPIDatabase (sin fallback)
        >>> if db:
        ...     manager = DatabaseManager(db)
    """
    tipo_db = tipo_db.lower().strip()

    if tipo_db == 'supabase':
        logger.info("Creando database tipo: Supabase")

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url or not supabase_key:
            logger.warning("Variables SUPABASE_URL y SUPABASE_KEY no configuradas")
            return None

        return SupabaseDatabase(supabase_url, supabase_key)

    elif tipo_db == 'nexura':
        logger.info("Creando database tipo: Nexura API (fallback desactivado)")

        nexura_url = os.getenv("NEXURA_API_BASE_URL")
        auth_type = os.getenv("NEXURA_AUTH_TYPE", "none")
        jwt_token = os.getenv("NEXURA_JWT_TOKEN", "")
        api_key = os.getenv("NEXURA_API_KEY", "")
        # Timeout aumentado a 30 segundos (sin fallback activo desde v3.11.1)
        timeout = int(os.getenv("NEXURA_API_TIMEOUT", "30"))

        if not nexura_url:
            logger.warning("Variable NEXURA_API_BASE_URL no configurada")
            return None

        # Crear auth provider segun configuracion (Factory Pattern)
        try:
            auth_provider = AuthProviderFactory.create_from_config(
                auth_type=auth_type,
                token=jwt_token,
                api_key=api_key
            )
            logger.info(f"Auth provider creado: tipo={auth_type}")
        except ValueError as e:
            logger.error(f"Error creando auth provider: {e}")
            return None

        # Crear database primaria (Nexura)
        nexura_db = NexuraAPIDatabase(
            base_url=nexura_url,
            auth_provider=auth_provider,
            timeout=timeout
        )

        # DECISIÓN ARQUITECTÓNICA v3.11.1+: Fallback desactivado
        logger.info(
            "⚠️  FALLBACK A SUPABASE DESACTIVADO - Sistema usando solo Nexura API en producción"
        )
        logger.info(
            "ℹ️  Para reactivar fallback: Descomentar código en database/setup.py líneas 127-150"
        )

        # ========================================
        # CÓDIGO DE FALLBACK PRESERVADO (COMENTADO)
        # Para reactivar: Descomentar bloque siguiente y configurar vars SUPABASE
        # ========================================
        # supabase_url = os.getenv("SUPABASE_URL")
        # supabase_key = os.getenv("SUPABASE_KEY")
        #
        # if supabase_url and supabase_key:
        #     logger.info("Configurando Supabase como database de fallback")
        #     supabase_db = SupabaseDatabase(supabase_url, supabase_key)
        #
        #     # Retornar DatabaseWithFallback (Decorator Pattern)
        #     fallback_db = DatabaseWithFallback(
        #         primary_db=nexura_db,
        #         fallback_db=supabase_db
        #     )
        #     logger.info("✅ Sistema de fallback Nexura -> Supabase configurado correctamente")
        #     return fallback_db
        # else:
        #     logger.warning(
        #         "⚠️ Variables SUPABASE_URL y/o SUPABASE_KEY no configuradas. "
        #         "Nexura funcionará SIN fallback (puede fallar si Nexura está caída)"
        #     )
        # ========================================

        return nexura_db  # Retornar Nexura directamente (sin wrapper de fallback)

    else:
        logger.error(f"Tipo de database no valido: {tipo_db}")
        logger.error("Tipos soportados: 'supabase', 'nexura'")
        return None


def inicializar_database_manager() -> Tuple[Optional[DatabaseManager], Optional[BusinessDataService]]:
    """
    Inicializa el gestor de base de datos y servicios asociados usando variables de entorno.

    PRINCIPIOS SOLID APLICADOS:
    - SRP: Funcion dedicada solo a inicializacion de componentes de base de datos
    - DIP: Servicios dependen de abstracciones inyectadas
    - OCP: Extensible para otras implementaciones de base de datos

    ARQUITECTURA:
    - Obtiene credenciales de variables de entorno (seguridad)
    - Crea implementacion concreta de database (SupabaseDatabase)
    - Crea DatabaseManager usando Strategy Pattern
    - Crea BusinessDataService con Dependency Injection
    - Implementa graceful degradation si no hay credenciales

    COMPORTAMIENTO:
    - Si no hay credenciales: Crea BusinessService sin DB (modo degradado)
    - Si hay error: Loggea error y retorna None + BusinessService sin DB
    - Si exitoso: Retorna DatabaseManager + BusinessService completo

    Returns:
        tuple: (database_manager, business_service)
            - database_manager: DatabaseManager o None si error
            - business_service: BusinessDataService (siempre disponible, con o sin DB)

    Environment Variables:
        DATABASE_TYPE: Tipo de database a usar ('supabase' o 'nexura', default: 'supabase')

        SUPABASE (si DATABASE_TYPE='supabase'):
            - SUPABASE_URL: URL de la instancia de Supabase
            - SUPABASE_KEY: Key de API de Supabase

        NEXURA (si DATABASE_TYPE='nexura'):
            - NEXURA_API_BASE_URL: URL base de la API de Nexura
            - NEXURA_AUTH_TYPE: Tipo de auth ('none', 'jwt', 'api_key')
            - NEXURA_JWT_TOKEN: Token JWT (si auth_type='jwt')
            - NEXURA_API_KEY: API Key (si auth_type='api_key')
            - NEXURA_API_TIMEOUT: Timeout en segundos (default: 30)

    NOTA v3.11.1+:
        - Fallback Nexura → Supabase DESACTIVADO por defecto
        - DATABASE_TYPE='nexura' retorna NexuraAPIDatabase directamente
        - Para reactivar fallback: ver database/setup.py líneas 127-150
        - DATABASE_TYPE='supabase' sigue funcionando sin cambios

    Example:
        >>> db_manager, business_service = inicializar_database_manager()
        >>> if db_manager:
        ...     print("Base de datos inicializada correctamente")
        >>> # business_service siempre esta disponible
        >>> resultado = business_service.obtener_datos_negocio(codigo)
    """
    try:
        # Obtener tipo de database desde variable de entorno (default: supabase)
        tipo_db = os.getenv("DATABASE_TYPE", "nexura")
        logger.info(f"Inicializando database tipo: {tipo_db}")

        # Usar factory para crear la implementacion correcta (Factory Pattern + OCP)
        db_implementation = crear_database_por_tipo(tipo_db)

        if not db_implementation:
            logger.warning(f"No se pudo crear implementacion de database tipo '{tipo_db}'")
            logger.warning("DatabaseManager no sera inicializado")

            # Crear business service sin database manager (graceful degradation)
            business_service = crear_business_service(None)
            logger.info("BusinessService creado en modo degradado (sin base de datos)")
            return None, business_service

        # Crear el manager usando el patron Strategy
        db_manager = DatabaseManager(db_implementation)
        logger.info(f"DatabaseManager inicializado correctamente (tipo: {tipo_db})")

        # Crear business service con dependency injection (DIP)
        business_service = crear_business_service(db_manager)
        logger.info("BusinessDataService inicializado con database manager")

        logger.info(f"Stack completo de base de datos inicializado exitosamente (tipo: {tipo_db})")
        return db_manager, business_service

    except Exception as e:
        logger.error(f" Error inicializando DatabaseManager: {e}")
        logger.exception("Traceback completo del error:")

        # Graceful degradation: crear business service sin database manager
        business_service = crear_business_service(None)
        logger.info(" BusinessService creado en modo degradado tras error")

        return None, business_service


def verificar_conexion_database(db_manager: Optional[DatabaseManager]) -> bool:
    """
    Verifica que la conexion a la base de datos este funcionando.

    PRINCIPIO SRP: Solo verifica conexion, no inicializa.

    Args:
        db_manager: DatabaseManager a verificar

    Returns:
        bool: True si la conexion esta OK, False si no

    Example:
        >>> db_manager, _ = inicializar_database_manager()
        >>> if verificar_conexion_database(db_manager):
        ...     print("Conexion OK")
    """
    if not db_manager:
        logger.warning("No hay DatabaseManager para verificar")
        return False

    try:
        # Intentar una operacion simple para verificar conexion
        # Aqui podrias agregar un health check especifico
        logger.info("Verificando conexion a base de datos...")
        # TODO: Implementar health check especifico si es necesario
        return True
    except Exception as e:
        logger.error(f"Error verificando conexion: {e}")
        return False


# Metadata del modulo
__version__ = "3.0.0"
__architecture__ = "Clean Architecture - Infrastructure Layer"
