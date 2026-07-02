from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlmodel import Session, select

from app.db.database import get_db

from app.models.tech_asset import (
    AssetCategory, 
    AssetStatus, 
    TechAssetResponse, 
    TechAssetSummary, 
    TechAssetUpdate, 
    TechAssetCreate, 
    TechAssetWithAssignment,
    GenerateAssetTagRequest,
)
from app.models.user import User

from app.api.deps import get_current_user, RoleChecker, require_inventory_manager, require_admin
from app.schemas.common import PaginatedResponse
from app.services.tech_asset_service import create_tech_asset, generate_asset_tag, get_tech_assets, get_tech_asset, update_tech_asset, delete_tech_asset, get_tech_assets_count, get_asset_statistics, get_warranty_expiring_assets

from app.core.rate_limiter import limiter
from app.config import settings
import logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=TechAssetResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.CRITICAL_WRITE_RATE_LIMIT) # 20/minuto
def create_tech_asset_endpoint(
    request: Request,
    tech_asset: TechAssetCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(require_admin) # solo admin
    ):
    """
    Crear un nuevo activo tecnologico
    Permisos: Solo adminsitradores
    Rate limit: 20 requests/minuto
    """
    try:
        logger.debug(f"Creando activo — payload recibido de {current_user.email}")
        result = create_tech_asset(db, tech_asset)
        logger.info(f"Activo creado: {result.id} por {current_user.email}")
        return result
    except ValueError as e:
        logger.warning(f"Validación fallida al crear activo: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("Error inesperado creando activo")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor")
    
