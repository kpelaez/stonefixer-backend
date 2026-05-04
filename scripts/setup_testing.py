"""
Script para configurar el sistema de testing en StoneFixer
Autor: StoneFixer Team
Fecha: 2025-12-18
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    HEADER = '\033[94m'

def print_header(text):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.ENDC}")

def create_test_directories():
    """Crear estructura de directorios para tests"""
    print_header("PASO 1: CREAR ESTRUCTURA DE DIRECTORIOS")
    
    directories = [
        "tests",
        "tests/unit",
        "tests/integration",
        "tests/e2e"
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print_success(f"Directorio creado: {directory}")
        else:
            print_info(f"Directorio ya existe: {directory}")
        
        # Crear __init__.py en cada directorio
        init_file = dir_path / "__init__.py"
        if not init_file.exists():
            init_file.write_text("# Tests\n")
            print_success(f"Archivo creado: {directory}/__init__.py")
    
    return True

def copy_test_files():
    """Copiar archivos de test a sus ubicaciones"""
    print_header("PASO 2: COPIAR ARCHIVOS DE TEST")
    
    files_to_copy = [
        ("pytest.ini", "pytest.ini"),
        ("conftest.py", "tests/conftest.py"),
        ("test_tech_asset_service.py", "tests/unit/test_tech_asset_service.py"),
        ("test_tech_assets_api.py", "tests/integration/test_tech_assets_api.py"),
    ]
    
    success_count = 0
    
    for source, destination in files_to_copy:
        source_path = Path(source)
        dest_path = Path(destination)
        
        if not source_path.exists():
            print_error(f"Archivo fuente no encontrado: {source}")
            continue
        
        try:
            # Crear backup si existe
            if dest_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = dest_path.with_suffix(f".backup_{timestamp}{dest_path.suffix}")
                shutil.copy2(dest_path, backup_path)
                print_warning(f"Backup creado: {backup_path}")
            
            # Copiar archivo
            shutil.copy2(source_path, dest_path)
            print_success(f"Copiado: {source} → {destination}")
            success_count += 1
            
        except Exception as e:
            print_error(f"Error copiando {source}: {e}")
    
    return success_count == len(files_to_copy)

def create_requirements_test():
    """Crear archivo requirements-test.txt"""
    print_header("PASO 3: CREAR REQUIREMENTS-TEST.TXT")
    
    requirements = """# Testing dependencies for StoneFixer
# Install with: pip install -r requirements-test.txt

# Core testing framework
pytest==7.4.3
pytest-cov==4.1.0

# Async support
pytest-asyncio==0.21.1

# Parallel execution
pytest-xdist==3.5.0

# Timeout support
pytest-timeout==2.2.0

# HTTP client for API tests
httpx==0.25.2

# Test data generation
faker==20.1.0

