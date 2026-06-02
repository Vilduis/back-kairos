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

    # Admins por defecto (seed). En local salen del .env; en Render, de las env vars.
    ADMIN_FULL_NAME: str = "Admin"
    ADMIN_EMAIL: Optional[str] = None
    ADMIN_LUIS_FULL_NAME: str = "Luis Admin"
    ADMIN_LUIS_EMAIL: Optional[str] = None
    ADMIN_KETY_FULL_NAME: str = "Katy Admin"
    ADMIN_KETY_EMAIL: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None

    # Model artifacts path (optional)
    MODEL_ARTIFACTS_PATH: Optional[str] = None

    # Gemini settings (opcionales)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: Optional[str] = None

    # Resend (email transaccional)
    API_RESEND: Optional[str] = None
    RESEND_FROM: str = "Kairos <noreply@vilduis.com>"

    # Frontend
    FRONTEND_URL: str
    PASSWORD_RESET_PATH: str = "/reset-password"
    
settings = Settings()