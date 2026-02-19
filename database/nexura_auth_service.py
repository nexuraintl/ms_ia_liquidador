"""
NexuraAuthService - Servicio de autenticacion centralizado para Nexura API

SRP: Responsabilidad unica - gestionar login y tokens de Nexura
DIP: Retorna abstracciones (IAuthProvider) para inyeccion
OCP: Extensible para nuevos metodos de auth sin modificar

CRITICAL: Si el login falla, el servicio debe lanzar excepcion
para prevenir inicio del sistema sin autenticacion valida.
"""

import httpx
import logging
from typing import Optional
from datetime import datetime, timedelta
from .auth_provider import JWTAuthProvider, IAuthProvider

logger = logging.getLogger(__name__)


class NexuraAuthenticationError(Exception):
    """Excepcion critica cuando falla la autenticacion con Nexura"""
    pass


class NexuraAuthService:
    """
    Servicio centralizado de autenticacion para Nexura API.

    SRP: Solo maneja autenticacion (login, refresh, validacion)
    DIP: Produce IAuthProvider para inyeccion en otros componentes

    CRITICAL: Si no puede autenticar, lanza NexuraAuthenticationError
    para prevenir inicio del servicio.
    """

    def __init__(
        self,
        base_url: str,
        login_user: str,
        login_password: str,
        timeout: int = 30
    ):
        """
        Inicializa servicio de autenticacion.

        Args:
            base_url: URL base de Nexura API (ej: https://preproduccion-fiducoldex.nexura.com/api)
            login_user: Usuario para login
            login_password: Contrasena para login
            timeout: Timeout para requests HTTP
        """
        self.base_url = base_url.rstrip('/')
        self.login_user = login_user
        self.login_password = login_password
        self.timeout = timeout

        # Estado interno
        self._auth_provider: Optional[IAuthProvider] = None
        self._token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiration: Optional[datetime] = None

        logger.info(f"NexuraAuthService inicializado para: {self.base_url}")

    async def login(self) -> IAuthProvider:
        """
        Ejecuta login a Nexura y crea AuthProvider con el token.

        CRITICAL: Si falla el login, lanza NexuraAuthenticationError
        para prevenir inicio del servicio.

        Returns:
            IAuthProvider configurado con token valido

        Raises:
            NexuraAuthenticationError: Si login falla (CRITICO)
        """
        logger.info("Iniciando login a Nexura API...")

        login_url = f"{self.base_url}/usuarios/login"
        payload = {
            "login": self.login_user,
            "password": self.login_password
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Nexura espera form-data (application/x-www-form-urlencoded)
                response = await client.post(
                    login_url,
                    data=payload,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                )

                # Verificar status code
                if response.status_code != 200:
                    error_msg = (
                        f"Login a Nexura fallo con status {response.status_code}. "
                        f"Response: {response.text[:500]}"
                    )
                    logger.critical(error_msg)
                    raise NexuraAuthenticationError(error_msg)

                # Parsear respuesta
                data = response.json()

                # Verificar error code en respuesta (Nexura retorna error.code)
                error_code = data.get("error", {}).get("code")
                if error_code is not None and error_code != 0:
                    error_msg = f"Login a Nexura retorno error: {data.get('error')}"
                    logger.critical(error_msg)
                    raise NexuraAuthenticationError(error_msg)

                # Verificar estructura de respuesta
                if "data" not in data or "token" not in data["data"]:
                    error_msg = "Respuesta de login sin token valido"
                    logger.critical(error_msg)
                    raise NexuraAuthenticationError(error_msg)

                # Extraer tokens
                self._token = data["data"]["token"]
                self._refresh_token = data["data"].get("refresh")

                # Calcular expiracion (asumir 1 hora si no viene en respuesta)
                self._token_expiration = datetime.now() + timedelta(hours=1)

                logger.info("Login a Nexura exitoso - Token obtenido")

                # Crear AuthProvider con el token
                self._auth_provider = JWTAuthProvider(
                    token=self._token,
                    token_type="Bearer",
                    auto_refresh=True,
                    refresh_callback=self._refresh_token_callback,
                    expiration_time=self._token_expiration
                )

                return self._auth_provider

        except httpx.TimeoutException as e:
            error_msg = f"Timeout en login a Nexura: {e}"
            logger.critical(error_msg)
            raise NexuraAuthenticationError(error_msg)

        except httpx.RequestError as e:
            error_msg = f"Error de red en login a Nexura: {e}"
            logger.critical(error_msg)
            raise NexuraAuthenticationError(error_msg)

        except NexuraAuthenticationError:
            # Re-lanzar excepciones de autenticacion
            raise

        except Exception as e:
            error_msg = f"Error inesperado en login a Nexura: {e}"
            logger.critical(error_msg)
            raise NexuraAuthenticationError(error_msg)

    def _refresh_token_callback(self):
        """
        Callback para refrescar token automaticamente.

        Returns:
            tuple: (nuevo_token, nueva_expiracion)
        """
        # TODO: Implementar refresh con refresh_token si Nexura lo soporta
        # Por ahora, retornar token actual (JWTAuthProvider no refrescara)
        logger.warning("Refresh de token no implementado - usando token actual")
        return self._token, self._token_expiration

    def get_auth_provider(self) -> Optional[IAuthProvider]:
        """
        Obtiene el AuthProvider actual (si ya se hizo login).

        Returns:
            IAuthProvider o None si no se ha hecho login
        """
        return self._auth_provider

    def get_token(self) -> Optional[str]:
        """
        Obtiene el token actual (para debugging/logging).

        Returns:
            Token JWT o None
        """
        return self._token
