import os
import secrets
from functools import lru_cache
from typing import List
import logging


from pydantic_settings import BaseSettings
from pydantic import field_validator, ValidationError

logger = logging.getLogger(__name__)

def _get_env_file() -> str:
    env = os.getenv("ENVIRONMENT", "development")
    env_file = f".env.{env}"
    if os.path.exists(env_file):
        return env_file
    # fallback a .env si existe
    if os.path.exists(".env"):
        return ".env"
    return env_file  # pydantic falle con mensaje claro


class Settings(BaseSettings):
    """
    Configuración centralizada de StoneFixer.

    Si una variable requerida no existe, la app NO ARRANCA (fail-fast).
    Esto es intencional: mejor fallar al inicio que tener un secret vacío en producción.
    """
    # Base de datos principal
    DATABASE_URL: str
    LAKEHOUSE_DATABASE_URL: str

    # Autenticación
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Aplicación
    DEBUG: bool = False
    APP_NAME: str = "StoneFixer"
    ENVIRONMENT: str = "development"  # development | staging | production

    # Humand API
    HUMAND_API_URL: str = "https://api-prod.humand.co/public/api/v1"
    HUMAND_API_KEY: str = ""
    HUMAND_FOLDER_ID: int = 358764

    # Seguridad DNI
    DNI_ENCRYPTION_KEY: str = ""

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://192.168.56.1:5173,http://192.168.0.146:5173,http://192.168.0.140:5173"
    APP_BASE_URL: str = "http://localhost:5173"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    API_RATE_LIMIT: str = "60/minute"
    LOGIN_RATE_LIMIT: str = "5/minute"
    READ_RATE_LIMIT: str = "120/minute"
    WRITE_RATE_LIMIT: str = "30/minute"
    CRITICAL_WRITE_RATE_LIMIT: str = "10/minute"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Swagger
    SWAGGER_USERNAME: str = "admin"
    SWAGGER_PASSWORD: str

    # URL para etiquetas
    LABEL_BASE_URL: str = "https://stonefixer.mklcoders.com.ar"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        FORBIDDEN_KEYS = {
            "secret", "secret_key", "mysecret", "changeme", "password",
            "12345678", "harumi2023", "harumi",
            "test", "dev", "development",
        }

        if not v:
            raise ValueError("SECRET_KEY no puede estar vacía")

        if len(v) < 32:
            raise ValueError(
                f"SECRET_KEY demasiado corta ({len(v)} chars). "
                "Mínimo 32 caracteres. "
                "Generá una segura con: openssl rand -hex 32"
            )

        if v.lower() in FORBIDDEN_KEYS:
            raise ValueError(
                f"SECRET_KEY '{v}' es un valor prohibido. "
                "Usá: openssl rand -hex 32"
            )

        return v

    @field_validator("DNI_ENCRYPTION_KEY")
    @classmethod
    def validate_dni_key(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "DNI_ENCRYPTION_KEY no puede estar vacía. "
                "Generá una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

        if len(v) != 44:
            raise ValueError(
                f"DNI_ENCRYPTION_KEY tiene formato inválido ({len(v)} chars). "
                "Debe ser una clave Fernet válida de 44 caracteres."
            )

        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL no puede estar vacía")

        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)

        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v.lower() not in allowed:
            raise ValueError(f"ENVIRONMENT debe ser uno de: {allowed}")
        return v.lower()

    def get_allowed_origins(self) -> List[str]:
        """Parsea ALLOWED_ORIGINS desde string separado por comas a lista"""
        origins = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]
        
        # En desarrollo, agregar automáticamente rangos de red local comunes
        if self.is_development():
            dev_origins = [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ]
            for origin in dev_origins:
                if origin not in origins:
                    origins.append(origin)
        
        return origins
    
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    model_config = {
        "env_file": _get_env_file(),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Retorna la instancia de Settings cacheada.

    El @lru_cache asegura que Settings() se instancia UNA SOLA VEZ
    durante todo el ciclo de vida de la aplicación.
    """
    try:
        env_file = _get_env_file()
        logger.info(f"Cargando configuración desde: {env_file}")
        return Settings()
    except ValidationError as e:
        print("ERROR DE CONFIGURACIÓN - StoneFixer no puede iniciar")
        print("=" * 70)
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            print(f"\n  Campo: {field}")
            print(f"  Error: {error['msg']}")
        print("\nSolución: Verificar el archivo .env o las variables de entorno")
        print("Template:  Ver .env.example en la raíz del proyecto")
        raise SystemExit(1)


# Instancia global - importar esto en toda la app
settings = get_settings()