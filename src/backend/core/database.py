import enum
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any, ClassVar

from fastapi import Depends
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    MetaData,
    Select,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from backend.core.config import get_settings
from backend.core.schemas import Pagination

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _enum_values(enum_class: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_class]


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar = {
        enum.Enum: Enum(enum.Enum, values_callable=_enum_values),
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
        list[dict[str, Any]]: JSONB,
    }


IntPk = Annotated[int, mapped_column(Identity(), primary_key=True)]
CreatedAt = Annotated[datetime, mapped_column(server_default=func.now())]


def cascade_fk(target: str, *, index: bool = True) -> Mapped[int]:
    return mapped_column(ForeignKey(target, ondelete="CASCADE"), index=index)


def paginate[T](statement: Select[tuple[T]], page: Pagination) -> Select[tuple[T]]:
    return statement.offset(page.skip).limit(page.limit)


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, autoflush=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
