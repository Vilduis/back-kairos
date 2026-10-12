from fastapi import APIRouter

from backend.core.schemas import Message
from backend.modules.contact import service
from backend.modules.contact.schemas import ContactMessage

router = APIRouter(tags=["contact"])


@router.post("/contact")
def send_contact_message(data: ContactMessage) -> Message:
    service.send_contact_message(data)
    return Message(detail="Mensaje enviado")
