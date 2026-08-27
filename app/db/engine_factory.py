"""
app/db/engine_factory.py

Factory centralizada para crear engines de PostgreSQL (Aiven u otro proveedor).
Evita duplicar la configuración de pool/timeouts en cada archivo *_database.py
cuando se agrega un nuevo origen de datos externo (KPI, Executive Dashboard, etc).

Uso:
    from app.db.engine_factory import build_readonly_engine

    executive_engine = build_readonly_engine(
        settings.EXECUTIVE_DASHBOARD_DATABASE_URL,
        pool_size=5,
        max_overflow=5,
    )
"""
from sqlmodel import create_engine
from sqlalchemy.engine import Engine
import logging

logger = logging.getLogger(__name__)


def build_readonly_engine(
    database_url: str,
    *,
    pool_size: int = 5,
    max_overflow: int = 5,
    pool_recycle: int = 1800,
    pool_timeout: int = 30,
    connect_timeout: int = 10,
    statement_timeout_ms: int = 30_000,
    echo: bool = False,
) -> Engine:
    """
    Crea un engine de SQLAlchemy/SQLModel optimizado para consumir una base
    PostgreSQL externa (Aiven) en modo solo lectura.

    IMPORTANTE - antes de subir a producción:
    1. El usuario de la connection string DEBE ser un rol de solo lectura
       (GRANT SELECT únicamente), nunca el usuario admin de la instancia.
    2. pool_size + max_overflow de ESTE engine, sumado al de los demás
       engines de la app (database.py, kpi_database.py, etc), no debe
       superar el "connection limit" configurado para el usuario en Aiven.
       Con varios engines corriendo a la vez, es fácil chocar ese límite
       si cada uno reserva 10-20 conexiones "por las dudas".
    3. statement_timeout evita que una query mal armada contra una base
       de producción ajena quede colgada indefinidamente y agote el pool.

    Args:
        database_url: connection string (postgres:// o postgresql://)
        pool_size: conexiones persistentes en el pool
        max_overflow: conexiones extra permitidas en picos de demanda
        pool_recycle: segundos antes de reciclar una conexión (Aiven cierra
                      conexiones idle, conviene < al timeout del proveedor)
        pool_timeout: segundos que espera un request para obtener conexión
                      del pool antes de fallar
        connect_timeout: segundos para el handshake inicial de conexión
        statement_timeout_ms: corta cualquier query que tarde más que esto
        echo: loggear SQL generado (solo para debug local)

    Returns:
        Engine configurado, listo para usarse con Session(engine)
    """
    if not database_url:
        raise ValueError(
            "database_url vacío. Verificá que la variable de entorno "
            "correspondiente esté seteada en .env / en el entorno de despliegue."
        )

    # Aiven a veces entregan postgres:// en vez
    # de postgresql://, que SQLAlchemy 2.x ya no acepta directamente.
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    engine = create_engine(
        database_url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,  # valida la conexión antes de usarla (evita "stale connection" con Aiven)
        pool_timeout=pool_timeout,
        connect_args={
            "connect_timeout": connect_timeout,
            "options": f"-c statement_timeout={statement_timeout_ms}",
        },
    )

    logger.info(
        "Engine creado (pool_size=%s, max_overflow=%s, statement_timeout=%sms)",
        pool_size,
        max_overflow,
        statement_timeout_ms,
    )

    return engine