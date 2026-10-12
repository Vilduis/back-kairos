from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.modules.users.models import User

# Subirla cuando cambie el texto del consentimiento: los estudiantes vuelven a aceptarlo.
CONSENT_VERSION = 1


def has_current_consent(user: User) -> bool:
    return user.consent_accepted_at is not None and user.consent_version == CONSENT_VERSION


def accept_consent(session: Session, user: User) -> User:
    if not has_current_consent(user):
        user.consent_accepted_at = datetime.now(UTC)
        user.consent_version = CONSENT_VERSION
        session.commit()
    return user
