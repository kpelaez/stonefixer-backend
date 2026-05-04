#!/usr/bin/env python3
"""
Verificar que todos los modelos SQLModel estén correctamente importados en alembic/env.py
"""

import os
import sys
import ast
from pathlib import Path
from typing import List, Set, Tuple

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def find_sqlmodel_classes(file_path: Path) -> Set[str]:
    """Encontrar todas las clases que heredan de SQLModel en un archivo"""
    classes = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Verificar si hereda de SQLModel
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == 'SQLModel':
                        classes.add(node.name)
                    elif isinstance(base, ast.Attribute) and base.attr == 'SQLModel':
                        classes.add(node.name)
        
        return classes
    
    except Exception as e:
        print(f"{Colors.RED}Error leyendo {file_path}: {e}{Colors.ENDC}")
        return set()

def scan_models_directory() -> dict:
    """Escanear el directorio de modelos y encontrar todas las clases SQLModel"""
    models_dir = Path("app/models")
    
    if not models_dir.exists():
        print(f"{Colors.RED}❌ Directorio app/models no existe{Colors.ENDC}")
        return {}
    
    model_files = {}
    
    for py_file in models_dir.glob("*.py"):
        if py_file.name == "__init__.py" or py_file.name.startswith("_"):
            continue
        
        classes = find_sqlmodel_classes(py_file)
        if classes:
            model_files[py_file.name] = classes
    
    return model_files

def get_imported_models_from_env() -> Set[str]:
    """Obtener modelos importados en alembic/env.py"""
    env_file = Path("alembic/env.py")
    
    if not env_file.exists():
        print(f"{Colors.RED}❌ Archivo alembic/env.py no existe{Colors.ENDC}")
        return set()
    
    imported_models = set()
    
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith('app.models'):
                    for alias in node.names:
                        imported_models.add(alias.name)
        
        return imported_models
    
    except Exception as e:
        print(f"{Colors.RED}Error leyendo alembic/env.py: {e}{Colors.ENDC}")
        return set()

def generate_import_statements(model_files: dict) -> List[str]:
    """Generar statements de importación para todos los modelos"""
    imports = []
    
    for file_name, classes in sorted(model_files.items()):
        module_name = file_name.replace('.py', '')
        for class_name in sorted(classes):
            imports.append(f"from app.models.{module_name} import {class_name}")
    
    return imports

def main():
    """Función principal"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}╔══════════════════════════════════════════════════════════╗{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}║  VERIFICACIÓN DE MODELOS EN ALEMBIC/ENV.PY              ║{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}╚══════════════════════════════════════════════════════════╝{Colors.ENDC}\n")
    
    # 1. Escanear modelos en app/models
    print(f"{Colors.BOLD}📁 Escaneando directorio app/models...{Colors.ENDC}")
    model_files = scan_models_directory()
    
    if not model_files:
        print(f"{Colors.YELLOW}⚠️  No se encontraron modelos SQLModel{Colors.ENDC}")
        return
    
    # Obtener todos los modelos encontrados
    all_models = set()
    for classes in model_files.values():
        all_models.update(classes)
    
    print(f"{Colors.GREEN}✅ Se encontraron {len(all_models)} modelo(s) en {len(model_files)} archivo(s):{Colors.ENDC}\n")
    
    for file_name, classes in sorted(model_files.items()):
        print(f"  📄 {file_name}")
        for class_name in sorted(classes):
            print(f"     └─ {class_name}")
    
    # 2. Verificar imports en alembic/env.py
    print(f"\n{Colors.BOLD}📋 Verificando imports en alembic/env.py...{Colors.ENDC}")
    imported_models = get_imported_models_from_env()
    
    if imported_models:
        print(f"{Colors.GREEN}✅ Modelos importados en alembic/env.py:{Colors.ENDC}")
        for model in sorted(imported_models):
            print(f"  ✓ {model}")
    else:
        print(f"{Colors.YELLOW}⚠️  No se encontraron imports de modelos{Colors.ENDC}")
    
    # 3. Comparar y encontrar modelos faltantes
    print(f"\n{Colors.BOLD}🔍 Análisis de diferencias...{Colors.ENDC}")
    
    missing_models = all_models - imported_models
    extra_models = imported_models - all_models
    
    if not missing_models and not extra_models:
        print(f"{Colors.GREEN}✅ ¡Perfecto! Todos los modelos están correctamente importados{Colors.ENDC}")
        return
    
    if missing_models:
        print(f"\n{Colors.RED}❌ MODELOS FALTANTES en alembic/env.py:{Colors.ENDC}")
        for model in sorted(missing_models):
            print(f"  ✗ {model}")
    
    if extra_models:
        print(f"\n{Colors.YELLOW}⚠️  MODELOS EXTRA en alembic/env.py (puede que ya no existan):{Colors.ENDC}")
        for model in sorted(extra_models):
            print(f"  ? {model}")
    
    # 4. Generar código de importación correcto
    if missing_models:
        print(f"\n{Colors.BOLD}📝 Código de importación sugerido para alembic/env.py:{Colors.ENDC}")
        print(f"{Colors.BLUE}{'='*60}{Colors.ENDC}")
        
        import_statements = generate_import_statements(model_files)
        for statement in import_statements:
            print(f"{Colors.GREEN}{statement}{Colors.ENDC}")
        
        print(f"{Colors.BLUE}{'='*60}{Colors.ENDC}")
        
        # 5. Ofrecer actualizar automáticamente
        print(f"\n{Colors.YELLOW}¿Deseas actualizar automáticamente alembic/env.py? (s/n): {Colors.ENDC}", end="")
        response = input().lower().strip()
        
        if response in ['s', 'si', 'sí', 'y', 'yes']:
            update_alembic_env(import_statements)
        else:
            print(f"\n{Colors.BLUE}ℹ️  Copia manualmente el código de importación sugerido arriba{Colors.ENDC}")
            print(f"{Colors.BLUE}   y pégalo en alembic/env.py después de los imports existentes{Colors.ENDC}")

def update_alembic_env(import_statements: List[str]):
    """Actualizar alembic/env.py con los imports correctos"""
    env_file = Path("alembic/env.py")
    
    try:
        # Leer contenido actual
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Encontrar la línea donde termina el último import de app.models
        lines = content.split('\n')
        insert_position = 0
        
        for i, line in enumerate(lines):
            if 'from app.models' in line or 'import' in line:
                insert_position = i + 1
        
        # Crear nuevo contenido
        new_lines = lines[:insert_position]
        
        # Agregar comentario
        new_lines.append("\n# === IMPORTS DE MODELOS (Auto-generado) ===")
        
        # Agregar imports
        for statement in import_statements:
            new_lines.append(statement)
        
        new_lines.append("# === FIN IMPORTS DE MODELOS ===\n")
        
        # Agregar resto del contenido (sin duplicar imports)
        for line in lines[insert_position:]:
            if not line.strip().startswith('from app.models'):
                new_lines.append(line)
        
        # Escribir archivo actualizado
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        
        print(f"\n{Colors.GREEN}✅ alembic/env.py actualizado exitosamente{Colors.ENDC}")
        print(f"{Colors.BLUE}ℹ️  Revisa el archivo para asegurarte de que los cambios son correctos{Colors.ENDC}")
        
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error actualizando archivo: {e}{Colors.ENDC}")
        print(f"{Colors.YELLOW}⚠️  Por favor, actualiza manualmente{Colors.ENDC}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️ Operación cancelada{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)