#!/usr/bin/env python3
"""
Script completo para diagnosticar y aplicar migraciones de Alembic
Autor: StoneFixer Team
Fecha: 2025-12-17
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
import subprocess
from typing import Tuple, List

# Cargar variables de entorno
load_dotenv()

class Colors:
    """Colores ANSI para output en consola"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_section(title: str):
    """Imprimir sección con formato"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}{title}{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

def print_success(message: str):
    """Imprimir mensaje de éxito"""
    print(f"{Colors.GREEN}✅ {message}{Colors.ENDC}")

def print_warning(message: str):
    """Imprimir mensaje de advertencia"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.ENDC}")

def print_error(message: str):
    """Imprimir mensaje de error"""
    print(f"{Colors.RED}❌ {message}{Colors.ENDC}")

def print_info(message: str):
    """Imprimir mensaje informativo"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.ENDC}")

def get_database_engine() -> Tuple[Engine, str]:
    """Obtener engine de base de datos"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        raise ValueError("DATABASE_URL no está configurada en .env")
    
    # Corregir URL si es necesario (Heroku compatibility)
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    engine = create_engine(database_url, echo=False)
    
    return engine, database_url

def test_database_connection() -> bool:
    """Test 1: Verificar conexión a la base de datos"""
    print_section("TEST 1: CONEXIÓN A LA BASE DE DATOS")
    
    try:
        engine, database_url = get_database_engine()
        
        # Mostrar info de conexión (ocultando credenciales)
        url_parts = database_url.split('@')
        if len(url_parts) > 1:
            safe_url = f"postgresql://****:****@{url_parts[1]}"
        else:
            safe_url = database_url[:50] + "..."
        
        print_info(f"URL de conexión: {safe_url}")
        
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print_success("Conexión exitosa a PostgreSQL")
            print_info(f"Versión: {version.split(',')[0]}")
            
            # Obtener nombre de la base de datos actual
            result = connection.execute(text("SELECT current_database()"))
            db_name = result.fetchone()[0]
            print_info(f"Base de datos: {db_name}")
        
        return True
        
    except Exception as e:
        print_error(f"Error de conexión: {e}")
        return False

def check_alembic_version_table() -> Tuple[bool, str]:
    """Test 2: Verificar si existe la tabla alembic_version"""
    print_section("TEST 2: TABLA DE VERSIONES DE ALEMBIC")
    
    try:
        engine, _ = get_database_engine()
        inspector = inspect(engine)
        
        # Verificar si existe la tabla alembic_version
        tables = inspector.get_table_names()
        
        if 'alembic_version' in tables:
            print_success("Tabla 'alembic_version' existe")
            
            # Obtener versión actual
            with engine.connect() as connection:
                result = connection.execute(text("SELECT version_num FROM alembic_version"))
                version = result.fetchone()
                
                if version:
                    current_version = version[0]
                    print_info(f"Versión actual de migración: {current_version}")
                    return True, current_version
                else:
                    print_warning("La tabla existe pero no tiene versión registrada")
                    return True, ""
        else:
            print_warning("Tabla 'alembic_version' NO existe")
            print_info("Esto indica que nunca se corrieron migraciones")
            return False, ""
            
    except Exception as e:
        print_error(f"Error verificando tabla de versiones: {e}")
        return False, ""

def check_existing_tables() -> List[str]:
    """Test 3: Verificar tablas existentes en la base de datos"""
    print_section("TEST 3: TABLAS EXISTENTES EN LA BASE DE DATOS")
    
    try:
        engine, _ = get_database_engine()
        inspector = inspect(engine)
        
        tables = inspector.get_table_names()
        
        if tables:
            print_success(f"Se encontraron {len(tables)} tablas:")
            for table in sorted(tables):
                print(f"  📋 {table}")
        else:
            print_warning("No se encontraron tablas en la base de datos")
        
        return tables
        
    except Exception as e:
        print_error(f"Error listando tablas: {e}")
        return []

