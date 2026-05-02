from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.db.database import get_db
from app.models.user import User
from app.models.overtime import (
    OvertimeEntryCreate, OvertimeEntryRead, OvertimeEntryReview,
    OvertimeBalanceRead, OvertimeStatus, OvertimeType
)
from app.api.deps import get_current_user, require_roles
from app.services.overtime_service import (
    create_overtime_entry, review_entry, cancel_entry,
    get_balance, get_entries
)

router = APIRouter()

MANAGER_ROLES = ["admin", "manager"]


@router.post("/", response_model=OvertimeEntryRead, status_code=201)
def create_entry(
    data: OvertimeEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crear solicitud de HE (CREDIT) o compensatorio (DEBIT).
    Cualquier usuario autenticado puede crear para sí mismo.
    Managers/Admin pueden crear para cualquier usuario.
    """
    user_roles = [r.role for r in current_user.roles]
    is_manager = any(r in MANAGER_ROLES for r in user_roles)

    # Empleado solo puede crear solicitudes para sí mismo
    if not is_manager and data.user_id != current_user.id:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes crear solicitudes para tu propio usuario"
        )

    return create_overtime_entry(db, data, requesting_user_id=current_user.id)


@router.patch("/{entry_id}/review", response_model=OvertimeEntryRead)
def review(
    entry_id: int,
    review_data: OvertimeEntryReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(MANAGER_ROLES)),
):
    """Aprobar o rechazar una solicitud. Solo managers/admin."""
    return review_entry(db, entry_id, review_data, reviewer_user_id=current_user.id)


@router.patch("/{entry_id}/cancel", response_model=OvertimeEntryRead)
def cancel(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancelar solicitud PENDING. El empleado cancela la suya; managers cualquiera."""
    user_roles = [r.role for r in current_user.roles]
    is_manager = any(r in MANAGER_ROLES for r in user_roles)
    return cancel_entry(db, entry_id, requesting_user_id=current_user.id)


@router.get("/balance/{user_id}", response_model=OvertimeBalanceRead)
def balance(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Saldo de un usuario. El empleado solo puede ver el suyo.
    Managers pueden ver el de cualquiera.
    """
    user_roles = [r.role for r in current_user.roles]
    is_manager = any(r in MANAGER_ROLES for r in user_roles)

    if not is_manager and user_id != current_user.id:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=403, detail="Sin permisos para ver este saldo")

    return get_balance(db, user_id)


@router.get("/", response_model=list[OvertimeEntryRead])
def list_entries(
    user_id: Optional[int] = Query(None),
    status: Optional[OvertimeStatus] = Query(None),
    entry_type: Optional[OvertimeType] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Listar entradas. Empleados solo ven las suyas.
    Managers ven todas (pueden filtrar por user_id).
    """
    user_roles = [r.role for r in current_user.roles]
    is_manager = any(r in MANAGER_ROLES for r in user_roles)

    # Forzar filtro propio si no es manager
    effective_user_id = user_id if is_manager else current_user.id

    return get_entries(db, user_id=effective_user_id, status=status,
                       entry_type=entry_type, limit=limit, offset=offset)