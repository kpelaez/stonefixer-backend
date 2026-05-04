#!/usr/bin/env python3
"""
SCRIPT MAESTRO DE MIGRACIÓN - STONEFIXER
Ejecuta todo el proceso de diagnóstico y migración en orden
"""

import os
import sys
import subprocess
from pathlib import Path

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Imprimir header principal"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("╔" + "═" * 68 + "╗")
    print(f"║{text.center(68)}║")
    print("╚" + "═" * 68 + "╝")
    print(f"{Colors.ENDC}\n")

def print_step(step_num, title):
    """Imprimir paso del proceso"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}PASO {step_num}: {title}{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

def run_script(script_name, description):
    """Ejecutar un script Python y retornar el resultado"""
    print(f"{Colors.BLUE}▶ Ejecutando: {description}{Colors.ENDC}\n")
    
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=False,  # Mostrar output en tiempo real
            text=True
        )
        
        return result.returncode == 0
    
    except Exception as e:
        print(f"{Colors.RED}❌ Error ejecutando {script_name}: {e}{Colors.ENDC}")
        return False

def check_prerequisites():
    """Verificar que existan los archivos necesarios"""
    print_step(1, "VERIFICAR PREREQUISITOS")
    
    required_files = {
        '.env': 'Archivo de configuración',
        'alembic.ini': 'Configuración de Alembic',
        'alembic/env.py': 'Configuración de entorno de Alembic',
        'app/models': 'Directorio de modelos',
        'app/db/database.py': 'Configuración de base de datos'
    }
    
    all_ok = True
    
    for file_path, description in required_files.items():
        path = Path(file_path)
        
        if path.exists():
            print(f"{Colors.GREEN}✅ {description}: {file_path}{Colors.ENDC}")
        else:
            print(f"{Colors.RED}❌ {description}: {file_path} NO ENCONTRADO{Colors.ENDC}")
            all_ok = False
    
    if not all_ok:
        print(f"\n{Colors.RED}❌ Faltan archivos requeridos. No se puede continuar.{Colors.ENDC}")
        return False
    
    print(f"\n{Colors.GREEN}✅ Todos los archivos requeridos están presentes{Colors.ENDC}")
    return True

def verify_models():
    """Verificar imports de modelos"""
    print_step(2, "VERIFICAR IMPORTS DE MODELOS")
    
    script_path = Path("verify_alembic_imports.py")
    
    if not script_path.exists():
        print(f"{Colors.YELLOW}⚠️ Script verify_alembic_imports.py no encontrado{Colors.ENDC}")
        print(f"{Colors.BLUE}ℹ️ Saltando verificación de imports...{Colors.ENDC}")
        return True
    
    return run_script(str(script_path), "Verificación de imports de modelos")

def run_diagnostic():
    """Ejecutar diagnóstico de base de datos"""
    print_step(3, "DIAGNÓSTICO DE BASE DE DATOS")
    
    script_path = Path("alembic_diagnostic_and_migration.py")
    
    if not script_path.exists():
        print(f"{Colors.RED}❌ Script alembic_diagnostic_and_migration.py no encontrado{Colors.ENDC}")
        return False
    
    return run_script(str(script_path), "Diagnóstico completo de base de datos")

def show_next_steps():
    """Mostrar próximos pasos después de la migración"""
    print_step(4, "PRÓXIMOS PASOS")
    
    print(f"{Colors.GREEN}✅ Proceso de migración completado{Colors.ENDC}\n")
    
    print(f"{Colors.BOLD}📋 Siguientes pasos recomendados:{Colors.ENDC}\n")
    
    steps = [
        ("1", "Verificar que las tablas se crearon correctamente",
         "   python -c \"from sqlalchemy import inspect; from app.db.database import engine; "
         "print(inspect(engine).get_table_names())\""),
        
        ("2", "Iniciar el servidor FastAPI",
         "   uvicorn app.main:app --reload"),
        
        ("3", "Probar endpoints básicos",
         "   curl http://localhost:8000/"),
        
        ("4", "Crear usuario administrador inicial",
         "   python scripts/create_admin_user.py  # (si tienes este script)"),
        
        ("5", "Ejecutar tests (cuando estén disponibles)",
         "   pytest tests/"),
        
        ("6", "Continuar con implementación de roles y permisos",
         "   Revisar el decorador @require_roles")
    ]
    
    for num, desc, command in steps:
        print(f"{Colors.CYAN}{num}. {desc}{Colors.ENDC}")
        print(f"{Colors.BLUE}{command}{Colors.ENDC}\n")
    
    print(f"{Colors.YELLOW}⚠️ IMPORTANTE:{Colors.ENDC}")
    print("  • Siempre haz backup antes de migraciones en producción")
    print("  • Prueba en desarrollo antes de aplicar en producción")
    print("  • Revisa los logs después de aplicar migraciones")
    print("  • Mantén un historial de todas las migraciones aplicadas\n")

def main():
    """Función principal"""
    print_header("PROCESO COMPLETO DE MIGRACIÓN - STONEFIXER")
    
    print(f"{Colors.BLUE}Este script ejecutará los siguientes pasos:{Colors.ENDC}")
    print("  1. Verificar prerequisitos")
    print("  2. Verificar imports de modelos")
    print("  3. Ejecutar diagnóstico completo de base de datos")
    print("  4. Aplicar migraciones (si es necesario)")
    print("  5. Mostrar próximos pasos\n")
    
    response = input(f"{Colors.YELLOW}¿Deseas continuar? (s/n): {Colors.ENDC}").lower().strip()
    
    if response not in ['s', 'si', 'sí', 'y', 'yes']:
        print(f"\n{Colors.YELLOW}⚠️ Proceso cancelado por el usuario{Colors.ENDC}")
        return
    
    # Paso 1: Verificar prerequisitos
    if not check_prerequisites():
        sys.exit(1)
    
    # Paso 2: Verificar imports
    if not verify_models():
        print(f"\n{Colors.YELLOW}⚠️ Hubo problemas con los imports de modelos{Colors.ENDC}")
        print(f"{Colors.BLUE}ℹ️ Por favor, corrige los imports manualmente antes de continuar{Colors.ENDC}")
        
        response = input(f"\n{Colors.YELLOW}¿Deseas continuar de todas formas? (s/n): {Colors.ENDC}").lower().strip()
        if response not in ['s', 'si', 'sí', 'y', 'yes']:
            sys.exit(1)
    
    # Paso 3: Ejecutar diagnóstico
    if not run_diagnostic():
        print(f"\n{Colors.RED}❌ El diagnóstico falló{Colors.ENDC}")
        sys.exit(1)
    
    # Paso 4: Mostrar próximos pasos
    show_next_steps()
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}✨ ¡Proceso completado!{Colors.ENDC}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️ Proceso interrumpido por el usuario{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error inesperado: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)