#!/usr/bin/env python3
"""
StoneFixer - QA Environment Check
Verifica que el entorno esté listo para testing manual
"""

import requests
import sys
from typing import Dict, List, Tuple
from datetime import datetime

class Colors:
    """Colores para output en terminal"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

class QAEnvironmentChecker:
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:5173"
        self.results: List[Tuple[str, bool, str]] = []
        
    def print_header(self, text: str):
        """Imprime un header formateado"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    def print_result(self, test_name: str, success: bool, message: str):
        """Imprime resultado de un test"""
        icon = f"{Colors.GREEN}✅" if success else f"{Colors.RED}❌"
        status = f"{Colors.GREEN}PASS" if success else f"{Colors.RED}FAIL"
        print(f"{icon} {test_name:<40} [{status}{Colors.END}]")
        if message:
            print(f"   {Colors.YELLOW}→ {message}{Colors.END}")
        self.results.append((test_name, success, message))
    
    def check_backend_health(self) -> bool:
        """Verifica que el backend esté corriendo"""
        try:
            response = requests.get(f"{self.backend_url}/", timeout=5)
            if response.status_code == 200:
                self.print_result("Backend Health Check", True, f"Backend respondiendo en {self.backend_url}")
                return True
            else:
                self.print_result("Backend Health Check", False, f"Status code inesperado: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            self.print_result("Backend Health Check", False, "No se puede conectar al backend. ¿Está corriendo?")
            return False
        except Exception as e:
            self.print_result("Backend Health Check", False, f"Error: {str(e)}")
            return False
    
    def check_backend_docs(self) -> bool:
        """Verifica que la documentación de API esté disponible"""
        try:
            response = requests.get(f"{self.backend_url}/docs", timeout=5)
            if response.status_code == 200:
                self.print_result("API Docs (Swagger)", True, f"Disponible en {self.backend_url}/docs")
                return True
            else:
                self.print_result("API Docs (Swagger)", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.print_result("API Docs (Swagger)", False, f"Error: {str(e)}")
            return False
    
    def check_database_connection(self) -> bool:
        """Verifica conexión a base de datos a través de un endpoint"""
        try:
            # Intentamos un endpoint que requiera DB
            response = requests.get(f"{self.backend_url}/inventory/tech-assets", timeout=5)
            if response.status_code == 200:
                categories = response.json()
                self.print_result("Database Connection", True, f"DB respondiendo ({len(categories)} categorías encontradas)")
                return True
            else:
                self.print_result("Database Connection", False, f"Endpoint retornó: {response.status_code}")
                return False
        except Exception as e:
            self.print_result("Database Connection", False, f"Error: {str(e)}")
            return False
    
    def check_critical_endpoints(self) -> Dict[str, bool]:
        """Verifica endpoints críticos del MVP"""
        endpoints = {
            "Auth Endpoint": "/token",
            "Tech Assets List": "/inventory/tech-assets",
            "Assignments List": "/inventory/assignments",
            "Categories List": "/inventory/tech-assets/categories/list",
            "Status List": "/inventory/tech-assets/status/list",
        }
        
        results = {}
        for name, path in endpoints.items():
            try:
                # Para /token usamos POST sin credenciales (esperamos 422 o 401)
                if path == "/token":
                    response = requests.post(
                        f"{self.backend_url}{path}",
                        data={"username": "test", "password": "test"},
                        timeout=5
                    )
                    # 401 o 422 son esperados (credenciales inválidas)
                    success = response.status_code in [401, 422]
                    msg = "Endpoint responde correctamente (401/422 esperado)"
                else:
                    # Para otros endpoints, GET sin auth (pueden retornar 401 o data)
                    response = requests.get(f"{self.backend_url}{path}", timeout=5)
                    # Aceptamos 200 (data pública) o 401 (requiere auth)
                    success = response.status_code in [200, 401]
                    msg = f"Status: {response.status_code}"
                
                self.print_result(f"Endpoint: {name}", success, msg)
                results[name] = success
            except Exception as e:
                self.print_result(f"Endpoint: {name}", False, f"Error: {str(e)}")
                results[name] = False
        
        return results
    
    def check_frontend(self) -> bool:
        """Verifica que el frontend esté corriendo"""
        try:
            response = requests.get(self.frontend_url, timeout=5)
            if response.status_code == 200:
                self.print_result("Frontend Server", True, f"Frontend accesible en {self.frontend_url}")
                return True
            else:
                self.print_result("Frontend Server", False, f"Status code: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            self.print_result("Frontend Server", False, "No se puede conectar. ¿Está corriendo 'npm run dev'?")
            return False
        except Exception as e:
            self.print_result("Frontend Server", False, f"Error: {str(e)}")
            return False
    
    def print_summary(self):
        """Imprime resumen final"""
        total = len(self.results)
        passed = sum(1 for _, success, _ in self.results if success)
        failed = total - passed
        
        self.print_header("RESUMEN DE VERIFICACIÓN")
        
        print(f"{Colors.BOLD}Total de checks: {total}{Colors.END}")
        print(f"{Colors.GREEN}Pasados: {passed}{Colors.END}")
        print(f"{Colors.RED}Fallidos: {failed}{Colors.END}")
        print(f"{Colors.BOLD}Porcentaje de éxito: {(passed/total*100):.1f}%{Colors.END}\n")
        
        if failed == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 ¡ENTORNO LISTO PARA QA!{Colors.END}\n")
            return True
        else:
            print(f"{Colors.RED}{Colors.BOLD}⚠️  HAY PROBLEMAS QUE RESOLVER{Colors.END}")
            print(f"{Colors.YELLOW}Revisa los checks fallidos arriba{Colors.END}\n")
            return False
    
    def run_all_checks(self):
        """Ejecuta todas las verificaciones"""
        self.print_header("STONEFIXER QA - VERIFICACIÓN DE ENTORNO")
        print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Backend checks
        print(f"\n{Colors.BOLD}🔧 BACKEND CHECKS{Colors.END}")
        print("-" * 60)
        backend_ok = self.check_backend_health()
        if backend_ok:
            self.check_backend_docs()
            self.check_database_connection()
            self.check_critical_endpoints()
        else:
            print(f"{Colors.YELLOW}⚠️  Backend no disponible, saltando checks dependientes{Colors.END}")
        
        # Frontend checks
        print(f"\n{Colors.BOLD}🎨 FRONTEND CHECKS{Colors.END}")
        print("-" * 60)
        self.check_frontend()
        
        # Summary
        success = self.print_summary()
        
        # Instrucciones
        if not success:
            self.print_header("INSTRUCCIONES PARA RESOLVER PROBLEMAS")
            print(f"{Colors.YELLOW}1. Backend no corre:{Colors.END}")
            print(f"   cd <proyecto-backend> && uvicorn main:app --reload --host 0.0.0.0 --port 8000\n")
            print(f"{Colors.YELLOW}2. Frontend no corre:{Colors.END}")
            print(f"   cd <proyecto-frontend> && npm run dev\n")
            print(f"{Colors.YELLOW}3. Base de datos:{Colors.END}")
            print(f"   Verifica tu .env y que PostgreSQL esté corriendo\n")
        
        return success


def main():
    """Función principal"""
    checker = QAEnvironmentChecker()
    success = checker.run_all_checks()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()