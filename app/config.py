from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

class Settings(BaseSettings):
    # Configuración de Pydantic Settings (v2)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # App
    DEBUG: bool = False
    CORS_ORIGINS: List[str]
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60
    SEED_ON_STARTUP: bool = False

    # Model artifacts path (optional)
    MODEL_ARTIFACTS_PATH: Optional[str] = None

    # Gemini settings (opcionales)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: Optional[str] = None

    # SMTP (Gmail)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    # Frontend
    FRONTEND_URL: str
    PASSWORD_RESET_PATH: str = "/reset-password"
    
settings = Settings()