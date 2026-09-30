import logging

import resend

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

PASSWORD_RESET_TEMPLATE = """<html><body>
<p>Hola,</p>
<p>Para restablecer tu contraseña en Kairos, haz clic en el siguiente enlace:</p>
<p><a href="{link}" style="background:#4f46e5;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;">Restablecer contraseña</a></p>
<p>O copia este enlace en tu navegador:</p>
<p style="color:#6b7280;font-size:13px;">{link}</p>
<p>El enlace expira en {minutes} minutos. Si no solicitaste este cambio, ignora este correo.</p>
</body></html>"""  # noqa: E501


def build_password_reset_link(token: str) -> str:
    settings = get_settings()
    path = settings.password_reset_path.lstrip("/")
    return f"{settings.frontend_url.rstrip('/')}/{path}?token={token}"


def send_password_reset_email(to_email: str, token: str) -> None:
    settings = get_settings()
    link = build_password_reset_link(token)

    if not settings.resend_api_key:
        logger.warning("Resend no está configurado; no se envió el correo a %s", to_email)
        if settings.debug:
            logger.warning("Enlace de recuperación (solo en debug): %s", link)
        return

    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send(
            {
                "from": settings.resend_from,
                "to": [to_email],
                "subject": "Restablece tu contraseña de Kairos",
                "html": PASSWORD_RESET_TEMPLATE.format(
                    link=link, minutes=settings.password_reset_expire_minutes
                ),
            }
        )
    except resend.exceptions.ResendError:
        logger.exception("No se pudo enviar el correo de recuperación a %s", to_email)
