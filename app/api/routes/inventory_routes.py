from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.db.database import get_db

from app.models.tech_asset import TechAssetResponse, TechAssetUpdate, TechAssetCreate
from app.models.user import User

from app.api.deps import require_roles
from app.services.tech_asset_service import create_asset, get_assets, get_asset, update_asset, delete_asset


router = APIRouter()


@router.post("/", response_model=TechAssetResponse, status_code=status.HTTP_201_CREATED)
@require_roles(["admin", "assets_inventory_manager"])
def create_product_endpoint(db: Session = Depends(get_db), asset: TechAssetCreate):
    """Crear un nuevo activo tecnologico"""
    return create_asset(db, asset)

@router.get("/", response_model=List[TechAssetResponse])
async def get_assets_endpoint(db: Session = Depends(get_db)):
    """Obtener lista de activos"""
    return get_assets(db)


@router.get("/{asset_id}", response_model=TechAssetResponse)
async def get_asset_endpoint(asset_id: int, db: Session = Depends(get_db)):
    """Obtener un activo tecnologico especifico"""
    asset = get_asset(db, asset_id)
    if not asset:
        raise HTTPException(
            status_code= status.HTTP_404_NOT_FOUND, detail="Activo no encontrado"
        )
    return asset

@router.patch("/{asset_id}", response_model=TechAssetResponse)
@require_roles(["admin", "assets_inventory_manager"])
async def update_asset_endpoint(asset_id: int, asset_update: TechAssetUpdate, db: Session = Depends(get_db)):
    """Actualizar un activo tecnologico"""
    asset = update_asset(db, asset_id, asset_update)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")
    return asset

@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_roles(["admin", "assets_inventory_manager"])
async def delete_asset_endpoint(db: Session = Depends(get_db), asset_id: int):
    """Eliminar un activo"""
    success = delete_asset(db, asset_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")
    return None

@router.get("/{asset_id}/maintenance-history")
async def get_asset_maintenance_history(asset_id: int, db: Session = Depends(get_db)):
    """Obtener historial de mantenimiento del activo"""
    from app.services.maintenance_service import get_asset_maintenance_history

    asset = get_asset(db, asset_id)
    if not asset: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")
    
    return get_asset_maintenance_history(db, asset_id)