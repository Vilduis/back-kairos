import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from ..config import settings

logger = logging.getLogger(__name__)


def build_reset_link(token: str) -> str:
    path = settings.PASSWORD_RESET_PATH
    if not path.startswith("/"):
        path = "/" + path
    return f"{settings.FRONTEND_URL}{path}?token={token}"


def send_password_reset_email(to_email: str, token: str) -> Optional[str]:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP no configurado, email de recuperación no enviado.")
        return None

    reset_link = build_reset_link(token)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Recupera tu contraseña - Kairos"
    msg["From"] = settings.SMTP_USER
    msg["To"] = to_email

    html = f"""<html><body>
        <p>Hola,</p>
        <p>Para restablecer tu contraseña, haz clic en el siguiente enlace:</p>
        <p><a href="{reset_link}">{reset_link}</a></p>
        <p>Este enlace expira en {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutos.</p>
        <p>Si no solicitaste esto, puedes ignorar este correo.</p>
    </body></html>"""
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
    except Exception as e:
        logger.error("Error enviando email de recuperación a %s: %s", to_email, e)
        return None

    return reset_link
