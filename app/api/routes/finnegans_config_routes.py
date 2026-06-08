# app/api/routes/finnegans_config_routes.py
"""
Router de configuración de Finnegans.

Endpoints (solo admin):
  GET  /finnegans-config/          → ver config activa + estado del token
  POST /finnegans-config/          → cargar/actualizar credenciales
  POST /finnegans-config/renovar-token → forzar renovación del token
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import get_current_user, RoleChecker
from app.core.exceptions import InvalidOperationError, ResourceNotFoundError
from app.db.database import get_db
from app.models.user import User
from app.schemas.finnegans_config import (
    FinnegansConfigCreate,
    FinnegansConfigResponse,
    FinnegansTokenStatus,
)
from app.services.finnegans_credential_service import FinnegansCredentialService

router = APIRouter()
logger = logging.getLogger(__name__)

# Solo admins pueden tocar la config de Finnegans
_solo_admin = RoleChecker(["admin"])


@router.get("/", response_model=FinnegansConfigResponse)
def get_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "manager"])),
):
    """
    Retorna la configuración activa de Finnegans con el estado del token.
    Managers pueden ver el estado pero no modificarlo.
    """
    config = FinnegansCredentialService.get_config_activa(db)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No hay credenciales de Finnegans configuradas. "
                "Un admin debe cargarlas desde este endpoint."
            ),
        )

    token_status = FinnegansCredentialService.get_token_status(db)

    return FinnegansConfigResponse(
        id=config.id,
        client_id=config.client_id,
        finnegans_user=config.finnegans_user,
        domain=config.domain,
        server=config.server,
        token_created_at=config.token_created_at,
        token_expires_at=config.token_expires_at,
        configurado_por_user_id=config.configurado_por_user_id,
        configurado_en=config.configurado_en,
        actualizado_en=config.actualizado_en,
        activa=config.activa,
        token_status=token_status,
    )


@router.post("/", response_model=FinnegansConfigResponse, status_code=status.HTTP_201_CREATED)
async def guardar_credenciales(
    payload: FinnegansConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_solo_admin),
):
    """
    Carga o actualiza las credenciales de Finnegans.
    Inmediatamente solicita un token nuevo para validar que las credenciales son correctas.
    Solo admin.
    """
    try:
        config = FinnegansCredentialService.guardar_credenciales(
            db, payload, current_user.id
        )

        # Validar credenciales solicitando un token inmediatamente
        logger.info(
            f"[FinnegansConfig] Validando credenciales para user_id={current_user.id}"
        )
        await FinnegansCredentialService.get_valid_token(db)

        # Refrescar config con los datos del token recién obtenido
        db.refresh(config)
        token_status = FinnegansCredentialService.get_token_status(db)

        return FinnegansConfigResponse(
            id=config.id,
            client_id=config.client_id,
            finnegans_user=config.finnegans_user,
            domain=config.domain,
            server=config.server,
            token_created_at=config.token_created_at,
            token_expires_at=config.token_expires_at,
            configurado_por_user_id=config.configurado_por_user_id,
            configurado_en=config.configurado_en,
            actualizado_en=config.actualizado_en,
            activa=config.activa,
            token_status=token_status,
        )

    except InvalidOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Credenciales inválidas: {exc.message}",
        )
    except Exception:
        logger.exception("[FinnegansConfig] Error al guardar credenciales")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al guardar credenciales",
        )


@router.post("/renovar-token", response_model=FinnegansTokenStatus)
async def renovar_token(
    db: Session = Depends(get_db),
    current_user: User = Depends(_solo_admin),
):
    """
    Fuerza la renovación del token aunque no haya expirado.
    Útil si el token fue revocado o hay problemas de autenticación.
    Solo admin.
    """
    config = FinnegansCredentialService.get_config_activa(db)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay credenciales configuradas.",
        )

    # Invalidar token actual para forzar renovación
    config.access_token_encrypted = None
    config.token_expires_at = None
    db.commit()

    try:
        await FinnegansCredentialService.get_valid_token(db)
        token_status = FinnegansCredentialService.get_token_status(db)
        logger.info(
            f"[FinnegansConfig] Token renovado manualmente por user_id={current_user.id}"
        )
        return token_status

    except InvalidOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error al renovar token: {exc.message}",
        )