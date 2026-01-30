"""
Sistema de Autenticacion para APIs Externas

Implementa Strategy Pattern para diferentes metodos de autenticacion,
permitiendo extensibilidad sin modificar codigo existente (OCP).

Principios SOLID aplicados:
- SRP: Cada provider tiene una sola responsabilidad (tipo de auth)
- OCP: Abierto para extension (nuevos providers), cerrado para modificacion
- LSP: Todos los providers pueden sustituir a IAuthProvider
- ISP: Interface especifica para autenticacion
- DIP: Clases dependen de IAuthProvider (abstraccion)
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class IAuthProvider(ABC):
    """
    Interface para proveedores de autenticacion (ISP + DIP)

    Define contrato que deben cumplir todas las implementaciones
    de autenticacion, permitiendo inyeccion de dependencias.
    """

    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """
        Obtiene headers HTTP necesarios para autenticacion

        Returns:
            Dict con headers (ej: {'Authorization': 'Bearer token'})
        """
        pass

    @abstractmethod
    def is_authenticated(self) -> bool:
        """
        Verifica si el provider tiene credenciales validas

        Returns:
            True si esta autenticado, False en caso contrario
        """
        pass

    @abstractmethod
    def refresh_if_needed(self) -> bool:
        """
        Refresca credenciales si es necesario

        Returns:
            True si se refresco exitosamente o no era necesario
            False si fallo el refresh
        """
        pass


class NoAuthProvider(IAuthProvider):
    """
    Provider sin autenticacion (SRP)

    Usado cuando la API no requiere autenticacion.
    Implementa Null Object Pattern para evitar None checks.
    """

    def get_headers(self) -> Dict[str, str]:
        """
        Retorna headers vacios (sin autenticacion)

        Returns:
            Diccionario vacio
        """
        return {}

    def is_authenticated(self) -> bool:
        """
        Siempre retorna True (no requiere auth)

        Returns:
            True
        """
        return True

    def refresh_if_needed(self) -> bool:
        """
        No necesita refresh (no hay credenciales)

        Returns:
            True
        """
        return True


class JWTAuthProvider(IAuthProvider):
    """
    Provider con autenticacion JWT (SRP)

    Maneja tokens JWT con refresh automatico opcional.
    Preparado para tokens dinamicos y expiracion.
    """

    def __init__(
        self,
        token: str,
        token_type: str = "Bearer",
        auto_refresh: bool = False,
        refresh_callback: Optional[callable] = None,
        expiration_time: Optional[datetime] = None
    ):
        """
        Inicializa provider JWT

        Args:
            token: Token JWT
            token_type: Tipo de token (default: "Bearer")
            auto_refresh: Si debe refrescar automaticamente
            refresh_callback: Funcion para refrescar token
            expiration_time: Tiempo de expiracion del token
        """
        self._token = token
        self._token_type = token_type
        self._auto_refresh = auto_refresh
        self._refresh_callback = refresh_callback
        self._expiration_time = expiration_time
        self._last_refresh = datetime.now()

        logger.info(f"JWTAuthProvider inicializado (auto_refresh={auto_refresh})")

    def get_headers(self) -> Dict[str, str]:
        """
        Obtiene headers con token JWT

        Returns:
            Dict con Authorization header
        """
        if self._auto_refresh:
            self.refresh_if_needed()

        return {
            "Authorization": f"{self._token_type} {self._token}"
        }

    def is_authenticated(self) -> bool:
        """
        Verifica si tiene token valido

        Returns:
            True si tiene token, False si esta vacio
        """
        if not self._token or self._token.strip() == "":
            return False

        # Verificar expiracion si esta configurada
        if self._expiration_time:
            return datetime.now() < self._expiration_time

        return True

    def refresh_if_needed(self) -> bool:
        """
        Refresca token si es necesario

        Returns:
            True si se refresco o no era necesario
            False si fallo el refresh
        """
        # Si no hay callback de refresh, no hacer nada
        if not self._refresh_callback:
            return True

        # Verificar si necesita refresh (ejemplo: 5 minutos antes de expirar)
        if self._expiration_time:
            time_until_expiration = self._expiration_time - datetime.now()
            if time_until_expiration < timedelta(minutes=5):
                return self._attempt_refresh()

        return True

    def _attempt_refresh(self) -> bool:
        """
        Intenta refrescar el token

        Returns:
            True si se refresco exitosamente, False en caso contrario
        """
        try:
            if self._refresh_callback:
                new_token, new_expiration = self._refresh_callback()
                self._token = new_token
                self._expiration_time = new_expiration
                self._last_refresh = datetime.now()
                logger.info("Token JWT refrescado exitosamente")
                return True
        except Exception as e:
            logger.error(f"Error al refrescar token JWT: {e}")
            return False

        return False

    def update_token(self, new_token: str, expiration_time: Optional[datetime] = None):
        """
        Actualiza el token manualmente

        Args:
            new_token: Nuevo token JWT
            expiration_time: Nueva fecha de expiracion
        """
        self._token = new_token
        self._expiration_time = expiration_time
        self._last_refresh = datetime.now()
        logger.info("Token JWT actualizado manualmente")


class APIKeyAuthProvider(IAuthProvider):
    """
    Provider con autenticacion por API Key (SRP)

    Usado para APIs que requieren API key en headers.
    """

    def __init__(self, api_key: str, header_name: str = "X-API-Key"):
        """
        Inicializa provider de API Key

        Args:
            api_key: Clave de API
            header_name: Nombre del header (default: "X-API-Key")
        """
        self._api_key = api_key
        self._header_name = header_name

        logger.info(f"APIKeyAuthProvider inicializado (header={header_name})")

    def get_headers(self) -> Dict[str, str]:
        """
        Obtiene headers con API key

        Returns:
            Dict con header de API key
        """
        return {
            self._header_name: self._api_key
        }

    def is_authenticated(self) -> bool:
        """
        Verifica si tiene API key valida

        Returns:
            True si tiene API key, False si esta vacia
        """
        return bool(self._api_key and self._api_key.strip() != "")

    def refresh_if_needed(self) -> bool:
        """
        API keys normalmente no necesitan refresh

        Returns:
            True
        """
        return True


class AuthProviderFactory:
    """
    Factory para crear proveedores de autenticacion (Factory Pattern + SRP)

    Centraliza la creacion de providers segun configuracion,
    facilitando mantenimiento y testing.
    """

    @staticmethod
    def create_from_config(
        auth_type: str,
        token: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> IAuthProvider:
        """
        Crea provider segun tipo de autenticacion

        Args:
            auth_type: Tipo de auth ('none', 'jwt', 'api_key')
            token: Token JWT (requerido si auth_type='jwt')
            api_key: API Key (requerida si auth_type='api_key')
            **kwargs: Argumentos adicionales para el provider

        Returns:
            Instancia de IAuthProvider

        Raises:
            ValueError: Si auth_type no es valido o faltan parametros
        """
        auth_type = auth_type.lower().strip()

        if auth_type == "none":
            logger.info("Creando NoAuthProvider")
            return NoAuthProvider()

        elif auth_type == "jwt":
            if not token or token.strip() == "":
                logger.warning("Token JWT vacio, usando NoAuthProvider")
                return NoAuthProvider()

            logger.info("Creando JWTAuthProvider")
            return JWTAuthProvider(
                token=token,
                token_type=kwargs.get("token_type", "Bearer"),
                auto_refresh=kwargs.get("auto_refresh", False),
                refresh_callback=kwargs.get("refresh_callback"),
                expiration_time=kwargs.get("expiration_time")
            )

        elif auth_type == "api_key":
            if not api_key or api_key.strip() == "":
                logger.warning("API Key vacia, usando NoAuthProvider")
                return NoAuthProvider()

            logger.info("Creando APIKeyAuthProvider")
            return APIKeyAuthProvider(
                api_key=api_key,
                header_name=kwargs.get("header_name", "X-API-Key")
            )

        else:
            logger.error(f"Tipo de autenticacion no valido: {auth_type}")
            raise ValueError(
                f"Tipo de autenticacion '{auth_type}' no valido. "
                f"Usar: 'none', 'jwt', o 'api_key'"
            )

    @staticmethod
    def create_no_auth() -> IAuthProvider:
        """
        Metodo helper para crear NoAuthProvider

        Returns:
            Instancia de NoAuthProvider
        """
        return NoAuthProvider()

    @staticmethod
    def create_jwt(token: str, **kwargs) -> IAuthProvider:
        """
        Metodo helper para crear JWTAuthProvider

        Args:
            token: Token JWT
            **kwargs: Argumentos adicionales

        Returns:
            Instancia de JWTAuthProvider
        """
        return JWTAuthProvider(token=token, **kwargs)

    @staticmethod
    def create_api_key(api_key: str, **kwargs) -> IAuthProvider:
        """
        Metodo helper para crear APIKeyAuthProvider

        Args:
            api_key: Clave de API
            **kwargs: Argumentos adicionales

        Returns:
            Instancia de APIKeyAuthProvider
        """
        return APIKeyAuthProvider(api_key=api_key, **kwargs)
