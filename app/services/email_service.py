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
    if not settings.API_RESEND:
        logger.warning("Resend API key no configurado, email no enviado.")
        return None

    reset_link = build_reset_link(token)

    html = f"""<html><body>
        <p>Hola,</p>
        <p>Para restablecer tu contraseña en Kairos, haz clic en el siguiente enlace:</p>
        <p><a href="{reset_link}" style="background:#4f46e5;color:white;padding:10px 20px;border-radius:6px;text-decoration:none;">
            Restablecer contraseña
        </a></p>
        <p>O copia este enlace en tu navegador:</p>
        <p style="color:#6b7280;font-size:13px;">{reset_link}</p>
        <p>Este enlace expira en {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutos.</p>
        <p style="color:#9ca3af;font-size:12px;">Si no solicitaste esto, puedes ignorar este correo.</p>
    </body></html>"""

    try:
        resend.api_key = settings.API_RESEND
        resend.Emails.send({
            "from": settings.RESEND_FROM,
            "to": [to_email],
            "subject": "Recupera tu contraseña - Kairos",
            "html": html,
        })
        logger.info("Email de recuperación enviado a %s", to_email)
    except Exception as e:
        logger.error("Error enviando email de recuperación a %s: %s", to_email, e)
        return None

    return reset_link
