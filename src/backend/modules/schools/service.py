from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError, NotFoundError
from backend.modules.schools.models import School
from backend.modules.schools.schemas import SchoolWrite


def get_school(session: Session, school_id: int) -> School:
    school = session.get(School, school_id)
    if school is None:
        raise NotFoundError("Colegio no encontrado")
    return school


def list_schools(session: Session) -> Sequence[School]:
    return session.scalars(select(School).order_by(School.name)).all()


def _ensure_name_available(session: Session, name: str, school_id: int | None = None) -> None:
    statement = select(School.school_id).where(func.lower(School.name) == name.lower())
    owner = session.scalar(statement)
    if owner is not None and owner != school_id:
        raise DomainError("Ya existe un colegio con ese nombre")


def create_school(session: Session, data: SchoolWrite) -> School:
    _ensure_name_available(session, data.name)
    school = School(name=data.name)
    session.add(school)
    session.commit()
    return school


def rename_school(session: Session, school_id: int, data: SchoolWrite) -> School:
    school = get_school(session, school_id)
    _ensure_name_available(session, data.name, school_id)
    school.name = data.name
    session.commit()
    return school