def check_expected_tables(existing_tables: List[str]) -> dict:
    """Test 4: Verificar si existen las tablas esperadas del modelo"""
    print_section("TEST 4: VERIFICACIÓN DE TABLAS DEL MODELO")
    
    # Tablas esperadas según los modelos de StoneFixer
    expected_tables = {
        'user': 'Usuarios del sistema',
        'user_roles': 'Roles de usuarios',
        'tech_asset': 'Activos tecnológicos',
        'asset_assignments': 'Asignaciones de activos',
        'asset_maintenances': 'Mantenimientos de activos'
    }
    
    results = {}
    
    for table, description in expected_tables.items():
        exists = table in existing_tables
        results[table] = exists
        
        if exists:
            print_success(f"{table}: {description}")
        else:
            print_error(f"{table}: {description} - NO EXISTE")
    
    missing_count = sum(1 for exists in results.values() if not exists)
    
    if missing_count == 0:
        print_success("\n✨ Todas las tablas esperadas existen")
    else:
        print_warning(f"\n⚠️ Faltan {missing_count} tablas por crear")
    
    return results

def check_alembic_migrations() -> List[str]:
    """Test 5: Verificar archivos de migración de Alembic"""
    print_section("TEST 5: ARCHIVOS DE MIGRACIÓN DE ALEMBIC")
    
    migrations_dir = Path("alembic/versions")
    
    if not migrations_dir.exists():
        print_error(f"Directorio de migraciones no existe: {migrations_dir}")
        return []
    
    migration_files = list(migrations_dir.glob("*.py"))
    migration_files = [f for f in migration_files if f.name != "__pycache__"]
    
    if migration_files:
        print_success(f"Se encontraron {len(migration_files)} archivo(s) de migración:")
        for migration in sorted(migration_files):
            print(f"  📄 {migration.name}")
    else:
        print_warning("No se encontraron archivos de migración")
    
    return [f.name for f in migration_files]

