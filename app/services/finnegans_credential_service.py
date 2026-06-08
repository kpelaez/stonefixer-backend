# app/services/finnegans_credential_service.py
"""
FinnegansCredentialService — gestiona el ciclo de vida del token OAuth2.

Responsabilidades:
  1. Guardar credenciales cifradas con Fernet en BD.
  2. Obtener un token válido (del caché en BD o renovando si expiró).
  3. Exponer el estado del token para la UI de SF.

Flujo de get_valid_token():
  ┌─ Lee config activa de BD
  ├─ Descifra con Fernet
  ├─ ¿token_expires_at > ahora + 5 min? → devuelve token del caché
  └─ Si no → llama GET /oauth/token → persiste nuevo token cifrado → devuelve

El margen de 5 minutos evita que el token expire durante una
consulta masiva de N productos en paralelo.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlmodel import Session, select

from app.config import settings
from app.core.exceptions import InvalidOperationError, ResourceNotFoundError
from app.models.finnegans_config import FinnegansConfig
from app.schemas.finnegans_config import FinnegansConfigCreate, FinnegansTokenStatus

logger = logging.getLogger(__name__)

# Margen de seguridad antes de la expiración real del token (Finnegans dura 1h)
_TOKEN_MARGIN_MINUTES = 5

# URL de autenticación OAuth2 de Finnegans
_AUTH_URL = "https://api.finneg.com/api/oauth/token"


class FinnegansCredentialService:

    # ------------------------------------------------------------------
    # Cifrado / Descifrado con Fernet
    # ------------------------------------------------------------------

    @staticmethod
    def _cifrar(texto: str) -> str:
        """Cifra un string con la Fernet key del proyecto."""
        from cryptography.fernet import Fernet
        fernet = Fernet(settings.DNI_ENCRYPTION_KEY.encode())
        return fernet.encrypt(texto.encode()).decode()

    @staticmethod
    def _descifrar(texto_cifrado: str) -> str:
        """Descifra un string con la Fernet key del proyecto."""
        from cryptography.fernet import Fernet
        fernet = Fernet(settings.DNI_ENCRYPTION_KEY.encode())
        return fernet.decrypt(texto_cifrado.encode()).decode()

    # ------------------------------------------------------------------
    # Config en BD
    # ------------------------------------------------------------------

    @staticmethod
    def get_config_activa(db: Session) -> Optional[FinnegansConfig]:
        """Retorna la configuración activa o None si no existe."""
        return db.exec(
            select(FinnegansConfig)
            .where(FinnegansConfig.activa == True)
            .order_by(FinnegansConfig.configurado_en.desc())
        ).first()

    @staticmethod
    def guardar_credenciales(
        db: Session,
        payload: FinnegansConfigCreate,
        user_id: int,
    ) -> FinnegansConfig:
        """
        Guarda o actualiza las credenciales en BD.
        El client_secret se cifra con Fernet antes de persistir.
        Si ya existe una config activa, la desactiva (solo 1 config activa).
        """
        # Desactivar config anterior si existe
        config_anterior = FinnegansCredentialService.get_config_activa(db)
        if config_anterior:
            config_anterior.activa = False
            db.add(config_anterior)

        nueva_config = FinnegansConfig(
            client_id=payload.client_id,
            client_secret_encrypted=FinnegansCredentialService._cifrar(
                payload.client_secret
            ),
            configurado_por_user_id=user_id,
        )
        db.add(nueva_config)
        db.commit()
        db.refresh(nueva_config)

        logger.info(
            f"[FinnegansConfig] Credenciales actualizadas por user_id={user_id}"
        )
        return nueva_config

    # ------------------------------------------------------------------
    # Token OAuth2
    # ------------------------------------------------------------------

    @staticmethod
    def _token_esta_vigente(config: FinnegansConfig) -> bool:
        """
        Retorna True si el token actual todavía es válido
        con el margen de seguridad de 5 minutos.
        """
        if not config.access_token_encrypted or not config.token_expires_at:
            return False

        ahora = datetime.now(timezone.utc)
        # token_expires_at puede venir sin tzinfo desde la BD
        expires = config.token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        return expires > ahora + timedelta(minutes=_TOKEN_MARGIN_MINUTES)

    @staticmethod
    async def _solicitar_token_nuevo(
        client_id: str, client_secret: str
    ) -> dict:
        """
        Llama a GET /oauth/token con client_credentials.
        Retorna el JSON completo de Finnegans:
          Token, User, Domain, Server, CreatedAt, ExpiresAt, ...
        """
        async with httpx.AsyncClient(timeout=30.0) as http:
            response = await http.get(
                _AUTH_URL,
                params={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "detailed": "1",
                },
            )

        if response.status_code != 200:
            raise InvalidOperationError(
                operation="solicitar_token_finnegans",
                reason=f"HTTP {response.status_code}: {response.text[:200]}",
            )

        data = response.json()
        if not data.get("Token"):
            raise InvalidOperationError(
                operation="solicitar_token_finnegans",
                reason=f"Respuesta inesperada de Finnegans: {str(data)[:200]}",
            )

        logger.info(
            f"[FinnegansAuth] Token obtenido para user={data.get('User')} "
            f"expira={data.get('ExpiresAt')}"
        )
        return data

    @staticmethod
    async def get_valid_token(db: Session) -> str:
        """
        Entry point principal — devuelve siempre un token válido.

        1. Lee config activa de BD.
        2. Si el token en caché no expiró → lo devuelve directamente.
        3. Si expiró (o no existe) → pide uno nuevo y lo persiste cifrado.

        Raises:
            ResourceNotFoundError: si no hay config cargada en SF.
            InvalidOperationError: si Finnegans rechaza las credenciales.
        """
        config = FinnegansCredentialService.get_config_activa(db)
        if not config:
            raise ResourceNotFoundError("FinnegansConfig", 0)

        # Caché vigente — no necesitamos llamar a Finnegans
        if FinnegansCredentialService._token_esta_vigente(config):
            logger.debug("[FinnegansAuth] Usando token del caché (BD)")
            return FinnegansCredentialService._descifrar(
                config.access_token_encrypted
            )

        # Token expirado o inexistente — renovar
        logger.info("[FinnegansAuth] Token expirado o ausente — solicitando nuevo")
        client_secret = FinnegansCredentialService._descifrar(
            config.client_secret_encrypted
        )

        token_data = await FinnegansCredentialService._solicitar_token_nuevo(
            config.client_id, client_secret
        )

        # Parsear ExpiresAt — formato ISO 8601 de Finnegans: "2026-06-07T21:38:14.905732355Z"
        expires_at = datetime.fromisoformat(
            token_data["ExpiresAt"].replace("Z", "+00:00")
        )
        created_at = datetime.fromisoformat(
            token_data["CreatedAt"].replace("Z", "+00:00")
        )

        # Persistir token cifrado + metadata
        config.access_token_encrypted = FinnegansCredentialService._cifrar(
            token_data["Token"]
        )
        config.token_created_at = created_at
        config.token_expires_at = expires_at
        config.finnegans_user = token_data.get("User")
        config.domain = token_data.get("Domain")
        config.server = token_data.get("Server")
        config.actualizado_en = datetime.now(timezone.utc)

        db.add(config)
        db.commit()

        return token_data["Token"]

    # ------------------------------------------------------------------
    # Estado para la UI
    # ------------------------------------------------------------------

    @staticmethod
    def get_token_status(db: Session) -> FinnegansTokenStatus:
        """Estado del token para mostrar en el panel de admin de SF."""
        config = FinnegansCredentialService.get_config_activa(db)

        if not config or not config.token_expires_at:
            return FinnegansTokenStatus(
                tiene_token=False,
                token_valido=False,
                token_expires_at=None,
                finnegans_user=None,
                domain=None,
                minutos_restantes=None,
            )

        vigente = FinnegansCredentialService._token_esta_vigente(config)

        expires = config.token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        minutos = int(
            (expires - datetime.now(timezone.utc)).total_seconds() / 60
        )

        return FinnegansTokenStatus(
            tiene_token=True,
            token_valido=vigente,
            token_expires_at=config.token_expires_at,
            finnegans_user=config.finnegans_user,
            domain=config.domain,
            minutos_restantes=max(0, minutos),
        )