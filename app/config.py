import os
import secrets
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings
from pydantic import field_validator, ValidationError


class Settings(BaseSettings):
    """
    Configuración centralizada de StoneFixer.

    Si una variable requerida no existe, la app NO ARRANCA (fail-fast).
    Esto es intencional: mejor fallar al inicio que tener un secret vacío en producción.
    """
    # Configuracion para conectarse a base de datos StoneFixer
    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DEBUG: bool = False
    APP_NAME: str = "StoneFixer"
    ENVIRONMET: str = "development" # development | staging | production

    # Configuracion para obtener KPIs en la base defaultdb
    KPI_DATABASE_URL: str

    # Humand API
    HUMAND_API_URL: str = "https://api-prod.humand.co/public/api/v1"
    HUMAND_API_KEY: str = ""
    HUMAND_FOLDER_ID: int = 358764 # UD de ka carpeta "Equipos tecnologicos"

    # Seguridad DNI
    DNI_ENCRYPTION_KEY: str = "" # Generar con Fernet.generate_key()

    # CORS
    # En .env: ALLOWED_ORIGINS=http://localhost:5173,https://stonefixer.omnimedica.com
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    APP_BASE_URL: str = "http://localhost:5173"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """
        Valida que la SECRET_KEY sea segura.
        Rechaza valores obvios/débiles que podrían estar hardcodeados.
        """
        FORBIDDEN_KEYS = {
            "secret", "secret_key", "mysecret", "changeme", "password",
            "12345678", "harumi2023", "harumi",  # 👈 previene el valor anterior
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
        """Valida que la clave Fernet tenga el formato correcto"""
        if not v:
            raise ValueError(
                "DNI_ENCRYPTION_KEY no puede estar vacía. "
                "Generá una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

        # Fernet keys son base64url de 44 chars
        if len(v) != 44:
            raise ValueError(
                f"DNI_ENCRYPTION_KEY tiene formato inválido ({len(v)} chars). "
                "Debe ser una clave Fernet válida de 44 caracteres."
            )

        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Normaliza URL de PostgreSQL (Aiven usa 'postgres://', SQLAlchemy necesita 'postgresql://')"""
        if not v:
            raise ValueError("DATABASE_URL no puede estar vacía")

        # Aiven a veces devuelve 'postgres://' que SQLAlchemy no acepta
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
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,  # DATABASE_URL y database_url son equivalentes
        "extra": "ignore",        # Ignora variables extra del .env que no estén definidas
    }

@lru_cache()
def get_settings() -> Settings:
    """
    Retorna la instancia de Settings cacheada.
    
    El @lru_cache asegura que Settings() se instancia UNA SOLA VEZ
    durante todo el ciclo de vida de la aplicación.
    
    Si hay errores de validación (ej: SECRET_KEY faltante), 
    la app falla inmediatamente al arrancar con un mensaje claro.
    """
    try:
        return Settings()
    except ValidationError as e:
        # Mensaje de error claro para el desarrollador/DevOps
        print("\n" + "="*70)
        print("❌ ERROR DE CONFIGURACIÓN - StoneFixer no puede iniciar")
        print("="*70)
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            print(f"\n  Campo: {field}")
            print(f"  Error: {error['msg']}")
        print("\n  📋 Solución: Verificar el archivo .env o las variables de entorno")
        print("  📋 Template:  Ver .env.example en la raíz del proyecto")
        print("="*70 + "\n")
        raise SystemExit(1)  # Fallo limpio, no traceback confuso


# Instancia global - importar esto en toda la app
settings = get_settings()