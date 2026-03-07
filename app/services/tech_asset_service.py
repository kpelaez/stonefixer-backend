from typing import Optional
from sqlmodel import Session, select, func
from datetime import datetime, timezone

from app.models.tech_asset import (
    TechAsset, 
    TechAssetCreate, 
    TechAssetSummary, 
    TechAssetResponse, 
    TechAssetUpdate, 
    TechAssetWithAssignment, 
    AssetCategory, 
    AssetStatus,
)

from app.models.asset_assignment import AssetAssignment, AssignmentStatus
from app.models.user import User

# MÁQUINA DE ESTADOS - Transiciones Permitidas

ALLOWED_STATE_TRANSITIONS = {
    AssetStatus.AVAILABLE: {
        AssetStatus.AVAILABLE,  # Mismo estado
        AssetStatus.ASSIGNED,   # Cuando se asigna
        AssetStatus.IN_MAINTENANCE,  # Puede ir a mantenimiento
        AssetStatus.OUT_OF_ORDER,  # Puede dañarse
        AssetStatus.RETIRED  # Puede darse de baja
    },
    AssetStatus.ASSIGNED: {
        AssetStatus.ASSIGNED,  # Mismo estado
        AssetStatus.AVAILABLE,  # Cuando se devuelve
        AssetStatus.IN_MAINTENANCE,  # Puede ir a mantenimiento
        AssetStatus.OUT_OF_ORDER  # Puede dañarse
        # NO puede ir a RETIRED mientras esté asignado
    },
    AssetStatus.IN_MAINTENANCE: {
        AssetStatus.IN_MAINTENANCE,  # Mismo estado
        AssetStatus.AVAILABLE,  # Después de reparar
        AssetStatus.OUT_OF_ORDER  # Si la reparación falla
        # NO puede asignarse directamente desde mantenimiento
    },
    AssetStatus.OUT_OF_ORDER: {
        AssetStatus.OUT_OF_ORDER,  # Mismo estado
        AssetStatus.AVAILABLE,  # Después de reparar
        AssetStatus.IN_MAINTENANCE,  # Para reparación
        AssetStatus.RETIRED  # Si no se puede reparar
    },
    AssetStatus.RETIRED: {
        AssetStatus.RETIRED  # Estado final, no puede cambiar
    }
}

def validate_state_transition(
    current_status: AssetStatus,
    new_status: AssetStatus
) -> bool:
    """
    Validar si una transición de estado es permitida.
    
    Args:
        current_status: Estado actual del activo
        new_status: Estado al que se quiere cambiar
        
    Returns:
        bool: True si la transición es permitida
        
    Raises:
        ValueError: Si la transición no es permitida
    """
    if new_status not in ALLOWED_STATE_TRANSITIONS.get(current_status, set()):
        raise ValueError(
            f"Transición de estado no permitida: {current_status.value} → {new_status.value}. "
            f"Transiciones permitidas desde {current_status.value}: "
            f"{[s.value for s in ALLOWED_STATE_TRANSITIONS[current_status]]}"
        )
    
    return True

def create_tech_asset(db: Session, tech_asset: TechAssetCreate):
    """
    Crear un nuevo activo tecnológico.
    
    Validaciones:
    - asset_tag único (si se proporciona)
    - serial_number único por marca
    
    Args:
        db: Sesión de base de datos
        tech_asset: Datos del activo a crear
        
    Returns:
        TechAsset: Activo creado
        
    Raises:
        ValueError: Si hay duplicados o datos inválidos
    """
    # Validar asset_tag único
    if tech_asset.asset_tag:
        existing_tag = db.exec(
            select(TechAsset)
            .where(TechAsset.asset_tag == tech_asset.asset_tag)
            .where(TechAsset.deleted_at.is_(None))  # Solo activos no eliminados
        ).first()
        
        if existing_tag:
            raise ValueError(
                f"Ya existe un activo con la etiqueta: {tech_asset.asset_tag}"
            )
    
    # FIX BUG #4: Validar serial_number único por marca
    existing_serial = db.exec(
        select(TechAsset)
        .where(TechAsset.brand == tech_asset.brand)
        .where(TechAsset.serial_number == tech_asset.serial_number)
        .where(TechAsset.deleted_at.is_(None))
    ).first()
    
    if existing_serial:
        raise ValueError(
            f"Ya existe un activo {tech_asset.brand} con número de serie: {tech_asset.serial_number}"
        )
    
    # Crear el activo
    db_asset = TechAsset(**tech_asset.dict())
    db_asset.created_at = datetime.now(timezone.utc)
    
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    
    return db_asset

