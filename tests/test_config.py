import pytest

from backend.core.config import Settings


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ],
)
def test_database_url_uses_psycopg_driver(url: str, expected: str) -> None:
    settings = Settings(database_url=url, secret_key="clave", _env_file=None)

    assert settings.database_url == expected