# Mocking
pytest-mock==3.12.0
"""
    
    try:
        req_file = Path("requirements-test.txt")
        
        if req_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = req_file.with_suffix(f".backup_{timestamp}.txt")
            shutil.copy2(req_file, backup)
            print_warning(f"Backup creado: {backup}")
        
        req_file.write_text(requirements)
        print_success("Archivo requirements-test.txt creado")
        return True
        
    except Exception as e:
        print_error(f"Error creando requirements-test.txt: {e}")
        return False

def install_dependencies():
    """Instalar dependencias de test"""
    print_header("PASO 4: INSTALAR DEPENDENCIAS")
    
    print_info("Para instalar las dependencias, ejecuta:")
    print(f"{Colors.CYAN}pip install -r requirements-test.txt{Colors.ENDC}\n")
    
    response = input(f"{Colors.YELLOW}¿Deseas instalar ahora? (s/n): {Colors.ENDC}").lower().strip()
    
    if response in ['s', 'si', 'sí', 'y', 'yes']:
        import subprocess
        try:
            print_info("Instalando dependencias...")
            result = subprocess.run(
                ["pip", "install", "-r", "requirements-test.txt"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print_success("Dependencias instaladas correctamente")
                return True
            else:
                print_error("Error instalando dependencias")
                print(result.stderr)
                return False
                
        except Exception as e:
            print_error(f"Error: {e}")
            return False
    else:
        print_info("Saltando instalación de dependencias")
        return True

def run_test_check():
    """Verificar que pytest funciona"""
    print_header("PASO 5: VERIFICAR INSTALACIÓN DE PYTEST")
    
    import subprocess
    
    try:
        # Verificar versión de pytest
        result = subprocess.run(
            ["pytest", "--version"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print_success(f"Pytest instalado: {result.stdout.strip()}")
            
            # Listar tests sin ejecutarlos
            print_info("\nTests disponibles:")
            result = subprocess.run(
                ["pytest", "--collect-only", "-q"],
                capture_output=True,
                text=True
            )
            
            print(f"{Colors.BLUE}{result.stdout}{Colors.ENDC}")
            return True
        else:
            print_error("Pytest no está instalado correctamente")
            return False
            
    except FileNotFoundError:
        print_error("Pytest no encontrado. Instala con: pip install pytest")
        return False
    except Exception as e:
        print_error(f"Error verificando pytest: {e}")
        return False

def show_next_steps():
    """Mostrar próximos pasos"""
    print_header("PRÓXIMOS PASOS")
    
    print(f"{Colors.BOLD}1. Ejecutar tests:{Colors.ENDC}")
    print(f"   {Colors.CYAN}pytest{Colors.ENDC}")
    print(f"   {Colors.CYAN}pytest -v{Colors.ENDC}  # Modo verbose")
    print(f"   {Colors.CYAN}pytest -m unit{Colors.ENDC}  # Solo unitarios")
    print()
    
    print(f"{Colors.BOLD}2. Ver cobertura de código:{Colors.ENDC}")
    print(f"   {Colors.CYAN}pytest --cov=app --cov-report=html{Colors.ENDC}")
    print(f"   {Colors.CYAN}open htmlcov/index.html{Colors.ENDC}  # Ver reporte")
    print()
    
    print(f"{Colors.BOLD}3. Ejecutar tests específicos:{Colors.ENDC}")
    print(f"   {Colors.CYAN}pytest tests/unit/test_tech_asset_service.py{Colors.ENDC}")
    print(f"   {Colors.CYAN}pytest tests/integration/test_tech_assets_api.py{Colors.ENDC}")
    print()
    
    print(f"{Colors.BOLD}4. Ver documentación:{Colors.ENDC}")
    print(f"   {Colors.CYAN}TESTING_GUIDE.md{Colors.ENDC} - Guía completa de testing")
    print(f"   {Colors.CYAN}TECH_ASSETS_ANALYSIS.md{Colors.ENDC} - Análisis del módulo")
    print()

def main():
    """Función principal"""
    print(f"{Colors.HEADER}{Colors.BOLD}")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║          CONFIGURAR SISTEMA DE TESTING - STONEFIXER           ║")
    print("║                  Módulo: Activos Tecnológicos                  ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}")
    
    print_info("Este script configurará el sistema de testing completo:")
    print("  1. Crear directorios de tests")
    print("  2. Copiar archivos de configuración y tests")
    print("  3. Crear requirements-test.txt")
    print("  4. Instalar dependencias (opcional)")
    print("  5. Verificar instalación")
    print()
    
    response = input(f"{Colors.YELLOW}¿Deseas continuar? (s/n): {Colors.ENDC}").lower().strip()
    
    if response not in ['s', 'si', 'sí', 'y', 'yes']:
        print_warning("Operación cancelada")
        return
    
    # Ejecutar pasos
    if not create_test_directories():
        print_error("Error creando directorios")
        return
    
    if not copy_test_files():
        print_warning("Algunos archivos no se pudieron copiar")
    
    if not create_requirements_test():
        print_error("Error creando requirements-test.txt")
        return
    
    install_dependencies()  # Opcional
    
    run_test_check()
    
    # Resumen
    print_header("RESUMEN")
    print_success("✨ Sistema de testing configurado correctamente")
    
    show_next_steps()
    
    print()
    print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.CYAN}📚 Documentación disponible:{Colors.ENDC}")
    print(f"{Colors.CYAN}   - TESTING_GUIDE.md{Colors.ENDC}")
    print(f"{Colors.CYAN}   - TECH_ASSETS_ANALYSIS.md{Colors.ENDC}")
    print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️ Operación cancelada{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()