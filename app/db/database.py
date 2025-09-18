from sqlmodel import SQLModel, create_engine, Session
from app.config import settings

def get_engine():
    """Crear el engine de base de datos con configuración apropiada según el tipo de DB"""
    database_url = settings.DATABASE_URL
    
    # Configuración específica según el tipo de base de datos
    if database_url.startswith('postgresql://') or database_url.startswith('postgres://'):
        # Configuración para PostgreSQL
        # Corregir URL si es necesario
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # Sin connect_args especiales para PostgreSQL (SSL se maneja en la URL)
        engine = create_engine(
            database_url,
            echo=settings.DEBUG,  # Mostrar queries SQL en modo debug
            pool_pre_ping=True,   # Verificar conexiones antes de usar
        )
    else:
        # Configuración para SQLite (desarrollo local)
        engine = create_engine(
            database_url, 
            connect_args={"check_same_thread": False},  # Solo para SQLite
            echo=settings.DEBUG
        )
    
    return engine

engine = get_engine()

def get_db():
    """Dependency para obtener sesión de base de datos"""
    with Session(engine) as session:
        yield session

def create_db_and_tables():
    """Crear todas las tablas definidas en los modelos"""
    SQLModel.metadata.create_all(engine)

def test_connection():
    """Función para probar la conexión a la base de datos"""
    try:
        with engine.connect() as connection:
            from sqlalchemy import text
            result = connection.execute(text("SELECT 1"))
            return True
    except Exception as e:
        print(f"Error de conexión: {e}")
        return False