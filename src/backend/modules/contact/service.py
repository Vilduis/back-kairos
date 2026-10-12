import logging

from fastapi import status

from backend.core.exceptions import DomainError
from backend.integrations.email import (
    EmailDeliveryError,
    EmailNotConfiguredError,
    send_contact_email,
)
from backend.modules.contact.schemas import ContactMessage

logger = logging.getLogger(__name__)


class ServiceUnavailableError(DomainError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


def send_contact_message(data: ContactMessage) -> None:
    # El campo `website` está oculto para las personas: si llega con texto lo llenó un bot.
    if data.website:
        return
    try:
        send_contact_email(data.name, str(data.email), data.subject, data.message)
    except EmailNotConfiguredError as error:
        logger.warning("Resend no está configurado; no se envió el mensaje de contacto")
        raise ServiceUnavailableError("El envío de mensajes no está disponible") from error
    except EmailDeliveryError as error:
        logger.exception("No se pudo enviar el mensaje de contacto")
        raise ServiceUnavailableError(
            "No pudimos enviar tu mensaje. Inténtalo más tarde."
        ) from error