def run_alembic_command(command: str, description: str) -> Tuple[bool, str]:
    """Ejecutar un comando de Alembic"""
    print_info(f"Ejecutando: {description}")
    print_info(f"Comando: alembic {command}")
    
    try:
        result = subprocess.run(
            f"alembic {command}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print_success(f"{description} - Exitoso")
            return True, result.stdout
        else:
            print_error(f"{description} - Falló")
            print_error(f"Error: {result.stderr}")
            return False, result.stderr
            
    except subprocess.TimeoutExpired:
        print_error(f"{description} - Timeout (>60s)")
        return False, "Timeout"
    except Exception as e:
        print_error(f"{description} - Error: {e}")
        return False, str(e)

def apply_migrations():
    """Test 6: Aplicar migraciones de Alembic"""
    print_section("TEST 6: APLICAR MIGRACIONES")
    
    print_info("Esto aplicará todas las migraciones pendientes a la base de datos")
    
    # Primero verificar el estado actual
    success, output = run_alembic_command("current", "Verificar versión actual")
    
    if success:
        print(f"\n{output}")
    
    # Aplicar migraciones
    print("\n" + "="*50)
    response = input(f"\n{Colors.YELLOW}¿Deseas aplicar las migraciones ahora? (s/n): {Colors.ENDC}").lower().strip()
    
    if response in ['s', 'si', 'sí', 'y', 'yes']:
        success, output = run_alembic_command("upgrade head", "Aplicar migraciones")
        
        if success:
            print(f"\n{output}")
            print_success("\n🎉 Migraciones aplicadas exitosamente")
            return True
        else:
            return False
    else:
        print_info("Migraciones NO aplicadas (decisión del usuario)")
        return False

def verify_migration_results():
    """Test 7: Verificar resultados después de migración"""
    print_section("TEST 7: VERIFICACIÓN POST-MIGRACIÓN")
    
    try:
        # Verificar tablas nuevamente
        existing_tables = check_existing_tables()
        
        # Verificar tabla de versiones
        has_version_table, current_version = check_alembic_version_table()
        
        # Verificar tablas esperadas
        table_status = check_expected_tables(existing_tables)
        
        all_tables_exist = all(table_status.values())
        
        if all_tables_exist and has_version_table:
            print_success("\n✨ La base de datos está completamente migrada")
            return True
        else:
            print_warning("\n⚠️ Algunas tablas todavía faltan")
            return False
            
    except Exception as e:
        print_error(f"Error en verificación: {e}")
        return False

def main():
    """Función principal"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     DIAGNÓSTICO Y MIGRACIÓN DE ALEMBIC - STONEFIXER DB        ║")
    print("║                    Módulo: Activos Tecnológicos                ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")
    
    # Test 1: Conexión
    if not test_database_connection():
        print_error("\n❌ No se pudo conectar a la base de datos")
        print_info("Por favor verifica tu archivo .env y la configuración de DATABASE_URL")
        sys.exit(1)
    
    # Test 2: Verificar tabla de versiones
    has_version_table, current_version = check_alembic_version_table()
    
    # Test 3: Listar tablas existentes
    existing_tables = check_existing_tables()
    
    # Test 4: Verificar tablas esperadas
    table_status = check_expected_tables(existing_tables)
    
    # Test 5: Verificar archivos de migración
    migration_files = check_alembic_migrations()
    
    # Análisis de situación
    print_section("ANÁLISIS DE SITUACIÓN")
    
    all_tables_exist = all(table_status.values())
    has_migrations = len(migration_files) > 0
    
    if all_tables_exist and has_version_table:
        print_success("✨ La base de datos ya está migrada correctamente")
        print_info(f"Versión actual: {current_version}")
        print_info("No es necesario aplicar migraciones")
        
    elif has_migrations and not all_tables_exist:
        print_warning("⚠️ Tienes archivos de migración pero las tablas no están creadas")
        print_info("Es necesario aplicar las migraciones")
        
        # Test 6: Aplicar migraciones
        if apply_migrations():
            # Test 7: Verificar resultados
            verify_migration_results()
        
    elif not has_migrations:
        print_warning("⚠️ No hay archivos de migración creados")
        print_info("Necesitas crear una migración inicial")
        print("\nPasos a seguir:")
        print("1. Verifica que tus modelos estén correctos en app/models/")
        print("2. Ejecuta: alembic revision --autogenerate -m 'Initial migration'")
        print("3. Revisa el archivo de migración generado")
        print("4. Ejecuta: alembic upgrade head")
    
    else:
        print_info("Estado: Listo para migrar")
    
    # Resumen final
    print_section("RESUMEN FINAL")
    print(f"{'Conexión a BD:':<30} {Colors.GREEN}✅ OK{Colors.ENDC}")
    print(f"{'Tabla alembic_version:':<30} {Colors.GREEN if has_version_table else Colors.RED}{'✅ OK' if has_version_table else '❌ NO EXISTE'}{Colors.ENDC}")
    print(f"{'Tablas del modelo:':<30} {Colors.GREEN if all_tables_exist else Colors.YELLOW}{'✅ TODAS' if all_tables_exist else '⚠️ INCOMPLETAS'}{Colors.ENDC}")
    print(f"{'Archivos de migración:':<30} {Colors.GREEN if has_migrations else Colors.RED}{'✅ SI' if has_migrations else '❌ NO'}{Colors.ENDC}")
    
    print("\n" + "="*70)
    
    # Próximos pasos recomendados
    if not all_tables_exist:
        print(f"\n{Colors.YELLOW}📋 PRÓXIMOS PASOS RECOMENDADOS:{Colors.ENDC}")
        print("1. Ejecutar este script nuevamente y aplicar migraciones")
        print("2. Verificar que todas las tablas se crearon correctamente")
        print("3. Probar la conexión desde tu aplicación FastAPI")
        print("4. Crear usuarios de prueba en la base de datos")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️ Operación cancelada por el usuario{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error inesperado: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)