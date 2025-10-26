from email.message import EmailMessage
import smtplib
from typing import Optional
from ..config import settings


def _smtp_configured() -> bool:
    return bool(getattr(settings, "SMTP_HOST", None) and getattr(settings, "SMTP_FROM", None))


def build_reset_link(token: str) -> str:
    base = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    path = getattr(settings, "PASSWORD_RESET_PATH", "/reset-password")
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}?token={token}"


def send_password_reset_email(to_email: str, token: str) -> Optional[str]:
    """Envía el correo de recuperación si SMTP está configurado.
    Retorna el enlace usado si se envía; None si no se envía.
    """
    if not _smtp_configured():
        return None

    host = settings.SMTP_HOST
    port = getattr(settings, "SMTP_PORT", 587)
    user = getattr(settings, "SMTP_USERNAME", None)
    pwd = getattr(settings, "SMTP_PASSWORD", None)
    from_addr = settings.SMTP_FROM
    use_starttls = getattr(settings, "SMTP_STARTTLS", True)

    msg = EmailMessage()
    msg["Subject"] = "Recupera tu contraseña - Kairos"
    msg["From"] = from_addr
    msg["To"] = to_email
    reset_link = build_reset_link(token)
    msg.set_content(
        f"Hola,\n\nPara restablecer tu contraseña, usa este enlace:\n{reset_link}\n\nSi no solicitaste esto, ignora este correo.\n"
    )
    msg.add_alternative(
        f"""<html><body>
            <p>Hola,</p>
            <p>Para restablecer tu contraseña, haz clic en el siguiente enlace:</p>
            <p><a href=\"{reset_link}\">{reset_link}</a></p>
            <p>Si no solicitaste esto, puedes ignorar este correo.</p>
        </body></html>""",
        subtype="html",
    )

    with smtplib.SMTP(host, port) as server:
        if use_starttls:
            server.starttls()
        if user and pwd:
            server.login(user, pwd)
        server.send_message(msg)

    return reset_link