from typing import Optional
from sqlmodel import Session, select
from datetime import datetime, timezone

from app.models.tech_asset import (
    TechAsset, 
    TechAssetCreate, 
    TechAssetSummary, 
    TechAssetResponse, 
    TechAssetUpdate, 
    TechAssetWithAssignment, 
    AssetCategory, 
    AssetStatus
)

from app.models.asset_assignment import AssetAssignment, AssignmentStatus

def create_tech_asset(db: Session, tech_asset: TechAssetCreate):
    """Crear un nuevo activo tecnologico"""

    # Verificar asset_tag si se proporciona
    if tech_asset.asset_tag:
        existing_tag = db.exec(
            select(TechAsset).where(TechAsset.asset_tag == tech_asset.asset_tag)).first()
            
        if existing_tag:
            raise ValueError(f"Ya existe un activo con la etiqueta: {tech_asset.asset_tag}")

    # Crear el activo
    db_asset = TechAsset(**tech_asset.dict())
    db_asset.created_at = datetime.now(timezone.utc)

    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)

    return db_asset

def get_tech_assets(db: Session):
    """Obtener lista de activos tecnologicos con filtros"""       

    query = select(TechAsset)

    query = query.order_by(TechAsset.created_at)

    assets = db.exec(query).all()

    return [TechAssetSummary.from_orm(asset) for asset in assets]

def get_tech_asset(db: Session, tech_asset_id: int):
    """Obtener un activo tecnologico por ID con informacion de asignacion"""

    # Obtener el activo
    asset = db.get(TechAsset, tech_asset_id)
    if not asset: 
        return None
    
    # Obtener asignacion activa si existe
    current_assignment = db.exec(
        select(AssetAssignment)
        .where(AssetAssignment.tech_asset_id == tech_asset_id)
        .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
    ).first()

    # Crear respuesta con informacion de asignacion
    asset_data = TechAssetWithAssignment.from_orm(asset)

    if current_assignment:
        from app.models.user import User
        assigned_user = db.get(User, current_assignment.assigned_to_user_id)
        if assigned_user:
            asset_data.assigned_to = f"{assigned_user.full_name} ({assigned_user.email})"

    return asset_data

def update_tech_asset(db: Session, tech_asset_id: int, tech_asset_update: TechAssetUpdate):
    """Actualizar un activo tecnologico"""

    asset = db.get(TechAsset, tech_asset_id)
    if not asset:
        return None
    
    # Obtener datos de actualziacion excluyendo campos no establecidos
    update_data = tech_asset_update.dict(exclude_unset = True)

    # Verificar unicidad de asset_tag si se esta actualizando
    if "asset_tag" in update_data and update_data["asset_tag"]:
        existing_tag = db.exec(
            select(TechAsset)
            .where(TechAsset.asset_tag == update_data["asset_tag"])
            .where(TechAsset.id != tech_asset_id)
        ).first()

        if existing_tag:
            raise ValueError(f"Ya existe un activo con la etiqueta: {update_data['asset_tag']}")
        
    # Actualizar campos
    for field, value in update_data.items():
        setattr(asset, field, value)

    asset.updated_at = datetime.now(timezone.utc)

    db.add(asset)
    db.commit()
    db.refresh(asset)

    return asset

def delete_tech_asset(db: Session, tech_asset_id: int):
    """Eliminar un activo tecnologico"""

    asset = db.get(TechAsset, tech_asset_id)
    if not asset:
        return False
    
    # Verificar que no tenga asignacion activas
    active_assignment = db.exec(
        select(AssetAssignment)
        .where(AssetAssignment.tech_asset_id == tech_asset_id)
        .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
    ).first()

    if active_assignment:
        raise ValueError("No se puede eliminar un activo que tiene asignaciones activas")
    
    # Verificar que no tenga mantenimientos pendientes
    from app.models.asset_maintenance import AssetMaintenance, MaintenanceStatus
    pending_maintenance = db.exec(
        select(AssetMaintenance)
        .where(AssetMaintenance.tech_asset_id == tech_asset_id)
        .where(AssetMaintenance.status.in_([
            MaintenanceStatus.SCHEDULED,
            MaintenanceStatus.IN_PROGRESS,
            MaintenanceStatus.PENDING_PARTS
        ]))
    ).first()

    if pending_maintenance:
        raise ValueError("No se puede eliminar un activo que tiene mantenimiento pendientes")
    
    db.delete(asset)
    db.commit()

    return True


def generate_asset_tag(db: Session, category: AssetCategory):
    """Generar una etiqueta de activo unica"""

    # Mapeo de categorias a prefijos
    category_prefixes = {
        AssetCategory.NOTEBOOK: "NBK",
        AssetCategory.DESKTOP: "DSK",
        AssetCategory.MONITOR: "MON",
        AssetCategory.TECLADO: "KBD",
        AssetCategory.MOUSE: "MSE",
        AssetCategory.KIT_TECLADO_MOUSE: "KTM",
        AssetCategory.IMPRESORA: "IMP",
        AssetCategory.TABLET: "TAB",
        AssetCategory.CELULAR: "CEL",
        AssetCategory.SERVER: "SRV",
        AssetCategory.ROUTER: "RTR",
        AssetCategory.ACCESORIOS: "ACC",
        AssetCategory.SOFTWARE: "SFT",
        AssetCategory.CABLE: "CBL",
        AssetCategory.OTRO: "OTH"
    }

    prefix = category_prefixes.get(category, "KPD") #Si no encuentra categoria, asigna AST por defecto

    # Obtener el siguiente numero secuencial

    existing_tags = db.exec(
        select(TechAsset.asset_tag)
        .where(TechAsset.asset_tag.like(f"{prefix}-%"))
    ).all()

    # Extraer numeros y encontrar el siguiente
    numbers = []
    for tag in existing_tags:
        if tag and '-' in tag:
            try:
                number = int(tag.split('-')[-1])
                numbers.append(number)
            except ValueError:
                continue

    next_number = max(numbers, default = 0) + 1

    return f"{prefix}-{next_number:03d}"

