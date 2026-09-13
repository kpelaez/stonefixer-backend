"""
app/db/lakehouse_database.py

Engine de solo lectura para el lakehouse Aiven (datos curados del ERP,
mantenidos por Martin). Reemplaza al Excel manual de tableros ejecutivos.

Usuario: stonefixer_readonly, con SELECT sobre schema 'prod' únicamente.
"""
from sqlmodel import Session
from app.db.engine_factory import build_readonly_engine
from app.config import settings
import logging

logger = logging.getLogger(__name__)

lakehouse_engine = build_readonly_engine(
    settings.LAKEHOUSE_DATABASE_URL,
    pool_size=3,
    max_overflow=2,
    echo=settings.DEBUG,
)


def get_lakehouse_db():
    """Dependency de FastAPI para obtener sesión del lakehouse."""
    with Session(lakehouse_engine) as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Error en sesión Lakehouse DB: {e}")
            session.rollback()
            raise
        finally:
            session.close()


def test_lakehouse_connection() -> bool:
    """Prueba de humo: valida conectividad y mide latencia básica."""
    from sqlalchemy import text
    import time

    try:
        with lakehouse_engine.connect() as connection:
            start = time.time()
            connection.execute(text("SELECT 1"))
            latency_ms = (time.time() - start) * 1000
            logger.info(f"Conexión Lakehouse DB OK ({latency_ms:.1f}ms)")
            return True
    except Exception as e:
        logger.error(f"Error de conexión a Lakehouse DB: {e}")
        return False