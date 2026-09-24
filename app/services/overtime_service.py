from decimal import Decimal
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Session, select, func, case, and_

from app.models.overtime import (
    OvertimeEntry, OvertimeEntryCreate, OvertimeEntryRead,
    OvertimeBalanceRead, OvertimeStatus, OvertimeType, OvertimeEntryReview
)
from app.models.user import User
from app.core.exceptions import (
    ResourceNotFoundError, InvalidOperationError, BusinessRuleViolationError
)


def _build_read(entry: OvertimeEntry) -> OvertimeEntryRead:
    return OvertimeEntryRead(
        id=entry.id,
        user_id=entry.user_id,
        user_full_name=entry.user.full_name if entry.user else "—",
        entry_type=entry.entry_type,
        hours=entry.hours,
        reference_date=entry.reference_date,
        reason=entry.reason,
        status=entry.status,
        review_note=entry.review_note,
        reviewed_at=entry.reviewed_at,
        reviewed_by_full_name=entry.reviewed_by.full_name if entry.reviewed_by else None,
        created_at=entry.created_at,
    )


def create_overtime_entry(
    db: Session,
    data: OvertimeEntryCreate,
    requesting_user_id: int,
) -> OvertimeEntryRead:
    """
    Crea una solicitud de HE o compensatorio.
    
    Regla crítica: si es DEBIT, verifica que el usuario tenga saldo suficiente
    ANTES de crear la solicitud (saldo aprobado, no pendiente).
    """
    # Verificar que el usuario objetivo existe
    user = db.get(User, data.user_id)
    if not user:
        raise ResourceNotFoundError("Usuario", data.user_id)

    # Regla de negocio: no se puede pedir compensatorio sin saldo real aprobado
    if data.entry_type == OvertimeType.DEBIT:
        balance = get_balance(db, data.user_id)
        if data.hours > balance.balance_hours:
            raise BusinessRuleViolationError(
                rule="saldo_overtime",
                reason=(
                    f"Saldo disponible insuficiente. "
                    f"Disponible: {balance.balance_hours}h | Solicitado: {data.hours}h"
                )
            )

    entry = OvertimeEntry(
        user_id=data.user_id,
        entry_type=data.entry_type,
        hours=data.hours,
        reference_date=data.reference_date,
        reason=data.reason,
        requested_by_user_id=requesting_user_id,
        status=OvertimeStatus.PENDING,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _build_read(entry)


def review_entry(
    db: Session,
    entry_id: int,
    review: OvertimeEntryReview,
    reviewer_user_id: int,
) -> OvertimeEntryRead:
    """
    Manager aprueba o rechaza una solicitud PENDING.
    Solo se aceptan status APPROVED o REJECTED.
    """
    if review.status not in (OvertimeStatus.APPROVED, OvertimeStatus.REJECTED):
        raise InvalidOperationError(
            operation="review_entry",
            reason="Solo se puede aprobar (APPROVED) o rechazar (REJECTED)"
        )

    entry = db.get(OvertimeEntry, entry_id)
    if not entry:
        raise ResourceNotFoundError("OvertimeEntry", entry_id)

    if entry.status != OvertimeStatus.PENDING:
        raise InvalidOperationError(
            operation="review_entry",
            reason=f"Solo se pueden revisar entradas PENDING. Estado actual: {entry.status}"
        )

    # Si se aprueba un DEBIT, re-verificar saldo en el momento de aprobación
    # (puede haber cambiado desde que se creó la solicitud)
    if review.status == OvertimeStatus.APPROVED and entry.entry_type == OvertimeType.DEBIT:
        balance = get_balance(db, entry.user_id)
        if entry.hours > balance.balance_hours:
            raise BusinessRuleViolationError(
                rule="saldo_overtime_aprobacion",
                reason=(
                    f"El empleado ya no tiene saldo suficiente para aprobar. "
                    f"Disponible: {balance.balance_hours}h"
                )
            )

    entry.status = review.status
    entry.review_note = review.review_note
    entry.reviewed_by_user_id = reviewer_user_id
    entry.reviewed_at = datetime.now(timezone.utc)
    entry.updated_at = datetime.now(timezone.utc)

    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _build_read(entry)


def cancel_entry(
    db: Session,
    entry_id: int,
    requesting_user_id: int,
) -> OvertimeEntryRead:
    """
    El empleado cancela su propia solicitud PENDING.
    Un manager puede cancelar cualquier solicitud PENDING.
    """
    entry = db.get(OvertimeEntry, entry_id)
    if not entry:
        raise ResourceNotFoundError("OvertimeEntry", entry_id)

    if entry.status != OvertimeStatus.PENDING:
        raise InvalidOperationError(
            operation="cancel_entry",
            reason="Solo se pueden cancelar entradas en estado PENDING"
        )

    entry.status = OvertimeStatus.CANCELLED
    entry.updated_at = datetime.now(timezone.utc)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _build_read(entry)


def get_balance(db: Session, user_id: int) -> OvertimeBalanceRead:
    """
    Calcula el saldo de un usuario directamente en la DB con una sola query.
    Nunca confiar en un campo calculado guardado.
    """
    user = db.get(User, user_id)
    if not user:
        raise ResourceNotFoundError("Usuario", user_id)

    result = db.exec(
        select(
            # Créditos aprobados
            func.coalesce(
                func.sum(
                    case(
                        (and_(
                            OvertimeEntry.entry_type == OvertimeType.CREDIT,
                            OvertimeEntry.status == OvertimeStatus.APPROVED
                        ), OvertimeEntry.hours),
                        else_=0
                    )
                ), Decimal("0")
            ).label("total_credit"),
            # Débitos aprobados
            func.coalesce(
                func.sum(
                    case(
                        (and_(
                            OvertimeEntry.entry_type == OvertimeType.DEBIT,
                            OvertimeEntry.status == OvertimeStatus.APPROVED
                        ), OvertimeEntry.hours),
                        else_=0
                    )
                ), Decimal("0")
            ).label("total_debit"),
            # Créditos pendientes
            func.coalesce(
                func.sum(
                    case(
                        (and_(
                            OvertimeEntry.entry_type == OvertimeType.CREDIT,
                            OvertimeEntry.status == OvertimeStatus.PENDING
                        ), OvertimeEntry.hours),
                        else_=0
                    )
                ), Decimal("0")
            ).label("pending_credit"),
            # Débitos pendientes
            func.coalesce(
                func.sum(
                    case(
                        (and_(
                            OvertimeEntry.entry_type == OvertimeType.DEBIT,
                            OvertimeEntry.status == OvertimeStatus.PENDING
                        ), OvertimeEntry.hours),
                        else_=0
                    )
                ), Decimal("0")
            ).label("pending_debit"),
        ).where(OvertimeEntry.user_id == user_id)
    ).one()

    credit = Decimal(str(result.total_credit))
    debit = Decimal(str(result.total_debit))

    return OvertimeBalanceRead(
        user_id=user_id,
        user_full_name=user.full_name or "—",
        total_credit_hours=credit,
        total_debit_hours=debit,
        balance_hours=credit - debit,
        pending_credit_hours=Decimal(str(result.pending_credit)),
        pending_debit_hours=Decimal(str(result.pending_debit)),
    )


def get_entries(
    db: Session,
    user_id: Optional[int] = None,
    status: Optional[OvertimeStatus] = None,
    entry_type: Optional[OvertimeType] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[OvertimeEntryRead]:
    stmt = select(OvertimeEntry).order_by(OvertimeEntry.created_at.desc())

    if user_id:
        stmt = stmt.where(OvertimeEntry.user_id == user_id)
    if status:
        stmt = stmt.where(OvertimeEntry.status == status)
    if entry_type:
        stmt = stmt.where(OvertimeEntry.entry_type == entry_type)

    stmt = stmt.offset(offset).limit(limit)
    entries = db.exec(stmt).all()
    return [_build_read(e) for e in entries]