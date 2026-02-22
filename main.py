from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.exceptions import register_exception_handlers
from app.db.database import create_db_and_tables
from app.config import settings

# Configurar logging para mejor debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar routers existentes refactorizados
from app.api.routes.auth_routes import router as auth_router
from app.api.routes.users_routes import router as users_router

# Importacion de todos los modelos
from app.models import (User, UserRole, Role, TechAsset, AssetAssignment, AssetMaintenance)

# Importacion de rutas de documento de asignaciones de activos
from app.api.routes.assignment_documents_routes import router as assignment_documents_router

# Crear tablas
create_db_and_tables()


# Importacion de nuevos routers
from app.api.routes.tech_assets_routes import router as tech_assets_router
from app.api.routes.asset_assignments_routes import router as asset_assignments_router
from app.api.routes.asset_maintenances_routes import router as asset_maintenances_router
# from app.api.routes.business_indicators_routes import router as business_indicators_router
from app.api.routes.business_indicators_routes_final import router as business_indicators_router_final
from app.api.routes.shift_schedule_routes import router as shift_schedule_router


app = FastAPI(title=settings.APP_NAME)

register_exception_handlers(app)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",    # Vite dev server
        "http://127.0.0.1:5173",   # alternativa
        "http://localhost:3000",    # por si usás otro puerto
        ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware personalizado para logging de rendimiento
@app.middleware("http")
async def log_requests(request, call_next):
    import time
    
    start_time = time.time()
    
    # Procesar request
    response = await call_next(request)
    
    # Calcular tiempo de procesamiento
    process_time = time.time() - start_time
    
    # Log solo requests lentos o con errores
    if process_time > 1.0 or response.status_code >= 400:
        logger.warning(
            f"{request.method} {request.url} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
    
    # Agregar header de tiempo de respuesta
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


# RUTAS DE AUTENTICACION (refactorizadas)
app.include_router(auth_router, tags=["Autenticacion"])

# RUTAS DE USUARIOS (refactorizadas)
app.include_router(users_router, prefix="/users", tags=["Usuarios"])

# RUTAS DE MODULO INVENTARIO
app.include_router(tech_assets_router, prefix="/inventory/tech-assets",tags=["Inventario - Activos Tech"])

app.include_router(asset_assignments_router, prefix="/inventory/assignments", tags=["Inventario - Asignaciones"])

app.include_router(asset_maintenances_router,prefix="/inventory/maintenance",tags=["Inventario - Mantenimiento"])

# RUTAS DE MODULO AGENDA STOCK
app.include_router(shift_schedule_router, prefix="/api/shift-schedules", tags=["Shift Scheduling"])

# RUTAS DE BUSINESS INDICATORS (KPIs) - NUEVA
# app.include_router(business_indicators_router, prefix="/api/business-indicators", tags=["Business Indicators"])
app.include_router(business_indicators_router_final, prefix="/api/business-indicators", tags=["Business Indicators"])

# RUTAS DE INTEGRACIO CON HUMAND
app.include_router(assignment_documents_router, prefix="/api/v1/assignments", tags=["Assignment Documents"])

# Endpoint de ingreso al servidor
@app.get("/")
def read_root():
    return {"message": "Bienvenido al servicio de autenticación de StoneFixer"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