@router.get("/", response_model=PaginatedResponse[TechAssetSummary])
@limiter.limit(settings.READ_RATE_LIMIT) #200/minuto
async def get_tech_assets_endpoint(
    request: Request,
    page: int = Query(default=1, ge=1, description="Número de página"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items por página"),
    search: Optional[str] = Query(default=None, description="Buscar por nombre, marca, modelo, serial o tag"),
    status: Optional[AssetStatus] = Query(default=None, description="Filtrar por estado"),
    category: Optional[AssetCategory] = Query(default=None, description="Filtrar por categoría"),
    location: Optional[str] = Query(default=None, description="Filtrar por ubicación"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtener lista de activos paginada tecnologicos con paginacion

    **Parámetros:**
    - `page`: Número de página (1, 2, 3, ...)
    - `page_size`: Cantidad de registros por página (máx 100)
    - `category`: Filtrar por categoría (opcional)
    - `status`: Filtrar por estado (opcional)
    - `search`: Buscar en nombre, asset_tag, marca, modelo o serial_number

    **Ejemplos:**
    - Primera página: `?page=1&page_size=50`
    - Solo notebooks: `?category=Notebook`
    - Notebooks disponibles: `?category=Notebook&status=available`

    Rate limit: 200 request/minuto
    """
    


    try:
        result = get_tech_assets(
            db=db,
            page=page,
            page_size=page_size,
            search=search,
            status=status,
            category=category,
            location=location,
        )
        return result
    except Exception as e:
        logging.error(f"Error obteniendo activos paginados: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error al obtener la lista de activos",
        )


@router.get("/statistics/overview")
async def get_asset_statistics_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener estadísticas generales de activos tecnológicos"""
    try:
        return get_asset_statistics(db)
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener estadísticas")


@router.get("/warranty/expiring")
async def get_warranty_expiring_endpoint(
    days_ahead: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtener activos con garantía por vencer"""
    try:
        return get_warranty_expiring_assets(db, days_ahead)
    except Exception as e:
        logger.error(f"Error obteniendo garantías: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener garantías")


@router.get("/{asset_id}", response_model=TechAssetWithAssignment)
@limiter.limit(settings.READ_RATE_LIMIT) # 200/minuto
async def get_tech_asset_endpoint(
    request: Request,
    asset_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    """
    Obtener un activo tecnologico especifico por ID
    Rate limit: 200 requests/minuto
    """
    tech_asset = get_tech_asset(db, asset_id)
    if not tech_asset:
        raise HTTPException(
            status_code= status.HTTP_404_NOT_FOUND, detail="Activo no encontrado"
        )
    return tech_asset

@router.patch("/{asset_id}", response_model=TechAssetResponse)
@limiter.limit(settings.WRITE_RATE_LIMIT) #50/minuto
async def update_tech_asset_endpoint(
    request: Request,
    asset_id: int, 
    tech_asset_update: TechAssetUpdate, 
    current_user: User = Depends(require_inventory_manager), 
    db: Session = Depends(get_db)
    ):
    """
    Actualizar un activo tecnologico

    Permisos: Administradores e Inventory Managers
    Rate limit: 50 requests/minuto
    """
    try:
        logger.info(f"Usuario {current_user.email} actualizando activo ID: {asset_id}")
        tech_asset = update_tech_asset(db, asset_id, tech_asset_update)

        if not tech_asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activo con ID {asset_id} no encontrado"
            )

        logger.info(f"Activo {asset_id} actualizado correctamente")
        return tech_asset

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception(f"Error inesperado actualizando activo {asset_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al actualizar el activo"
        )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.CRITICAL_WRITE_RATE_LIMIT) #20/minuto
async def delete_asset_endpoint(
    request: Request,
    asset_id: int, 
    current_user: User = Depends(require_admin), 
    db: Session = Depends(get_db)):
    """
    Eliminar un activo

    Operacion Critica
    Permiso: Solo administradores
    Rate limit: 20 requests/minuto
    """
    try:
        logger.warning(f"Usuario {current_user.email} eliminando activo ID: {asset_id}")
        success = delete_tech_asset(db, asset_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activo con ID {asset_id} no encontrado"
            )

        logger.info(f"Activo {asset_id} eliminado correctamente")
        return None

    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Error eliminando activo {asset_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al eliminar el activo"
        )

@router.get("/{asset_id}/maintenance-history")
async def get_asset_maintenance_history_endpoint(asset_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Obtener historial de mantenimiento del activo"""
    from app.services.asset_maintenance_service import get_asset_maintenance_history

    asset = get_tech_asset(db, asset_id)
    if not asset: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activo con ID {asset_id} no encontrado"
        )
    
    try:
        return get_asset_maintenance_history(db, asset_id)
    except Exception:
        logger.exception(f"Error obteniendo historial de mantenimiento del activo {asset_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el historial de mantenimiento"
        )


@router.get("/categories/list")
async def get_asset_categories(current_user: User = Depends(get_current_user)):
    """Obtener lista de categorías disponibles para activos tecnológicos"""
    try:
        return [
            {"value": category.value, "label": category.value.replace("_", " ").title()}
            for category in AssetCategory
        ]
    except Exception:
        logger.exception("Error obteniendo categorías")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al obtener las categorías")

@router.get("/status/list")
async def get_asset_statuses(current_user: User = Depends(get_current_user)):
    """Obtener lista de estados disponibles para activos tecnológicos"""
    try:
        return [
            {"value": status_item.value, "label": status_item.value.replace("_", " ").title()}
            for status_item in AssetStatus
        ]
    except Exception:
        logger.exception("Error obteniendo estados")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al obtener los estados")
    
@router.post("/generate-tag",response_model=dict)
#@require_roles(["admin", "inventory_manager"])
async def generate_asset_tag_endpoint(
    request: GenerateAssetTagRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)    
):
    """Generar una etiqueta de activo única"""
    try:
        tag = generate_asset_tag(db, request.category)
        logger.info(
            f"Tag generado: {tag} para categoría {request.category.value} por {current_user.email}"
        )
        return {"asset_tag": tag, "category": request.category.value}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error generando tag de activo")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al generar el tag del activo"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Error generando tag: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al generar el tag del activo"
        )