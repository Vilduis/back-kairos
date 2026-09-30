import os
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import Base, get_session
from backend.core.enums import ChatMode, EvaluationMode, EvaluationStatus, UserRole
from backend.core.security import create_access_token, hash_password
from backend.main import app
from backend.modules.chat.models import ChatSession
from backend.modules.evaluations.models import Evaluation, EvaluationResult
from backend.modules.users.models import User

DEFAULT_PASSWORD = "secreto123"

type UserFactory = Callable[..., User]
type EvaluationFactory = Callable[..., Evaluation]


def _ensure_database_exists(url: URL) -> None:
    server = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        exists = connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        )
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    server.dispose()


@pytest.fixture(autouse=True)
def no_llm_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ningún test debe llamar a una API externa aunque haya claves reales en .env.
    monkeypatch.setattr("backend.integrations.llm.get_providers", lambda: ())


@pytest.fixture(scope="session")
def connection() -> Iterator[Connection]:
    url = make_url(get_settings().database_url)
    test_url = url.set(database=os.environ.get("TEST_DATABASE_NAME", f"{url.database}_test"))
    _ensure_database_exists(test_url)

    engine = create_engine(test_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        yield connection
    engine.dispose()


@pytest.fixture
def session(connection: Connection) -> Iterator[Session]:
    transaction = connection.begin()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        yield session
    transaction.rollback()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def create_user(session: Session) -> UserFactory:
    def factory(
        *,
        email: str = "estudiante@kairos.dev",
        role: UserRole = UserRole.STUDENT,
        is_active: bool = True,
    ) -> User:
        user = User(
            full_name="Usuario de Prueba",
            email=email,
            password_hash=hash_password(DEFAULT_PASSWORD),
            role=role,
            is_active=is_active,
        )
        session.add(user)
        session.flush()
        return user

    return factory


@pytest.fixture
def create_evaluation(session: Session) -> EvaluationFactory:
    def factory(student: User, *, with_result: bool = True) -> Evaluation:
        chat_session = ChatSession(user_id=student.user_id, chat_mode=ChatMode.GUIDED)
        session.add(chat_session)
        session.flush()
        evaluation = Evaluation(
            user_id=student.user_id,
            session_id=chat_session.session_id,
            evaluation_mode=EvaluationMode.GUIDED,
        )
        if with_result:
            evaluation.status = EvaluationStatus.COMPLETED
            evaluation.progress = 1.0
            evaluation.result = EvaluationResult(
                riasec_scores={"R": 0.2, "I": 0.9, "A": 0.4, "S": 0.3, "E": 0.1, "C": 0.5},
                top_careers=[{"career": "Ingeniería de Sistemas", "score": 0.93}],
                metrics={"model_version": 8.0, "source_mode": 0.0},
            )
        session.add(evaluation)
        session.flush()
        return evaluation

    return factory


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.user_id))}"}
