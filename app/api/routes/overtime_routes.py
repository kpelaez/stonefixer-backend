from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import Session

from app.db.database import get_db
from app.models.user import User
from app.models.overtime import (
    OvertimeEntryCreate, OvertimeEntryRead, OvertimeEntryReview,
    OvertimeBalanceRead, OvertimeStatus, OvertimeType
)
from app.api.deps import get_current_user
from app.services.overtime_service import (
    create_overtime_entry, review_entry, cancel_entry,
    get_balance, get_entries
)
from app.core.rate_limiter import limiter
from app.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

MANAGER_ROLES = ["admin", "manager"]


def _is_manager(user: User) -> bool:
    return any(r.role in MANAGER_ROLES for r in user.roles)


@router.post("/", response_model=OvertimeEntryRead, status_code=201)
@limiter.limit(settings.WRITE_RATE_LIMIT)
async def create_entry(
    request: Request,
    data: OvertimeEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_manager(current_user) and data.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo podés crear solicitudes para tu propio usuario"
        )
    return create_overtime_entry(db, data, requesting_user_id=current_user.id)


@router.patch("/{entry_id}/review", response_model=OvertimeEntryRead)
@limiter.limit(settings.WRITE_RATE_LIMIT)
async def review(
    request: Request,
    entry_id: int,
    review_data: OvertimeEntryReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_manager(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo managers o administradores pueden revisar solicitudes"
        )
    return review_entry(db, entry_id, review_data, reviewer_user_id=current_user.id)


@router.patch("/{entry_id}/cancel", response_model=OvertimeEntryRead)
@limiter.limit(settings.WRITE_RATE_LIMIT)
async def cancel(
    request: Request,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return cancel_entry(db, entry_id, requesting_user_id=current_user.id)


@router.get("/balance/{user_id}", response_model=OvertimeBalanceRead)
@limiter.limit(settings.READ_RATE_LIMIT)
async def balance(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_manager(current_user) and user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés permisos para ver el saldo de otro usuario"
        )
    return get_balance(db, user_id)


@router.get("/", response_model=list[OvertimeEntryRead])
@limiter.limit(settings.READ_RATE_LIMIT)
async def list_entries(
    request: Request,
    user_id: Optional[int] = Query(None),
    status: Optional[OvertimeStatus] = Query(None),
    entry_type: Optional[OvertimeType] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    effective_user_id = user_id if _is_manager(current_user) else current_user.id
    return get_entries(
        db, user_id=effective_user_id,
        status=status, entry_type=entry_type,
        limit=limit, offset=offset
    )