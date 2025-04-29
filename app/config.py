import os
from pydantic import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    DEBUG: bool
    APP_NAME: str

settings = Settings(
    DATABASE_URL=os.getenv("DATABASE_URL","sqlite///./sql_app.db"),
    SECRET_KEY='Harumi2023',
    ALGORITHM="HS256",
    ACCESS_TOKEN_EXPIRE_MINUTES=30,
    DEBUG= os.getenv("DEBUG", "False") == "True",
    APP_NAME="Auth Service"
)