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
from app.core.middleware import register_cors, register_middlewares
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




# Instancia de la app
app = FastAPI(
    title=settings.APP_NAME,
    docs_url= None,
    redoc_url= None,
    openapi_url= None,
)

# Handlers de error centralizado
register_exception_handlers(app)

# Middlewares
register_middlewares(app)

# Configurar CORS

allowed_origins = settings.get_allowed_origins()
logger.info(f"CORS permitido para: {allowed_origins}")

register_cors(app)

# Importar routers 
from app.api.api import api_router
# REGISTRAR ROUTERS
app.include_router(api_router)



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

