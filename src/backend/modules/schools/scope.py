from dataclasses import dataclass

from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute

from backend.core.exceptions import DomainError
from backend.modules.users.models import User

SCHOOL_REQUIRED = "Indica el colegio"


@dataclass(frozen=True)
class SchoolScope:
    """Colegio al que se limita lo que gestiona un administrador; sin colegio abarca todos."""

    school_id: int | None
    is_superadmin: bool

    def narrow(self, school_id: int | None) -> SchoolScope:
        if self.school_id is not None or school_id is None:
            return self
        return SchoolScope(school_id=school_id, is_superadmin=self.is_superadmin)

    def covers(self, school_id: int | None) -> bool:
        return self.school_id is None or school_id == self.school_id

    def conditions(
        self, column: InstrumentedAttribute[int | None] = User.school_id
    ) -> list[ColumnElement[bool]]:
        return [] if self.school_id is None else [column == self.school_id]

    def target_school(self, requested: int | None) -> int:
        """Colegio donde se crea algo: el que elige el superadmin o el del administrador."""
        school_id = requested if self.is_superadmin else self.school_id
        if school_id is None:
            raise DomainError(SCHOOL_REQUIRED)
        return school_id
