from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from datetime import datetime, timedelta

from app.db.database import get_db
from app.models.tech_asset import TechAsset, AssetStatus
from app.models.asset_assignment import AssetAssignment, AssignmentStatus
from app.models.asset_maintenance import AssetMaintenance, MaintenanceStatus
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/metrics")
async def get_dashboard_metrics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Obtener métricas para el dashboard de inventario"""
    
    # Métricas de activos
    total_assets = db.scalar(select(func.count(TechAsset.id)))
    available_assets = db.scalar(
        select(func.count(TechAsset.id)).where(TechAsset.status == AssetStatus.AVAILABLE)
    )
    assigned_assets = db.scalar(
        select(func.count(TechAsset.id)).where(TechAsset.status == AssetStatus.ASSIGNED)
    )
    maintenance_assets = db.scalar(
        select(func.count(TechAsset.id)).where(TechAsset.status == AssetStatus.IN_MAINTENANCE)
    )
    
    # Valor total del inventario
    total_value = db.scalar(select(func.sum(TechAsset.purchase_price))) or 0
    
    # Métricas de asignaciones
    active_assignments = db.scalar(
        select(func.count(AssetAssignment.id)).where(
            AssetAssignment.status == AssignmentStatus.ACTIVE
        )
    )
    
    # Métricas de mantenimientos
    pending_maintenances = db.scalar(
        select(func.count(AssetMaintenance.id)).where(
            AssetMaintenance.status == MaintenanceStatus.SCHEDULED
        )
    )
    
    # Mantenimientos vencidos (scheduled pero con fecha pasada)
    today = datetime.now().date()
    overdue_maintenances = db.scalar(
        select(func.count(AssetMaintenance.id)).where(
            AssetMaintenance.status == MaintenanceStatus.SCHEDULED,
            AssetMaintenance.scheduled_date < today
        )
    )
    
    # Próximos mantenimientos (próximos 30 días)
    next_month = today + timedelta(days=30)
    upcoming_maintenances = db.scalar(
        select(func.count(AssetMaintenance.id)).where(
            AssetMaintenance.status == MaintenanceStatus.SCHEDULED,
            AssetMaintenance.scheduled_date.between(today, next_month)
        )
    )
    
    return {
        "total_assets": total_assets or 0,
        "available_assets": available_assets or 0,
        "assigned_assets": assigned_assets or 0,
        "maintenance_assets": maintenance_assets or 0,
        "total_value": float(total_value),
        "active_assignments": active_assignments or 0,
        "pending_maintenances": pending_maintenances or 0,
        "overdue_maintenances": overdue_maintenances or 0,
        "upcoming_maintenances": upcoming_maintenances or 0,
        "last_updated": datetime.now().isoformat()
    }

@router.get("/recent-activity")
async def get_recent_activity(db: Session = Depends(get_db), limit: int = 10):
    """Obtener actividad reciente del sistema"""
    
    # Últimas asignaciones
    recent_assignments = db.exec(
        select(AssetAssignment)
        .order_by(AssetAssignment.assigned_date.desc())
        .limit(limit // 2)
    ).all()
    
    # Últimos mantenimientos
    recent_maintenances = db.exec(
        select(AssetMaintenance)
        .order_by(AssetMaintenance.created_at.desc())
        .limit(limit // 2)
    ).all()
    
    # Combinar y formatear actividad
    activities = []
    
    for assignment in recent_assignments:
        activities.append({
            "type": "assignment",
            "title": f"Activo asignado",
            "description": f"Activo {assignment.tech_asset_id} asignado a usuario {assignment.user_id}",
            "date": assignment.assigned_date,
            "status": assignment.status.value
        })
    
    for maintenance in recent_maintenances:
        activities.append({
            "type": "maintenance",
            "title": f"Mantenimiento {maintenance.type.value}",
            "description": f"Activo {maintenance.tech_asset_id} - {maintenance.description[:50]}...",
            "date": maintenance.created_at,
            "status": maintenance.status.value
        })
    
    # Ordenar por fecha
    activities.sort(key=lambda x: x["date"], reverse=True)
    
    return activities[:limit]

@router.get("/alerts")
async def get_system_alerts(db: Session = Depends(get_db)):
    """Obtener alertas del sistema"""
    
    alerts = []
    today = datetime.now().date()
    
    # Mantenimientos vencidos
    overdue_count = db.scalar(
        select(func.count(AssetMaintenance.id)).where(
            AssetMaintenance.status == MaintenanceStatus.SCHEDULED,
            AssetMaintenance.scheduled_date < today
        )
    )
    
    if overdue_count and overdue_count > 0:
        alerts.append({
            "type": "error",
            "title": "Mantenimientos Vencidos",
            "message": f"{overdue_count} mantenimientos requieren atención inmediata",
            "action": "/inventory/maintenance?status=overdue"
        })
    
    # Próximos mantenimientos (próximos 7 días)
    week_ahead = today + timedelta(days=7)
    upcoming_count = db.scalar(
        select(func.count(AssetMaintenance.id)).where(
            AssetMaintenance.status == MaintenanceStatus.SCHEDULED,
            AssetMaintenance.scheduled_date.between(today, week_ahead)
        )
    )
    
    if upcoming_count and upcoming_count > 0:
        alerts.append({
            "type": "warning",
            "title": "Mantenimientos Próximos",
            "message": f"{upcoming_count} mantenimientos programados para esta semana",
            "action": "/inventory/maintenance?status=scheduled"
        })
    
    # Activos sin asignar por mucho tiempo (más de 30 días)
    month_ago = today - timedelta(days=30)
    unassigned_count = db.scalar(
        select(func.count(TechAsset.id)).where(
            TechAsset.status == AssetStatus.AVAILABLE,
            TechAsset.created_at < month_ago
        )
    )
    
    if unassigned_count and unassigned_count > 5:
        alerts.append({
            "type": "info",
            "title": "Activos Sin Asignar",
            "message": f"{unassigned_count} activos disponibles por más de 30 días",
            "action": "/inventory/assets?status=available"
        })
    
    return alerts