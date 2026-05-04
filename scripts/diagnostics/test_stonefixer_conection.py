#!/usr/bin/env python3
"""
Script completo para probar la conexión a la base StoneFixer
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, DateTime, inspect
from datetime import datetime

# Cargar variables de entorno
load_dotenv()

def test_basic_connection():
    """Prueba básica de conexión"""
    print("🔗 Probando conexión básica...")
    
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("❌ DATABASE_URL no configurada")
            return False
        
        # Corregir URL si es necesario
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        print(f"📍 URL: {database_url[:50]}...")
        
        engine = create_engine(database_url)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1 as test"))
            test_value = result.fetchone()[0]
            
            if test_value == 1:
                print("✅ Conexión básica exitosa")
                return True
                
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

def test_database_info():
    """Obtener información de la base de datos"""
    print("\n📊 Obteniendo información de la base...")
    
    try:
        database_url = os.getenv("DATABASE_URL")
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        engine = create_engine(database_url)
        with engine.connect() as connection:
            # Nombre de la base actual
            db_result = connection.execute(text("SELECT current_database()"))
            current_db = db_result.fetchone()[0]
            print(f"📂 Base de datos actual: {current_db}")
            
            # Versión de PostgreSQL
            version_result = connection.execute(text("SELECT version()"))
            version = version_result.fetchone()[0]
            print(f"🐘 PostgreSQL: {version.split(',')[0]}")
            
            # Usuario actual
            user_result = connection.execute(text("SELECT current_user"))
            current_user = user_result.fetchone()[0]
            print(f"👤 Usuario: {current_user}")
            
            # Verificar permisos
            perms_result = connection.execute(text("""
                SELECT has_database_privilege(current_user, current_database(), 'CREATE') as can_create
            """))
            can_create = perms_result.fetchone()[0]
            print(f"🔐 Permisos de CREATE: {'✅' if can_create else '❌'}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error obteniendo info: {e}")
        return False

def test_list_tables():
    """Listar tablas existentes"""
    print("\n📋 Listando tablas existentes...")
    
    try:
        database_url = os.getenv("DATABASE_URL")
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        engine = create_engine(database_url)
        inspector = inspect(engine)
        
        tables = inspector.get_table_names()
        
        if tables:
            print(f"📊 Tablas encontradas ({len(tables)}):")
            for table in tables:
                print(f"  • {table}")
        else:
            print("📭 No hay tablas en la base de datos (está vacía)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error listando tablas: {e}")
        return False

def create_test_table():
    """Crear una tabla de prueba"""
    print("\n🔨 Creando tabla de prueba...")
    
    try:
        database_url = os.getenv("DATABASE_URL")
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        engine = create_engine(database_url)
        
        # Definir tabla de prueba
        metadata = MetaData()
        test_table = Table(
            'test_connection',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String(100), nullable=False),
            Column('message', String(255)),
            Column('created_at', DateTime, default=datetime.utcnow)
        )
        
        # Crear tabla
        metadata.create_all(engine)
        print("✅ Tabla 'test_connection' creada exitosamente")
        
        # Insertar datos de prueba
        with engine.begin() as connection:  # Usar begin() en lugar de connect()
            connection.execute(
                text("""
                    INSERT INTO test_connection (name, message, created_at) 
                    VALUES (:name, :message, :created_at)
                """),
                {
                    'name': 'StoneFixer Test',
                    'message': 'Conexión exitosa a base StoneFixer',
                    'created_at': datetime.now()
                }
            )
            # No necesitas commit() con begin(), se hace automáticamente
            print("✅ Datos de prueba insertados")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creando tabla: {e}")
        return False

def test_crud_operations():
    """Probar operaciones CRUD en la tabla de prueba"""
    print("\n🔄 Probando operaciones CRUD...")
    
    try:
        database_url = os.getenv("DATABASE_URL")
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        engine = create_engine(database_url)
        
        with engine.begin() as connection:  # Usar begin() para transacciones automáticas
            # CREATE - Insertar más datos
            connection.execute(
                text("""
                    INSERT INTO test_connection (name, message) 
                    VALUES ('Test INSERT', 'Operación CREATE exitosa')
                """)
            )
            
            # UPDATE - Actualizar datos
            connection.execute(
                text("""
                    UPDATE test_connection 
                    SET message = 'Operación UPDATE exitosa' 
                    WHERE name = 'Test INSERT'
                """)
            )
            print("📝 CREATE y UPDATE: Operaciones completadas")
        
        # READ - Leer datos (en transacción separada)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT * FROM test_connection"))
            rows = result.fetchall()
            print(f"📖 READ: Encontrados {len(rows)} registros")
            
            for row in rows:
                print(f"  • ID: {row[0]}, Nombre: {row[1]}, Mensaje: {row[2]}")
        
        print("✅ Operaciones CRUD completadas exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error en operaciones CRUD: {e}")
        return False

def cleanup_test_table():
    """Limpiar tabla de prueba (opcional)"""
    print("\n🧹 ¿Deseas eliminar la tabla de prueba? (y/n): ", end="")
    
    try:
        response = input().lower().strip()
        
        if response in ['y', 'yes', 'sí', 's']:
            database_url = os.getenv("DATABASE_URL")
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
            engine = create_engine(database_url)
            
            with engine.begin() as connection:  # Usar begin() para transacciones automáticas
                connection.execute(text("DROP TABLE IF EXISTS test_connection"))
                print("✅ Tabla de prueba eliminada")
        else:
            print("ℹ️ Tabla de prueba conservada")
        
        return True
        
    except Exception as e:
        print(f"❌ Error limpiando tabla: {e}")
        return False

def main():
    print("🧪 Prueba Completa de Conexión a StoneFixer")
    print("=" * 50)
    
    # Test 1: Conexión básica
    if not test_basic_connection():
        print("❌ Falló la conexión básica")
        return
    
    # Test 2: Información de la base
    if not test_database_info():
        print("❌ Falló obteniendo información")
        return
    
    # Test 3: Listar tablas
    if not test_list_tables():
        print("❌ Falló listando tablas")
        return
    
    # Test 4: Crear tabla de prueba
    if not create_test_table():
        print("❌ Falló creando tabla de prueba")
        return
    
    # Test 5: Operaciones CRUD
    if not test_crud_operations():
        print("❌ Falló operaciones CRUD")
        return
    
    # Test 6: Limpiar (opcional)
    cleanup_test_table()
    
    print("\n🎉 ¡Todas las pruebas completadas exitosamente!")
    print("✅ La base StoneFixer está lista para usar")
    print("\n👉 Próximos pasos:")
    print("   1. alembic revision --autogenerate -m 'Initial StoneFixer migration'")
    print("   2. alembic upgrade head")

if __name__ == "__main__":
    main()