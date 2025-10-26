from pydantic_settings import BaseSettings
from typing import Optional, List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # App
    DEBUG: bool = True
    CORS_ORIGINS: List[str] = ["https://kairos-pe.netlify.app/"]
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60
    SEED_ON_STARTUP: bool = False

    # Model artifacts path (optional)
    MODEL_ARTIFACTS_PATH: Optional[str] = None

    # Gemini settings (opcionales)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: Optional[str] = None

    # Email / SMTP (opcionales pero recomendados para recuperación)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_STARTTLS: bool = True

    # Frontend URL para construir enlaces de recuperación
    FRONTEND_URL: str = "https://kairos-pe.netlify.app/"
    PASSWORD_RESET_PATH: str = "/reset-password"
    
    class Config:
        env_file = ".env"

settings = Settings()