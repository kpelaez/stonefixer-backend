from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import sys
import os

# Agregar el directorio raíz al path para importar tus modelos
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Importar tus modelos - AJUSTA SEGÚN TU ESTRUCTURA
# Si tus modelos están en models.py:
from app.models.tech_asset import TechAsset
from app.models.asset_assignment import AssetAssignment
from app.models.asset_maintenance import AssetMaintenance
from app.models.role import Role
from app.models.user import User
from app.models.overtime import OvertimeEntry

from sqlmodel import SQLModel

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = SQLModel.metadata

# Usar DATABASE_URL de variables de entorno si está disponible
def get_url():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    return config.get_main_option("sqlalchemy.url")

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    
    # Override with environment variable if available
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        configuration['sqlalchemy.url'] = database_url
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()