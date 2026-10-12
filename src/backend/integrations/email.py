import logging
from html import escape

import resend

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

INDIGO = "#5460a8"
INK = "#1e2152"

PASSWORD_RESET_TEMPLATE = """<html><body style="color:{ink};font-family:sans-serif;">
<p>Hola,</p>
<p>Para restablecer tu contraseña en Kairos, haz clic en el siguiente enlace:</p>
<p><a href="{link}" style="background:{indigo};color:white;padding:10px 20px;border-radius:12px;text-decoration:none;">Restablecer contraseña</a></p>
<p>O copia este enlace en tu navegador:</p>
<p style="font-size:13px;">{link}</p>
<p>El enlace expira en {minutes} minutos. Si no solicitaste este cambio, ignora este correo.</p>
</body></html>"""  # noqa: E501

CONTACT_TEMPLATE = """<html><body style="color:{ink};font-family:sans-serif;">
<h2 style="color:{indigo};">{subject}</h2>
<p><strong>Nombre:</strong> {name}<br><strong>Correo:</strong> {email}</p>
<p style="white-space:pre-line;">{message}</p>
</body></html>"""


class EmailNotConfiguredError(Exception):
    pass


class EmailDeliveryError(Exception):
    pass


def _send(params: dict[str, str | list[str]]) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        raise EmailNotConfiguredError
    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send({"from": settings.resend_from, **params})
    except resend.exceptions.ResendError as error:
        raise EmailDeliveryError from error


def build_password_reset_link(token: str) -> str:
    settings = get_settings()
    path = settings.password_reset_path.lstrip("/")
    return f"{settings.frontend_url.rstrip('/')}/{path}?token={token}"


def send_password_reset_email(to_email: str, token: str) -> None:
    settings = get_settings()
    link = build_password_reset_link(token)
    html = PASSWORD_RESET_TEMPLATE.format(
        link=link, minutes=settings.password_reset_expire_minutes, indigo=INDIGO, ink=INK
    )
    try:
        _send({"to": [to_email], "subject": "Restablece tu contraseña de Kairos", "html": html})
    except EmailNotConfiguredError:
        logger.warning("Resend no está configurado; no se envió el correo a %s", to_email)
        if settings.debug:
            logger.warning("Enlace de recuperación (solo en debug): %s", link)
    except EmailDeliveryError:
        logger.exception("No se pudo enviar el correo de recuperación a %s", to_email)


def send_contact_email(name: str, email: str, subject: str, message: str) -> None:
    html = CONTACT_TEMPLATE.format(
        subject=escape(subject),
        name=escape(name),
        email=escape(email),
        message=escape(message),
        indigo=INDIGO,
        ink=INK,
    )
    _send(
        {
            "to": [get_settings().contact_email],
            "reply_to": email,
            "subject": f"[Kairos] {subject} - {name}",
            "html": html,
        }
    )
