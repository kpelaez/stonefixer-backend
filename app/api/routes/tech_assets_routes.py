from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, logger, status
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
from app.services.tech_asset_service import create_tech_asset, generate_asset_tag, get_tech_assets, get_tech_asset, update_tech_asset, delete_tech_asset


router = APIRouter()


@router.post("/", response_model=TechAssetResponse, status_code=status.HTTP_201_CREATED)
def create_tech_asset_endpoint(tech_asset: TechAssetCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Crear un nuevo activo tecnologico"""
    try:
        print(f"Received tech_asset data: {tech_asset}")  # Para debugging
        result = create_tech_asset(db, tech_asset)
        print(f"Created tech_asset: {result}")  # Para debugging
        return result
    except ValueError as e:
        print(f"ValueError creating tech_asset: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Unexpected error creating tech_asset: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor")
    
@router.get("/", response_model=List[TechAssetSummary])
async def get_tech_assets_endpoint(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Obtener lista de activos"""
    try:
        assets = get_tech_assets(db)
        return assets
    except Exception as e:
        print(f"[ERROR] Error obteniendo activos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener la lista de activos"
        )

@router.get("/{asset_id}", response_model=TechAssetWithAssignment)
async def get_tech_asset_endpoint(asset_id: int, current_user: User = Depends(get_current_user) ,db: Session = Depends(get_db)):
    """Obtener un activo tecnologico especifico"""
    tech_asset = get_tech_asset(db, asset_id)
    if not tech_asset:
        raise HTTPException(
            status_code= status.HTTP_404_NOT_FOUND, detail="Activo no encontrado"
        )
    return tech_asset

@router.patch("/{asset_id}", response_model=TechAssetResponse)
async def update_tech_asset_endpoint(asset_id: int, tech_asset_update: TechAssetUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Actualizar un activo tecnologico"""
    try:
        print(f"[INFO] Usuario {current_user.email} actualizando activo ID: {asset_id}")
        
        tech_asset = update_tech_asset(db, asset_id, tech_asset_update)
        
        if not tech_asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activo con ID {asset_id} no encontrado"
            )
        
        print(f"[SUCCESS] Activo {asset_id} actualizado correctamente")
        return tech_asset
        
    except HTTPException:
        # Re-lanzar HTTPException sin modificar
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al actualizar el activo"
        )


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_endpoint(asset_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Eliminar un activo"""
    try:
        print(f"[WARNING] Usuario {current_user.email} eliminando activo ID: {asset_id}")
        
        success = delete_tech_asset(db, asset_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activo con ID {asset_id} no encontrado"
            )
        
        print(f"[SUCCESS] Activo {asset_id} eliminado correctamente")
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Error eliminando activo: {e}")
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
        history = get_asset_maintenance_history(db, asset_id)
        return history
    except Exception as e:
        print(f"[ERROR] Error obteniendo historial: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el historial de mantenimiento"
        )


@router.get("/categories/list")
async def get_asset_categories(current_user: User = Depends(get_current_user)):
    """Obtener lista de categorías disponibles para activos tecnológicos"""
    try:
        categories = [
            {
                "value": category.value,
                "label": category.value.replace("_", " ").title()
            }
            for category in AssetCategory
        ]
        return categories
    except Exception as e:
        print(f"[ERROR] Error obteniendo categorías: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener las categorías"
        )

@router.get("/status/list")
async def get_asset_statuses(current_user: User = Depends(get_current_user)):
    """Obtener lista de estados disponibles para activos tecnológicos"""
    try:
        statuses = [
            {
                "value": status_item.value,
                "label": status_item.value.replace("_", " ").title()
            }
            for status_item in AssetStatus
        ]
        return statuses
    except Exception as e:
        print(f"[ERROR] Error obteniendo estados: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener los estados"
        )
    
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
            f"[TAG GENERADO] {tag} para categoría {request.category.value} "
            f"por usuario {current_user.email}"
        )
        
        return {
            "asset_tag": tag,
            "category": request.category.value
        }
        
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