import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from backend.core.config import get_settings

_password_hash = PasswordHash.recommended()

# Hash de referencia para verificar contraseñas de usuarios inexistentes: iguala el tiempo
# de respuesta y evita revelar qué emails están registrados.
DUMMY_PASSWORD_HASH = _password_hash.hash("kairos-dummy-password")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expires_at}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError:
        return None
    return payload.get("sub")


def generate_url_token() -> str:
    return secrets.token_urlsafe(32)


def hash_url_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
