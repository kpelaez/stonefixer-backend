from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select
from starlette.middleware.base import RequestResponseEndpoint

import logging
import secrets
import time
import base64

from app.core.exceptions import register_exception_handlers
from app.db.database import create_db_and_tables, engine
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
from app.models import (User, UserRole, Role, TechAsset, AssetAssignment, AssetMaintenance, OvertimeEntry)

# Crear tablas
create_db_and_tables()

# ── Resolver referencias circulares de Pydantic v2 
# TechAssetWithAssignment referencia a AssetAssignmentRead con una forward
# reference (string "AssetAssignmentRead") para evitar importaciones circulares
# entre tech_asset.py y asset_assignment.py.
#
# Pydantic v2 NO resuelve estas referencias automáticamente en el momento de
# la definición de la clase; es necesario llamar a model_rebuild() una vez que
# AMBOS modelos ya están importados en el mismo contexto.
#
# Si se elimina esta llamada, el schema de OpenAPI y la serialización de
# TechAssetWithAssignment fallarán con un error de forward reference.
from app.models.tech_asset import TechAssetWithAssignment
from app.models.asset_assignment import AssetAssignmentRead # necesari para el rebuild  

TechAssetWithAssignment.model_rebuild()
logger.info("Modelos Pydantic reconstruidos correctamente")


# Importar routers 
from app.api.routes.auth_routes import router as auth_router
from app.api.routes.users_routes import router as users_router
from app.api.routes.assignment_documents_routes import router as assignment_documents_router
from app.api.routes.tech_assets_routes import router as tech_assets_router
from app.api.routes.asset_assignments_routes import router as asset_assignments_router
from app.api.routes.asset_maintenances_routes import router as asset_maintenances_router
from app.api.routes.business_indicators_routes import router as business_indicators_router
from app.api.routes.shift_schedule_routes import router as shift_schedule_router
from app.api.routes.overtime_routes import router as overtime_router
from app.api.routes.dashboard_routes import router as dashboard_router

# Instancia de la app
app = FastAPI(
    title=settings.APP_NAME,
    docs_url= None,
    redoc_url= None,
    openapi_url= None,
)

# Handlers de error centralizado
register_exception_handlers(app)


@app.middleware("http")
async def log_requests(request: Request, call_next: RequestResponseEndpoint):
    """Registra duración y status de cada request. Advierte sobre lentos o errores."""

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

# Middleware de Security Headers 
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next: RequestResponseEndpoint):
    """Inyecta security headers en todas las respuestas."""
    response = await call_next(request)
    
    # Previene que el browser interprete archivos con MIME type incorrecto
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Previene clickjacking — la app no puede ser embebida en un iframe
    response.headers["X-Frame-Options"] = "DENY"
    
    # Fuerza HTTPS en producción (navegadores recuerdan esto por 1 año)
    if settings.is_production():
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Controla qué información se envía en el header Referer
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Deshabilita funcionalidades del browser que no necesitamos
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # Elimina el header que revela que usamos uvicorn/Python
    if "server" in response.headers:
        del response.headers["server"]
    
    return response

# Configurar CORS

allowed_origins = settings.get_allowed_origins()
logger.info(f"CORS permitido para: {allowed_origins}")

# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Process-Time", "Content-Disposition"],
)

# REGISTRAR ROUTERS
app.include_router(auth_router, prefix="/api/v1/auth" ,tags=["Autenticacion"])
app.include_router(users_router, prefix="/api/v1/users", tags=["Usuarios"])
app.include_router(tech_assets_router, prefix="/api/v1/inventory/tech-assets",tags=["Inventario - Activos Tech"])
app.include_router(asset_assignments_router, prefix="/api/v1/inventory/assignments", tags=["Inventario - Asignaciones"])
app.include_router(asset_maintenances_router,prefix="/api/v1/inventory/maintenance",tags=["Inventario - Mantenimiento"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(shift_schedule_router, prefix="/api/v1/shift-schedules", tags=["Shift Scheduling"])
app.include_router(business_indicators_router, prefix="/api/v1/business-indicators", tags=["Business Indicators"])
app.include_router(assignment_documents_router, prefix="/api/v1/assignments", tags=["Assignment Documents"])
app.include_router(overtime_router, prefix="/api/v1/overtime", tags=["Horas Extras"])



# Swagger protegido con Basic Auth
def _verify_swagger_auth(request: Request) -> bool:
    """
    Verifica las credenciales Basic Auth para los endpoints de documentación.
    Usa secrets.compare_digest para prevenir timing attacks.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        username, password = decoded.split(":", 1)
        return (
            secrets.compare_digest(username, settings.SWAGGER_USERNAME)
            and secrets.compare_digest(password, settings.SWAGGER_PASSWORD)
        )
    except Exception:
        return False
 
 
def _unauthorized_response() -> Response:
    return Response(
        content="Autenticación requerida",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="StoneFixer API Docs"'},
    )

@app.get("/docs", include_in_schema=False)
async def swagger_ui(request: Request):
    if not _verify_swagger_auth(request):
        return _unauthorized_response()
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.APP_NAME} — API Docs",
    )


@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema(request: Request):
    if not _verify_swagger_auth(request):
        return _unauthorized_response()
 
    schema = get_openapi(
        title=settings.APP_NAME,
        version="1.0.0",
        description="StoneFixer API — Documentación interna",
        routes=app.routes,
    )
    return JSONResponse(content=jsonable_encoder(schema))



# Health check
@app.get("/health", tags=["Sistema"])
def health_check():
    """
    Health check para monitoreo y load balancers.
    Verifica tanto que la app esté corriendo como que la DB sea accesible.
    """
    try:
        with Session(engine) as session:
            session.exec(select(1))
        db_status = "ok"
    except Exception as e:
        logger.error(f"Health check — fallo de DB: {e}")
        db_status = "error"
 
    overall = "ok" if db_status == "ok" else "degraded"
 
    return {
        "status": overall,
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
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

