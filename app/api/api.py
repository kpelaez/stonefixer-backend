from fastapi import APIRouter

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

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/api/v1/auth", tags=["Autenticacion"])
api_router.include_router(users_router, prefix="/api/v1/users", tags=["Usuarios"])
api_router.include_router(tech_assets_router, prefix="/api/v1/inventory/tech-assets", tags=["Inventario - Activos Tech"])
api_router.include_router(asset_assignments_router, prefix="/api/v1/inventory/assignments", tags=["Inventario - Asignaciones"])
api_router.include_router(asset_maintenances_router, prefix="/api/v1/inventory/maintenance", tags=["Inventario - Mantenimiento"])
api_router.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["Dashboard"])
api_router.include_router(shift_schedule_router, prefix="/api/v1/shift-schedules", tags=["Shift Scheduling"])
api_router.include_router(business_indicators_router, prefix="/api/v1/business-indicators", tags=["Business Indicators"])
api_router.include_router(assignment_documents_router, prefix="/api/v1/assignments", tags=["Assignment Documents"])
api_router.include_router(overtime_router, prefix="/api/v1/overtime", tags=["Horas Extras"])