from sqlmodel import create_engine, Session
from app.config import settings
import logging

logger = logging.getLogger(__name__)

def get_kpi_engine():
    """
    Crear el engine optimizado para la base de datos de KPIs (Aiven)
    """
    kpi_database_url = settings.KPI_DATABASE_URL

    if not kpi_database_url:
        raise ValueError("KPI_DATABASE_URL no está configurado en las variables de entorno")

    # Corregir URL si es necesario (Aiven)
    if kpi_database_url.startswith('postgres://'):
        kpi_database_url = kpi_database_url.replace('postgres://', 'postgresql://', 1)

    # CONFIGURACIÓN OPTIMIZADA PARA AIVEN
    engine = create_engine(
        kpi_database_url,       
        echo=settings.DEBUG,  # Mostrar queries SQL en modo debug
        
        # === OPTIMIZACIONES DE RENDIMIENTO ===
        
        # Pool de conexiones optimizado para Aiven
        pool_size=10,              # Aumentado de 5 a 10
        max_overflow=20,           # Aumentado de 10 a 20  
        pool_recycle=1800,         # Reducido de 3600 a 30min (mejor para Aiven)
        pool_pre_ping=True,        # Verificar conexiones antes de usar
        
        # Timeouts optimizados para conexiones remotas
        pool_timeout=30,           # Timeout para obtener conexión del pool
        
        # Configuración específica para PostgreSQL/Aiven
        connect_args={
            "connect_timeout": 10,           # Timeout de conexión inicial
            "command_timeout": 30,           # Timeout para comandos SQL
            "server_settings": {
                "application_name": "stonefixer_dashboard",
                "tcp_keepalives_idle": "300",     # Keep alive cada 5 min
                "tcp_keepalives_interval": "30",   # Intervalo entre keep alives
                "tcp_keepalives_count": "3",       # Número de intentos
            }
        }
    )

    return engine

# Crear engine para KPIs con configuración optimizada
kpi_engine = get_kpi_engine()

def get_kpi_db():
    """
    Dependency optimizado para obtener conexión a la base de datos de KPIs
    """
    with Session(kpi_engine) as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Error en sesión KPI: {e}")
            session.rollback()
            raise
        finally:
            session.close()

def test_kpi_connection():
    """
    Función mejorada para probar la conexión a la base de datos de KPIs
    """
    try: 
        with kpi_engine.connect() as connection:
            from sqlalchemy import text
            import time
            
            start_time = time.time()
            result = connection.execute(text("SELECT 1"))
            end_time = time.time()
            
            latency = (end_time - start_time) * 1000  # en milisegundos
            
            logger.info(f"Conexión KPI exitosa. Latencia: {latency:.2f}ms")
            return {
                "success": True,
                "latency_ms": latency,
                "pool_size": kpi_engine.pool.size(),
                "checked_out": kpi_engine.pool.checkedout()
            }
            
    except Exception as e:
        logger.error(f"Error de conexión a KPI DB: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# === FUNCIONES DE MONITOREO ===

def get_connection_pool_stats():
    """
    Obtener estadísticas del pool de conexiones para monitoreo
    """
    try:
        pool = kpi_engine.pool
        
        return {
            "pool_size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "checked_in": pool.checkedin(),
            "pool_timeout": pool._timeout,
            "pool_recycle": pool._recycle
        }
    except Exception as e:
        logger.error(f"Error obteniendo stats del pool: {e}")
        return {"error": str(e)}

def warm_up_connections():
    """
    Pre-calentar el pool de conexiones al inicio de la aplicación
    """
    try:
        connections = []
        
        # Crear conexiones hasta llenar el pool
        for i in range(kpi_engine.pool.size()):
            try:
                conn = kpi_engine.connect()
                connections.append(conn)
                logger.info(f"Conexión {i+1} pre-calentada")
            except Exception as e:
                logger.warning(f"Error pre-calentando conexión {i+1}: {e}")
                break
        
        # Cerrar todas las conexiones para devolverlas al pool
        for conn in connections:
            conn.close()
            
        logger.info(f"Pool de conexiones KPI pre-calentado con {len(connections)} conexiones")
        
    except Exception as e:
        logger.error(f"Error calentando pool de conexiones: {e}")

# === CONTEXT MANAGER PARA TRANSACCIONES OPTIMIZADAS ===

from contextlib import contextmanager

@contextmanager
def get_kpi_connection():
    """
    Context manager optimizado para obtener conexiones KPI
    """
    connection = None
    try:
        connection = kpi_engine.connect()
        yield connection
    except Exception as e:
        logger.error(f"Error en conexión KPI: {e}")
        raise
    finally:
        if connection:
            connection.close()