import os
from typing import List
from pydantic import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Configuracion para conectarse a base de datos StoneFixer
    DATABASE_URL: str
    KPI_DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    ALLOWED_ORIGINS: str = "http://localhost:5173"

    APP_NAME: str = "StoneFixer"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT: str = "5/minute"
    REGISTER_RATE_LIMIT: str = "5/hour"
    API_RATE_LIMIT: str = "100/minute"

    # Por tipo de operación
    READ_RATE_LIMIT: str = "200/minute"
    WRITE_RATE_LIMIT: str = "50/minute"
    CRITICAL_WRITE_RATE_LIMIT: str = "20/minute"
    SEARCH_RATE_LIMIT: str = "100/minute"

    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def cors_origins(self) -> List[str]:
        """Convertir string de origins a lista"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    

@lru_cache()
def get_settings() -> Settings:
    """Singleton de settings con cache"""
    return Settings()


settings = get_settings()


