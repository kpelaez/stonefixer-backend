import os
from pydantic import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Configuracion para conectarse a base de datos StoneFixer
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    DEBUG: bool
    APP_NAME: str

    # Configuracion para obtener KPIs en la base defaultdb
    KPI_DATABASE_URL: str

settings = Settings(
    # Configuracion para conectarse a base de datos StoneFixer
    DATABASE_URL=os.getenv("DATABASE_URL","sqlite///./sql_app.db"),
    # Clave para jwt
    SECRET_KEY='Harumi2023',
    ALGORITHM="HS256",
    ACCESS_TOKEN_EXPIRE_MINUTES=30,
    DEBUG= os.getenv("DEBUG", "False") == "True",
    APP_NAME="StoneFixer Services",

    # Nueva configuracion para KPIs
    KPI_DATABASE_URL = os.getenv("KPI_DATABASE_URL", ""),
)