def get_tech_assets(
        db: Session,
        page: int =1, 
        page_size: int = 10,
        search: Optional[str] = None,
        status: Optional[AssetStatus] = None,
        category: Optional[AssetCategory] = None,
        location: Optional[str] = None,
        include_deleted: bool = False,
    ):
    """
    Obtener lista de activos tecnológicos.
    
    Args:
        db: Sesión de base de datos
        page: Número de página (inicia en 1)
        page_size: Cantidad de registros por página (máx 100)
        search: Búsqueda por nombre, marca, modelo, serial o asset_tag
        status: Filtrar por estado del activo
        category: Filtrar por categoría
        location: Filtrar por ubicación
        include_deleted: Si True, incluye activos eliminados (soft-deleted)
        
    Returns:
        dict con: iotems, total, page, page_size, total_pages
    """
    # Validar límites para evitar queries abusivos
    page = max(1, page)
    page_size = min(max(1, page_size), 100)


    query = ( select(
        TechAsset, 
        AssetAssignment.assigned_to_user_id, 
        User.full_name, 
        User.email
        ).outerjoin(
        AssetAssignment,
        (AssetAssignment.tech_asset_id == TechAsset.id) &
        (AssetAssignment.status == AssignmentStatus.ACTIVE)
        ).outerjoin(
            User, User.id == AssetAssignment.assigned_to_user_id
        )
    )   
    
    # Por defecto, excluir eliminados
    if not include_deleted:
        query = query.where(TechAsset.deleted_at.is_(None))

    if status:
        query = query.where(TechAsset.status == status)

    if category:
        query = query.where(TechAsset.category == category)

    if location:
        query = query.where(TechAsset.location.ilike(f"%{location}%"))

    if search:
        search_term = f"%{search.strip()}%"
        query = query.where(
            TechAsset.name.ilike(search_term)
            | TechAsset.brand.ilike(search_term)
            | TechAsset.model.ilike(search_term)
            | TechAsset.serial_number.ilike(search_term)
            | TechAsset.asset_tag.ilike(search_term)
        )
    
    if status:
        count_query = count_query.where(TechAsset.status == status)
    if category:
        count_query = count_query.where(TechAsset.category == category)
    if location:
        count_query = count_query.where(TechAsset.location.ilike(f"%{location}%"))
    if search:
        search_term = f"%{search.strip()}%"
        count_query = count_query.where(
            TechAsset.name.ilike(search_term)
            | TechAsset.brand.ilike(search_term)
            | TechAsset.model.ilike(search_term)
            | TechAsset.serial_number.ilike(search_term)
            | TechAsset.asset_tag.ilike(search_term)
        )

    total = db.exec(count_query).one()
    
    query = query.order_by(TechAsset.created_at.desc())

    skip = (page - 1) * page_size
    query = query.offset(skip).limit(page_size)
    
    results = db.exec(query).all()
    
    items = []
    for asset, assigned_to_id, user_name, user_email in results:
        asset_summary = TechAssetSummary.model_validate(asset)

        if assigned_to_id and user_name:
            asset_summary.user_assigned = f"{user_name} ({user_email})"
        else:
            asset_summary.user_assigned = None

        items.append(asset_summary)

    total_pages = max(1, -(-total // page_size))  # division sin import math
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }

def get_tech_asset(db: Session, tech_asset_id: int):
    """
    Obtener un activo tecnológico por ID con información de asignación.
    
    Args:
        db: Sesión de base de datos
        tech_asset_id: ID del activo
        
    Returns:
        TechAssetWithAssignment: Activo con información de asignación, o None si no existe
    """
    # Obtener el activo (solo si no está eliminado)
    asset = db.exec(
        select(TechAsset)
        .where(TechAsset.id == tech_asset_id)
        .where(TechAsset.deleted_at.is_(None))
    ).first()
    
    if not asset:
        return None
    
    # Obtener asignación activa si existe
    current_assignment = db.exec(
        select(AssetAssignment)
        .where(AssetAssignment.tech_asset_id == tech_asset_id)
        .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
    ).first()
    
    # Crear respuesta con información de asignación
    asset_data = TechAssetWithAssignment.from_orm(asset)
    
    if current_assignment:
        from app.models.user import User
        assigned_user = db.get(User, current_assignment.assigned_to_user_id)
        if assigned_user:
            asset_data.assigned_to = f"{assigned_user.full_name} ({assigned_user.email})"
    
    return asset_data

def update_tech_asset(db: Session, tech_asset_id: int, tech_asset_update: TechAssetUpdate):
    """
    Actualizar un activo tecnológico.
    
    FIX BUG #3: Ahora valida transiciones de estado.
    
    Args:
        db: Sesión de base de datos
        tech_asset_id: ID del activo a actualizar
        tech_asset_update: Datos a actualizar
        
    Returns:
        TechAsset: Activo actualizado, o None si no existe
        
    Raises:
        ValueError: Si la validación falla
    """
    asset = db.exec(
        select(TechAsset)
        .where(TechAsset.id == tech_asset_id)
        .where(TechAsset.deleted_at.is_(None))
    ).first()
    
    if not asset:
        return None
    
    # Obtener datos de actualización excluyendo campos no establecidos
    update_data = tech_asset_update.dict(exclude_unset=True)
    
    # Verificar unicidad de asset_tag si se está actualizando
    if "asset_tag" in update_data and update_data["asset_tag"]:
        existing_tag = db.exec(
            select(TechAsset)
            .where(TechAsset.asset_tag == update_data["asset_tag"])
            .where(TechAsset.id != tech_asset_id)
            .where(TechAsset.deleted_at.is_(None))
        ).first()
        
        if existing_tag:
            raise ValueError(
                f"Ya existe un activo con la etiqueta: {update_data['asset_tag']}"
            )
    
    # FIX BUG #3: Validar transiciones de estado
    if "status" in update_data and update_data["status"]:
        new_status = AssetStatus(update_data["status"])
        current_status = asset.status
        
        # Validar transición
        validate_state_transition(current_status, new_status)
        
        # Validaciones adicionales según el estado
        if new_status == AssetStatus.ASSIGNED:
            # Verificar que existe una asignación activa
            active_assignment = db.exec(
                select(AssetAssignment)
                .where(AssetAssignment.tech_asset_id == tech_asset_id)
                .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
            ).first()
            
            if not active_assignment:
                raise ValueError(
                    "No se puede cambiar el estado a 'assigned' sin una asignación activa"
                )
        
        elif new_status == AssetStatus.AVAILABLE:
            # Si cambia a available, verificar que no tiene asignaciones activas
            active_assignment = db.exec(
                select(AssetAssignment)
                .where(AssetAssignment.tech_asset_id == tech_asset_id)
                .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
            ).first()
            
            if active_assignment:
                raise ValueError(
                    "No se puede cambiar el estado a 'available' con asignaciones activas. "
                    "Primero devuelve el activo."
                )
    
    # Actualizar campos
    for field, value in update_data.items():
        setattr(asset, field, value)
    
    asset.updated_at = datetime.now(timezone.utc)
    
    db.add(asset)
    db.commit()
    db.refresh(asset)
    
    return asset

def delete_tech_asset(
    db: Session,
    tech_asset_id: int,
    deleted_by_user_id: Optional[int] = None,
    hard_delete: bool = False
) -> bool:
    """
    Eliminar un activo tecnológico.
    
    FIX BUG #2: Implementa soft-delete por defecto con auditoría.
    
    Args:
        db: Sesión de base de datos
        tech_asset_id: ID del activo a eliminar
        deleted_by_user_id: ID del usuario que elimina (para auditoría)
        hard_delete: Si True, elimina físicamente (usar con MUCHO cuidado)
        
    Returns:
        bool: True si se eliminó correctamente
        
    Raises:
        ValueError: Si el activo tiene restricciones que impiden eliminarlo
    """
    asset = db.exec(
        select(TechAsset)
        .where(TechAsset.id == tech_asset_id)
        .where(TechAsset.deleted_at.is_(None))
    ).first()
    
    if not asset:
        return False
    
    # Verificar que no tenga asignaciones activas
    active_assignment = db.exec(
        select(AssetAssignment)
        .where(AssetAssignment.tech_asset_id == tech_asset_id)
        .where(AssetAssignment.status == AssignmentStatus.ACTIVE)
    ).first()
    
    if active_assignment:
        raise ValueError(
            "No se puede eliminar un activo que tiene asignaciones activas"
        )
    
    # Verificar que no tenga mantenimientos pendientes
    from app.models.asset_maintenance import AssetMaintenance, MaintenanceStatus
    
    pending_maintenance = db.exec(
        select(AssetMaintenance)
        .where(AssetMaintenance.tech_asset_id == tech_asset_id)
        .where(AssetMaintenance.status.in_([
            MaintenanceStatus.SCHEDULED,
            MaintenanceStatus.IN_PROGRESS
        ]))
    ).first()
    
    if pending_maintenance:
        raise ValueError(
            "No se puede eliminar un activo con mantenimientos pendientes"
        )
    
    if hard_delete:
        # Hard delete - USAR CON CUIDADO
        db.delete(asset)
        db.commit()
    else:
        # FIX BUG #2: Soft delete con auditoría
        asset.deleted_at = datetime.now(timezone.utc)
        asset.deleted_by_user_id = deleted_by_user_id
        asset.updated_at = datetime.now(timezone.utc)
        
        db.add(asset)
        db.commit()
    
    return True

def restore_tech_asset(
    db: Session,
    tech_asset_id: int,
    restored_by_user_id: Optional[int] = None
) -> Optional[TechAsset]:
    """
    Restaurar un activo eliminado (soft-deleted).
    
    NUEVA FUNCIÓN: Permite recuperar activos eliminados.
    
    Args:
        db: Sesión de base de datos
        tech_asset_id: ID del activo a restaurar
        restored_by_user_id: ID del usuario que restaura
        
    Returns:
        TechAsset: Activo restaurado, o None si no existe
    """
    asset = db.exec(
        select(TechAsset)
        .where(TechAsset.id == tech_asset_id)
        .where(TechAsset.deleted_at.is_not(None))  # Solo eliminados
    ).first()
    
    if not asset:
        return None
    
    # Restaurar
    asset.deleted_at = None
    asset.deleted_by_user_id = None
    asset.updated_at = datetime.now(timezone.utc)
    
    db.add(asset)
    db.commit()
    db.refresh(asset)
    
    return asset

# ============================================================================
# ASSET TAG GENERATION
# ============================================================================


def generate_asset_tag(db: Session, category: AssetCategory) -> str:
    """
    Generar un asset tag único para un activo.
    
    FIX BUG #1: Usa SELECT FOR UPDATE para evitar race conditions.
    
    Formato: {PREFIX}-{NUMBER}
    Ejemplo: NBK-001, DSK-042
    
    Args:
        db: Sesión de base de datos
        category: Categoría del activo
        
    Returns:
        str: Asset tag único generado
    """
    # Prefijos por categoría
    category_prefixes = {
        AssetCategory.NOTEBOOK: "NBK",
        AssetCategory.DESKTOP: "DSK",
        AssetCategory.MONITOR: "MON",
        AssetCategory.TECLADO: "TEC",
        AssetCategory.MOUSE: "MOU",
        AssetCategory.KIT_TECLADO_MOUSE: "KIT",
        AssetCategory.IMPRESORA: "IMP",
        AssetCategory.TABLET: "TAB",
        AssetCategory.CELULAR: "CEL",
        AssetCategory.SERVER: "SRV",
        AssetCategory.ROUTER: "RTR",
        AssetCategory.ACCESORIOS: "ACC",
        AssetCategory.SOFTWARE: "SFT",
        AssetCategory.CABLE: "CAB",
        AssetCategory.OTRO: "OTH"
    }
    
    prefix = category_prefixes.get(category, "GEN")
    
    # FIX BUG #1: Usar SELECT FOR UPDATE para evitar race conditions
    # Esto bloquea las filas hasta que se complete la transacción
    
    # Buscar el último número usado para esta categoría y año
    # con lock para evitar que otros procesos lean el mismo valor
    last_asset = db.exec(
        select(TechAsset)
        .where(TechAsset.asset_tag.startswith(f"{prefix}-"))
        .order_by(TechAsset.asset_tag.desc())
        .limit(1)
        .with_for_update()  # LOCK para evitar race condition
    ).first()
    
    if last_asset and last_asset.asset_tag:
        # Extraer el número del tag
        parts = last_asset.asset_tag.split('-')
        if len(parts) == 3:
            try:
                last_number = int(parts[2])
                new_number = last_number + 1
            except ValueError:
                new_number = 1
        else:
            new_number = 1
    else:
        new_number = 1
    
    # Generar tag con número de 3 dígitos
    asset_tag = f"{prefix}-{new_number:03d}"
    
    # Verificar que no existe (extra safety check)
    existing = db.exec(
        select(TechAsset)
        .where(TechAsset.asset_tag == asset_tag)
    ).first()
    
    if existing:
        # Si existe, intentar con el siguiente número
        new_number += 1
        asset_tag = f"{prefix}-{new_number:03d}"
    
    return asset_tag