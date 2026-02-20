"""
WebhookPublisher - Publicador de resultados a servicio externo

SRP: Responsabilidad unica - enviar POST HTTP a webhook
OCP: Extensible para nuevos tipos de autenticacion/retry
"""

import httpx
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class WebhookPublisher:
    """
    Publica resultados de procesamiento a un webhook externo.

    SRP: Responsabilidad unica - enviar POST HTTP a webhook
    OCP: Extensible para nuevos tipos de autenticacion/retry

    CONFIGURACION (.env):
    - WEBHOOK_URL: URL del endpoint destino
    - WEBHOOK_TIMEOUT: Timeout en segundos (default: 30)
    - WEBHOOK_MAX_RETRIES: Numero de reintentos (default: 3)
    - WEBHOOK_AUTH_TYPE: Tipo de auth ('none', 'bearer', 'api_key')
    - WEBHOOK_AUTH_TOKEN: Token/API Key si aplica
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        auth_type: str = "none",
        auth_token: Optional[str] = None
    ):
        """
        Args:
            webhook_url: URL del webhook (None = obtener desde .env)
            timeout: Timeout en segundos
            max_retries: Numero de reintentos
            auth_type: Tipo de autenticacion ('none', 'bearer', 'api_key')
            auth_token: Token de autenticacion (si aplica)
        """
        self.webhook_url = webhook_url or os.getenv("WEBHOOK_URL")
        self.timeout = int(os.getenv("WEBHOOK_TIMEOUT", timeout))
        self.max_retries = int(os.getenv("WEBHOOK_MAX_RETRIES", max_retries))
        self.auth_type = os.getenv("WEBHOOK_AUTH_TYPE", auth_type)
        self.auth_token = auth_token or os.getenv("WEBHOOK_AUTH_TOKEN")

        if not self.webhook_url:
            logger.warning("WEBHOOK_URL no configurado - webhook deshabilitado")

    def update_auth_token(self, new_token: str):
        """
        Actualiza el token de autenticacion dinamicamente.

        v3.13.0: Usado por BackgroundProcessor para inyectar token fresco
        obtenido via re-autenticacion antes de cada tarea.

        Args:
            new_token: Nuevo token JWT

        Example:
            >>> publisher = WebhookPublisher(auth_type="bearer")
            >>> publisher.update_auth_token("eyJ0eXAiOiJKV1QiLCJhbGci...")
        """
        self.auth_token = new_token
        logger.info("Token de autenticacion actualizado en WebhookPublisher")

    async def enviar_resultado(
        self,
        factura_id: int,
        resultado: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Envia el resultado del procesamiento al webhook.

        Args:
            factura_id: ID unico de la factura del cliente (entero)
            resultado: Diccionario con resultado completo

        Returns:
            Dict con informacion del envio:
            {
                'success': bool,
                'status_code': int,
                'message': str,
                'intentos': int,
                'timestamp': str
            }
        """
        if not self.webhook_url:
            logger.warning(f"Factura {factura_id}: Webhook no configurado - resultado no enviado")
            return {
                "success": False,
                "status_code": 0,
                "message": "Webhook no configurado",
                "intentos": 0,
                "timestamp": datetime.now().isoformat()
            }

        # Preparar payload para webhook
        payload = {
            "facturaId": factura_id,
            "timestamp": datetime.now().isoformat(),
            "data": resultado
        }

        # Configurar headers con autenticacion
        headers = self._configurar_headers()

        # Intentar envio con reintentos
        for intento in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Factura {factura_id}: Enviando resultado a webhook "
                    f"(intento {intento}/{self.max_retries})"
                )

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.webhook_url,
                        json=payload,
                        headers=headers
                    )

                if response.status_code in [200, 201, 202]:
                    logger.info(
                        f"Factura {factura_id}: Webhook exitoso "
                        f"(status: {response.status_code})"
                    )
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "message": "Resultado enviado exitosamente",
                        "intentos": intento,
                        "timestamp": datetime.now().isoformat(),
                        "response_body": response.text[:500]  # Primeros 500 chars
                    }
                else:
                    logger.warning(
                        f"Factura {factura_id}: Webhook respondio con status {response.status_code}"
                    )
                    if intento < self.max_retries:
                        await asyncio.sleep(2 ** intento)  # Backoff exponencial
                        continue

            except httpx.TimeoutException as e:
                logger.error(f"Factura {factura_id}: Timeout en intento {intento} - {e}")
                if intento < self.max_retries:
                    await asyncio.sleep(2 ** intento)
                    continue

            except Exception as e:
                logger.error(
                    f"Factura {factura_id}: Error enviando a webhook (intento {intento}): {e}"
                )
                if intento < self.max_retries:
                    await asyncio.sleep(2 ** intento)
                    continue

        # Todos los reintentos fallaron
        return {
            "success": False,
            "status_code": 0,
            "message": f"Webhook fallo despues de {self.max_retries} intentos",
            "intentos": self.max_retries,
            "timestamp": datetime.now().isoformat()
        }

    def _configurar_headers(self) -> Dict[str, str]:
        """
        Configura headers HTTP incluyendo autenticacion.

        Returns:
            Dict con headers HTTP
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        if self.auth_type == "bearer" and self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        elif self.auth_type == "api_key" and self.auth_token:
            headers["X-API-Key"] = self.auth_token

        return headers
