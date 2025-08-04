from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.db.database import get_db

from app.models.tech_asset import AssetCategory, AssetStatus, TechAssetResponse, TechAssetSummary, TechAssetUpdate, TechAssetCreate, TechAssetWithAssignment
from app.models.user import User

from app.api.deps import get_current_user, require_roles
from app.services.tech_asset_service import create_tech_asset, generate_asset_tag, get_tech_assets, get_tech_asset, update_tech_asset, delete_tech_asset


router = APIRouter()


@router.post("/", response_model=TechAssetResponse, status_code=status.HTTP_201_CREATED)
@require_roles(["admin", "assets_inventory_manager"])
def create_tech_asset_endpoint(tech_asset: TechAssetCreate, db: Session = Depends(get_db)):
    """Crear un nuevo activo tecnologico"""
    return create_tech_asset(db, tech_asset)

@router.get("/", response_model=List[TechAssetSummary])
async def get_tech_assets_endpoint(db: Session = Depends(get_db)):
    """Obtener lista de activos"""
    return get_tech_assets(db)


@router.get("/{asset_id}", response_model=TechAssetWithAssignment)
async def get_tech_asset_endpoint(tech_asset_id: int, db: Session = Depends(get_db)):
    """Obtener un activo tecnologico especifico"""
    tech_asset = get_tech_asset(db, tech_asset_id)
    if not tech_asset:
        raise HTTPException(
            status_code= status.HTTP_404_NOT_FOUND, detail="Activo no encontrado"
        )
    return tech_asset

@router.patch("/{asset_id}", response_model=TechAssetResponse)
@require_roles(["admin", "assets_inventory_manager"])
async def update_tech_asset_endpoint(asset_id: int, tech_asset_update: TechAssetUpdate, db: Session = Depends(get_db)):
    """Actualizar un activo tecnologico"""
    tech_asset = update_tech_asset(db, asset_id, tech_asset_update)
    if not tech_asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")
    return tech_asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_roles(["admin", "assets_inventory_manager"])
async def delete_asset_endpoint(asset_id: int, db: Session = Depends(get_db)):
    """Eliminar un activo"""
    success = delete_tech_asset(db, asset_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")
    return None

@router.get("/{asset_id}/maintenance-history")
async def get_asset_maintenance_history_endpoint(asset_id: int, db: Session = Depends(get_db)):
    """Obtener historial de mantenimiento del activo"""
    from app.services.asset_maintenance_service import get_asset_maintenance_history

    asset = get_tech_asset(db, asset_id)
    if not asset: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")
    
    return get_asset_maintenance_history(db, asset_id)


@router.get("/categories/list")
async def get_asset_categories():
    """Obtener lista de categorías disponibles para activos tecnológicos"""
    return [{"value": category.value, "label": category.value.replace("_", " ").title()} 
            for category in AssetCategory]

@router.get("/status/list")
async def get_asset_statuses():
    """Obtener lista de estados disponibles para activos tecnológicos"""
    return [{"value": status.value, "label": status.value.replace("_", " ").title()} 
            for status in AssetStatus]

@router.post("/generate-tag")
@require_roles(["admin", "inventory_manager"])
async def generate_asset_tag_endpoint(
    category: AssetCategory,
    location: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generar una etiqueta de activo única"""
    tag = generate_asset_tag(db, category, location)
    return {"asset_tag": tag, "category": category.value, "location": location}