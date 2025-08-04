from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import create_db_and_tables
from app.config import settings

# Importar routers existentes refactorizados
from app.api.routes.auth_routes import router as auth_router
from app.api.routes.users_routes import router as users_router

# Importacion de nuevos routers
from app.api.routes.tech_assets_routes import router as tech_assets_router
from app.api.routes.asset_assignaments_routes import router as asset_assignments_router
from app.api.routes.asset_maintenances_routes import router as asset_maintenances_router


# Importacion de todos los modelos
from app.models.user import User
from app.models.role import Role
from app.models.tech_asset import TechAsset
from app.models.asset_assignment import AssetAssignment
from app.models.asset_maintenance import AssetMaintenance

# Crear tablas
create_db_and_tables()

app = FastAPI(title=settings.APP_NAME)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # URL de tu frontend (ajustar según sea necesario)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RUTAS DE AUTENTICACION (refactorizadas)
app.include_router(auth_router, tags=["Autenticacion"])

# RUTAS DE USUARIOS (refactorizadas)
app.include_router(users_router, prefix="/users", tags=["Usuarios"])

# RUTAS DE MODULO INVENTARIO
app.include_router(tech_assets_router, prefix="/inventario/assets",tags=["Inventario - Activos Tech"])

app.include_router(asset_assignments_router, prefix="/inventario/asignments", tags=["Inventario - Asignaciones"])

app.include_router(asset_maintenances_router,prefix="/inventory/maintenance",tags=["Inventario - Mantenimiento"])


# Endpoint de ingreso al servidor
@app.get("/")
def read_root():
    return {"message": "Bienvenido al servicio de autenticación de StoneFixer"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
