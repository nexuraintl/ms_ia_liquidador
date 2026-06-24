"""
Modulo de procesamiento asincrono para PRELIQUIDADOR v3.0

Implementa procesamiento en background con arquitectura SOLID:
- SRP: Cada clase tiene una responsabilidad unica
- OCP: Extensible sin modificar codigo existente
- DIP: Depende de abstracciones, no de concreciones

Componentes:
- WebhookPublisher: Envio de resultados a servicio externo
- BackgroundProcessor: Orquestador del flujo completo

Uso:
    from Background import WebhookPublisher, BackgroundProcessor

    webhook_publisher = WebhookPublisher()

    processor = BackgroundProcessor(
        webhook_publisher=webhook_publisher,
        business_service=business_service,
        db_manager=db_manager
    )
"""

from .webhook_publisher import WebhookPublisher
from .background_processor import BackgroundProcessor

__all__ = [
    "WebhookPublisher",
    "BackgroundProcessor",
]

__version__ = "3.0.0"
