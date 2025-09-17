#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def test_driver():
    """Probar que el driver de PostgreSQL esté instalado"""
    try:
        import psycopg2
        print("✅ psycopg2 está instalado")
        return True
    except ImportError:
        try:
            import psycopg
            print("✅ psycopg3 está instalado")
            return True
        except ImportError:
            print("❌ No hay driver de PostgreSQL instalado")
            print("👉 Ejecuta: pip install psycopg2-binary")
            return False

def test_env_config():
    """Probar configuración de variables de entorno"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ DATABASE_URL no configurada")
        print("👉 Crea un archivo .env con:")
        print('DATABASE_URL="postgresql://user:pass@host:port/db?sslmode=require"')
        return False
    
    print(f"✅ DATABASE_URL configurada: {database_url[:50]}...")
    
    if database_url.startswith('sqlite'):
        print("⚠️ Aún estás usando SQLite, cambia a PostgreSQL")
        return False
        
    if database_url.startswith('postgresql'):
        print("✅ Configuración PostgreSQL detectada")
        return True
    
    return True

def test_connection():
    """Probar conexión real a la base de datos"""
    try:
        from sqlalchemy import create_engine, text
        database_url = os.getenv("DATABASE_URL")
        
        engine = create_engine(database_url)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            if result.fetchone()[0] == 1:
                print("✅ Conexión a la base de datos exitosa")
                return True
                
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        print("👉 Verifica tus credenciales y que el servidor esté accesible")
        return False

def main():
    print("🧪 Probando configuración de PostgreSQL")
    print("=" * 50)
    
    # Test 1: Driver
    if not test_driver():
        sys.exit(1)
    
    # Test 2: Configuración
    if not test_env_config():
        sys.exit(1)
    
    # Test 3: Conexión
    if not test_connection():
        sys.exit(1)
    
    print("\n🎉 ¡Todo configurado correctamente!")
    print("👉 Ahora puedes ejecutar: alembic revision --autogenerate -m 'Initial migration'")

if __name__ == "__main__":
    main()