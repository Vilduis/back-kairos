from sqlalchemy import Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base, CreatedAt, IntPk


class School(Base):
    __tablename__ = "schools"

    school_id: Mapped[IntPk]
    name: Mapped[str] = mapped_column(String(150))
    created_at: Mapped[CreatedAt]


Index("uq_schools_name_lower", func.lower(School.name), unique=True)
