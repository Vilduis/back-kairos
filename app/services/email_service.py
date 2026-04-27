import logging
import resend
from typing import Optional
from ..config import settings

logger = logging.getLogger(__name__)


def build_reset_link(token: str) -> str:
    path = settings.PASSWORD_RESET_PATH
    if not path.startswith("/"):
        path = "/" + path
    return f"{settings.FRONTEND_URL}{path}?token={token}"


def send_password_reset_email(to_email: str, token: str) -> Optional[str]:
    if not settings.RESEND_API_KEY:
        return None

    reset_link = build_reset_link(token)
    resend.api_key = settings.RESEND_API_KEY

    try:
        resend.Emails.send({
            "from": settings.RESEND_FROM,
            "to": [to_email],
            "subject": "Recupera tu contraseña - Kairos",
            "html": f"""<html><body>
                <p>Hola,</p>
                <p>Para restablecer tu contraseña, haz clic en el siguiente enlace:</p>
                <p><a href="{reset_link}">{reset_link}</a></p>
                <p>Si no solicitaste esto, puedes ignorar este correo.</p>
            </body></html>""",
        })
    except Exception as e:
        logger.error("Error enviando email de recuperación a %s: %s", to_email, e)
        return None

    return reset_link
