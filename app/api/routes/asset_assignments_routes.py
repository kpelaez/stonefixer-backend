from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.db.database import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User

from app.models.asset_assignment import (
    AssetAssignment,
    AssetAssignmentCreate,
    AssetAssignmentRead,
    AssetAssignmentUpdate,
    AssetAssignmentWithDetails,
    AssetReturn,
    AssignmentStatus,
    UserAssignmentSummary
)
from app.services.asset_assignment_service import (
    create_assignment,
    get_asset_assignments,
    get_assignment,
    get_assignments,
    update_assignment,
    delete_assignment,
    return_asset,
    transfer_asset,
    get_user_assignments,
    get_users_assignment_summary,
    get_assignment_statistics
)

router = APIRouter()


@router.post("/", response_model=AssetAssignmentRead, status_code=status.HTTP_201_CREATED)
# @require_roles(["admin", "inventory_manager"])
async def assign_asset(assignment: AssetAssignmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Asignar un activo tecnologico a un usuario"""

    try:
        print(f"Received assignment data: {assignment}")
        result = create_assignment(db, assignment, current_user.id)
        print(f"Created assignment: {result}")
        return result
    except ValueError as e:
        print(f"ValueError creating assignment: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Unexpected error creating assignment: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor")


@router.get("/", response_model=List[AssetAssignmentWithDetails])
async def get_assignments_endpoint(user_id: Optional[int] = None, asset_id: Optional[int] = None, active_only: bool = False, db: Session = Depends(get_db)):
    """"Obtener lista de asignaciones de activos"""
    return get_assignments(
        db=db,
        user_id=user_id,
        asset_id= asset_id,
        active_only=active_only
    )

@router.get("/{assignment_id}", response_model=AssetAssignmentWithDetails)
async def get_assignment_endpoint(assignment_id: int, db: Session = Depends(get_db)):
    """Obtener una asignacion especifica"""

    assignment = get_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException( status_code=status.HTTP_404_NOT_FOUND, detail="Asignacion no encontrada")
    
    return assignment

@router.patch("/{assignment_id}", response_model=AssetAssignmentRead)
# @require_roles(["admin", "inventory_manager"])
async def update_assignment_endpoint(assignment_id: int, assignment_update: AssetAssignmentUpdate, db: Session = Depends(get_db)):
    """Actualizar una asignacion"""
    assignment = update_assignment(db, assignment_id, assignment_update)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asignacion no encontrada")
    
    return assignment

@router.post("/{assignment_id}/return", response_model=AssetAssignmentRead)
#@require_roles(["admin", "inventory_manager"])
async def return_asset_endpoint(assignment_id: int, return_data: AssetReturn, db: Session = Depends(get_db)):
    """Marcar un activo como devuelto"""
    try:
        assignment = return_asset(db, assignment_id, return_data)
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asignacion no encontrada")
        return assignment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
@router.post("/{assignment_id}/transfer", response_model=AssetAssignmentRead)
# @require_roles(["admin", "inventory_manager"])
async def transfer_asset_endpoint(assignment_id: int, new_user_id: int, transfer_notes: Optional[str] = None, db: Session = Depends(get_db)):
    """Transferir un activo de un usuario a otro"""
    try:
        new_assignment = transfer_asset(db, assignment_id, new_user_id, transfer_notes)
        return new_assignment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
#@require_roles(["admin", "inventory_manager"])
async def unassing_asset(assignment_id: int, db: Session = Depends(get_db)):
    """Desasignar un activo (marcar como devuelto)"""
    success = delete_assignment(db, assignment_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asignacion no encontrada")
    
    return None

@router.get("/user/{user_id}", response_model=List[AssetAssignmentWithDetails])
async def get_user_assignments_endpoint(user_id: int, active_only: bool = True, db: Session = Depends(get_db)):
    """Obtener asignaciones de un usuario especifico"""
    # Verificar que el usuario exista
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    return get_user_assignments(db, user_id, active_only)

@router.get("/asset/{asset_id}/history", response_model=List[AssetAssignmentWithDetails])
async def get_asset_assignments_endpoint(asset_id:int, db: Session = Depends(get_db)):
    """Obtener historial de asignaciones de un activo especifico"""
    from app.services.tech_asset_service import get_tech_asset

    # Verificar que el activo exista
    asset = get_tech_asset(db, asset_id)
    if not asset: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo tecnologico no encontrado") 

    return get_asset_assignments(db, asset_id)

@router.get("/statistics/overview")
async def get_assignment_statistics_endpoint(db: Session = Depends(get_db)):
    """Obtener estadisticas de asignaciones"""
    return get_assignment_statistics(db)

@router.get("/users/summary", response_model=List[UserAssignmentSummary])
async def get_users_assignment_summary_endpoint(db: Session = Depends(get_db)):
    """Obtener resumen de asignaciones por usuarios"""
    return get_users_assignment_summary(db)

@router.get("/my-assets", response_model=List[AssetAssignmentWithDetails])
async def get_my_assignments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Obtener activos asignados al usuario actual"""
    return get_user_assignments(db, current_user.id, active_only=True)