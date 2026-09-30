from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

type LLMProviderName = Literal["deepseek", "gemini"]


class SeedAdmin(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Kairos API"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]

    database_url: str

    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    password_reset_expire_minutes: int = 60

    frontend_url: str = "http://localhost:3000"
    password_reset_path: str = "/reset-password"
    resend_api_key: str | None = None
    resend_from: str = "Kairos <noreply@vilduis.com>"

    model_artifacts_dir: Path = Path("artifacts")

    llm_providers: list[LLMProviderName] = ["deepseek", "gemini"]
    llm_timeout_seconds: float = 20.0
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    seed_admins: list[SeedAdmin] = []

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, url: str) -> str:
        """Render entrega `postgresql://`, que SQLAlchemy asocia a psycopg2 (no instalado)."""
        scheme, separator, rest = url.partition("://")
        if scheme in {"postgres", "postgresql"}:
            return f"postgresql+psycopg{separator}{rest}"
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
