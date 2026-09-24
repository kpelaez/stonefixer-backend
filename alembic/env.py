from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import sys
import os

# Agregar el directorio raíz al path para importar la app
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Única fuente de verdad para la conexión: la misma que usa la app en runtime.
# app.config.settings ya resuelve correctamente qué .env cargar según ENVIRONMENT,
# con fail-fast si falta algo — no reimplementamos esa lógica acá.
from app.config import settings

from app.models.tech_asset import TechAsset
from app.models.asset_assignment import AssetAssignment
from app.models.asset_maintenance import AssetMaintenance
from app.models.role import Role
from app.models.user import User
from app.models.overtime import OvertimeEntry

from sqlmodel import SQLModel

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def get_url() -> str:
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


# Print explícito para que SIEMPRE veas a qué base te estás por conectar
# antes de que corra ninguna migración — esto es la salvaguarda que faltó la vez pasada.
print(f"🔌 Alembic conectando a: {get_url().split('@')[-1]}  (ENVIRONMENT={settings.ENVIRONMENT})")

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()