from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
import logging
import secrets

from app.core.exceptions import register_exception_handlers
from app.db.database import create_db_and_tables
from app.config import settings

# Configurar logging para mejor debugging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s -%(message)s'
)
logger = logging.getLogger(__name__)

# Log del entorno al arrancar (sin mostrar secrets)
logger.info(f"Iniciando {settings.APP_NAME}")
logger.info(f"Entorno: {settings.ENVIRONMENT}")
logger.info(f"Debug: {settings.DEBUG}")

# Importacion de todos los modelos
from app.models import (User, UserRole, Role, TechAsset, AssetAssignment, AssetMaintenance)

# Crear tablas
create_db_and_tables()

# Importar routers existentes refactorizados
from app.api.routes.auth_routes import router as auth_router
from app.api.routes.users_routes import router as users_router
# Importacion de rutas de documento de asignaciones de activos
from app.api.routes.assignment_documents_routes import router as assignment_documents_router
from app.api.routes.tech_assets_routes import router as tech_assets_router
from app.api.routes.asset_assignments_routes import router as asset_assignments_router
from app.api.routes.asset_maintenances_routes import router as asset_maintenances_router
from app.api.routes.business_indicators_routes_final import router as business_indicators_router
from app.api.routes.shift_schedule_routes import router as shift_schedule_router


app = FastAPI(
    title=settings.APP_NAME,
    docs_url= None,
    redoc_url= None,
    openapi_url= None,
)

register_exception_handlers(app)

# Configurar CORS

allowed_origins = settings.get_allowed_origins()
logger.info(f"CORS permitido para: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# Middleware personalizado para logging de rendimiento
@app.middleware("http")
async def log_requests(request, call_next):
    import time
    
    start_time = time.time()

    # Log de request
    logger.info(f"→ {request.method} {request.url.path}")
    
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
    else:
        logger.info(
            f"← {request.method} {request.url.path} - "
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
app.include_router(shift_schedule_router, prefix="/shift-schedules", tags=["Shift Scheduling"])

# RUTAS DE BUSINESS INDICATORS (KPIs) - NUEVA
app.include_router(business_indicators_router, prefix="/api/business-indicators", tags=["Business Indicators"])

# RUTAS DE INTEGRACIO CON HUMAND
app.include_router(assignment_documents_router, prefix="/api/v1/assignments", tags=["Assignment Documents"])


@app.get("/docs", include_in_schema=False)
async def swagger_ui(request: Request):
    # Verificar Basic Auth manualmente
    import base64
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Basic "):
        return Response(
            content="Autenticación requerida",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="StoneFixer API Docs"'}
        )
    
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        username, password = decoded.split(":", 1)
        correct_user = secrets.compare_digest(username, settings.SWAGGER_USERNAME)
        correct_pass = secrets.compare_digest(password, settings.SWAGGER_PASSWORD)
        if not (correct_user and correct_pass):
            return Response(
                content="Credenciales incorrectas",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="StoneFixer API Docs"'}
            )
    except Exception:
        return Response(
            content="Error de autenticación",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="StoneFixer API Docs"'}
        )
    
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.APP_NAME} — API Docs"
    )


@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema(request: Request):
    import base64
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Basic "):
        return Response(
            content="Autenticación requerida",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="StoneFixer API Docs"'}
        )
    
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        username, password = decoded.split(":", 1)
        correct_user = secrets.compare_digest(username, settings.SWAGGER_USERNAME)
        correct_pass = secrets.compare_digest(password, settings.SWAGGER_PASSWORD)
        if not (correct_user and correct_pass):
            return Response(
                content="Credenciales incorrectas",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="StoneFixer API Docs"'}
            )
    except Exception:
        return Response(
            content="Error de autenticación",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="StoneFixer API Docs"'}
        )
    
    return get_openapi(
        title=settings.APP_NAME,
        version="1.0.0",
        routes=app.routes
    )



# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Sistema"])
def health_check():
    """Endpoint de salud para monitoreo y load balancers"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["Sistema"])
def read_root():
    return {"message": f"Bienvenido a {settings.APP_NAME}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development(),
    )