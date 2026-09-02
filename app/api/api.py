from fastapi import APIRouter

from app.api.routes.auth_routes import router as auth_router
from app.api.routes.users_routes import router as users_router
from app.api.routes.assignment_documents_routes import router as assignment_documents_router
from app.api.routes.tech_assets_routes import router as tech_assets_router
from app.api.routes.asset_assignments_routes import router as asset_assignments_router
from app.api.routes.asset_maintenances_routes import router as asset_maintenances_router
from app.api.routes.shift_schedule_routes import router as shift_schedule_router
from app.api.routes.overtime_routes import router as overtime_router
from app.api.routes.dashboard_routes import router as dashboard_router
from app.api.routes.contribucion_marginal_routes import router as contribucion_marginal_router
from app.api.routes.ot_detalle_routes import router as ot_detalle_router
from app.api.routes.facturacion_cobranza_routes import router as facturacion_cobranza_router
from app.api.routes.venta_mes_routes import router as venta_mes_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/api/v1/auth", tags=["Autenticacion"])
api_router.include_router(users_router, prefix="/api/v1/users", tags=["Usuarios"])
api_router.include_router(tech_assets_router, prefix="/api/v1/inventory/tech-assets", tags=["Inventario - Activos Tech"])
api_router.include_router(asset_assignments_router, prefix="/api/v1/inventory/assignments", tags=["Inventario - Asignaciones"])
api_router.include_router(asset_maintenances_router, prefix="/api/v1/inventory/maintenance", tags=["Inventario - Mantenimiento"])
api_router.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["Dashboard"])
api_router.include_router(shift_schedule_router, prefix="/api/v1/shift-schedules", tags=["Shift Scheduling"])
api_router.include_router(assignment_documents_router, prefix="/api/v1/assignments", tags=["Assignment Documents"])
api_router.include_router(overtime_router, prefix="/api/v1/overtime", tags=["Horas Extras"])
api_router.include_router(contribucion_marginal_router, prefix="/api/v1/contribucion-marginal", tags=["Contribucion Marginal"])
api_router.include_router(ot_detalle_router, prefix="/api/v1/ot-detalle", tags=["OT Detalle"])
api_router.include_router(facturacion_cobranza_router, prefix="/api/v1/facturacion-cobranza", tags=["Facturación y Cobranza"])
api_router.include_router(venta_mes_router, prefix="/api/v1/venta-mes", tags=["Venta del Mes"])