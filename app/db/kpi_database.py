from sqlmodel import create_engine, Session
from app.config import settings


def get_kpi_engine():
    """Crear el engine especifico para la base de datos de KPIs (defaultdb)"""
    kpi_database_url = settings.KPI_DATABASE_URL

    if not kpi_database_url:
        raise ValueError("KPI_DATABASE_URL no esta configurado en las variables de entorno")

    # Corregir URL si es neceesario (Aiven)
    if kpi_database_url.startswith('postgres://'):
        kpi_database_url = kpi_database_url.replace('postgres://', 'postgresql://', 1)

    # Configuracion optimizada para lectura (solo consultas)
    engine = create_engine(
        kpi_database_url,       
        echo = settings.DEBUG,  # Mostrar queries SQL en modo debug
        pool_pre_ping= True,    # Verificar conexiones antes de usar
        pool_recycle=3600,      # Renovar conexiones antes de usar
        pool_size=5,            # Menor pool ya que es solo lectura
        max_overflow=10,        # Conexiones adicionales si es necesario
    )

    return engine

# Crear engine para KPIs
kpi_engine = get_kpi_engine()

def get_kpi_db():
    """Dependency para obtener conexion a la base de datos de KPIs"""
    with Session(kpi_engine) as session:
        yield session

def test_kpi_connection():
    """Funcion para probar la conexcion a la base de datos de KPIs"""
    try: 
        with kpi_engine.connect() as connection:
            from sqlalchemy import text
            result = connection.execute(text("SELECT 1"))
            return True
    except Exception as e:
        print(f"Error de conexión a KPI DB: {e}")
        return False
