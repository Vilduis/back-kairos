from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, EmailStr, StringConstraints


class ContactSubject(StrEnum):
    DEMO = "Solicitar una demo"
    SERVICE = "Consulta sobre el servicio"
    SUPPORT = "Soporte técnico"
    SUGGESTION = "Sugerencias"
    OTHER = "Otro"


class ContactMessage(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    email: EmailStr
    subject: ContactSubject
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)
    ]
    website: str = ""
