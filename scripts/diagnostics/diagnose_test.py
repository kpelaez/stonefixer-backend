#!/usr/bin/env python3
"""
Script de diagnóstico para el sistema de testing
Autor: StoneFixer Team
Fecha: 2025-12-18
"""

import subprocess
import sys
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.ENDC}")

def run_command(cmd, description):
    """Ejecutar comando y mostrar resultado"""
    print(f"\n{Colors.BOLD}Ejecutando: {description}{Colors.ENDC}")
    print(f"{Colors.CYAN}$ {' '.join(cmd)}{Colors.ENDC}\n")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print(f"{Colors.YELLOW}{result.stderr}{Colors.ENDC}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print_error("Comando excedió el tiempo límite")
        return False
    except Exception as e:
        print_error(f"Error ejecutando comando: {e}")
        return False

def check_file_structure():
    """Verificar estructura de archivos"""
    print_header("VERIFICACIÓN DE ESTRUCTURA DE ARCHIVOS")
    
    required_files = [
        "pytest.ini",
        "tests/__init__.py",
        "tests/conftest.py",
        "tests/unit/__init__.py",
        "tests/unit/test_tech_asset_service.py",
        "tests/integration/__init__.py",
        "tests/integration/test_tech_assets_api.py",
    ]
    
    all_good = True
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print_success(f"Encontrado: {file_path}")
        else:
            print_error(f"FALTA: {file_path}")
            all_good = False
    
    return all_good

def check_imports():
    """Verificar que los imports funcionan"""
    print_header("VERIFICACIÓN DE IMPORTS")
    
    imports_to_check = [
        ("pytest", "import pytest"),
        ("sqlmodel", "from sqlmodel import Session, SQLModel, create_engine"),
        ("fastapi.testclient", "from fastapi.testclient import TestClient"),
        ("app.models.tech_asset", "from app.models.tech_asset import TechAsset"),
        ("app.services.tech_asset_service", "from app.services.tech_asset_service import create_tech_asset"),
    ]
    
    all_good = True
    for module_name, import_statement in imports_to_check:
        try:
            exec(import_statement)
            print_success(f"Import OK: {module_name}")
        except Exception as e:
            print_error(f"Import FALLA: {module_name}")
            print(f"   Error: {e}")
            all_good = False
    
    return all_good

def main():
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║           DIAGNÓSTICO DEL SISTEMA DE TESTING                   ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")
    
    # 1. Verificar estructura de archivos
    structure_ok = check_file_structure()
    
    # 2. Verificar imports
    imports_ok = check_imports()
    
    # 3. Verificar pytest instalado
    print_header("VERIFICACIÓN DE PYTEST")
    pytest_ok = run_command(
        ["pytest", "--version"],
        "Verificar versión de pytest"
    )
    
    # 4. Listar tests disponibles
    print_header("TESTS DISPONIBLES")
    run_command(
        ["pytest", "--collect-only", "-q"],
        "Listar todos los tests"
    )
    
    # 5. Ejecutar un test simple
    print_header("EJECUTAR TEST SIMPLE")
    run_command(
        ["pytest", "tests/unit/test_tech_asset_service.py::TestCreateTechAsset::test_create_asset_success", "-v"],
        "Ejecutar un test específico"
    )
    
    # 6. Ver cobertura de un archivo
    print_header("COBERTURA DE UN ARCHIVO")
    run_command(
        ["pytest", "tests/unit/test_tech_asset_service.py", "--cov=app.services.tech_asset_service", "--cov-report=term-missing"],
        "Cobertura del servicio de tech_asset"
    )
    
    # Resumen
    print_header("RESUMEN DEL DIAGNÓSTICO")
    
    if structure_ok and imports_ok and pytest_ok:
        print_success("✨ Todo parece estar bien configurado")
        print_info("Si los tests no corren, el problema está en el código de los tests")
    else:
        print_error("Hay problemas de configuración")
        if not structure_ok:
            print("  - Faltan archivos de tests")
        if not imports_ok:
            print("  - Hay problemas con los imports")
        if not pytest_ok:
            print("  - Pytest no está instalado correctamente")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️ Diagnóstico cancelado{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()