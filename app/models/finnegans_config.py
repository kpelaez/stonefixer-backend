# app/models/finnegans_config.py
"""
Configuración de credenciales Finnegans persistida en BD.

Una sola fila activa por dominio (upsert al guardar).
client_secret, access_token y refresh_token se almacenan
SIEMPRE cifrados con Fernet — nunca en texto plano.

Campos públicos (no sensibles):
  - client_id, finnegans_user, domain, server
  - token_expires_at, token_created_at
  - configurado_por_user_id, configurado_en

Campos cifrados:
  - client_secret_encrypted
  - access_token_encrypted
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class FinnegansConfig(SQLModel, table=True):
    __tablename__ = "finnegans_config"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Credenciales OAuth2 — client_id es público, secret va cifrado
    client_id: str = Field(max_length=200)
    client_secret_encrypted: str = Field(
        description="client_secret cifrado con Fernet. NUNCA texto plano."
    )

    # Token activo — cifrado + metadata de expiración
    access_token_encrypted: Optional[str] = Field(
        default=None,
        description="access_token cifrado con Fernet.",
    )
    token_created_at: Optional[datetime] = Field(default=None)
    token_expires_at: Optional[datetime] = Field(default=None)

    # Info del usuario Finnegans (viene en la respuesta de /oauth/token)
    finnegans_user: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Email del usuario Finnegans (ej: kpelaez@omnimedica.com.ar)",
    )
    domain: Optional[str] = Field(default=None, max_length=200)
    server: Optional[str] = Field(default=None, max_length=500)

    # Auditoría
    configurado_por_user_id: int = Field(foreign_key="user.id")
    configurado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    actualizado_en: Optional[datetime] = Field(default=None)

    # ¿Está activa esta config?
    activa: bool = Field(default=True)


class FinnegansConfigRead(SQLModel):
    """Schema de lectura — NUNCA expone campos cifrados."""
    id: int
    client_id: str
    finnegans_user: Optional[str]
    domain: Optional[str]
    server: Optional[str]
    token_created_at: Optional[datetime]
    token_expires_at: Optional[datetime]
    configurado_por_user_id: int
    configurado_en: datetime
    actualizado_en: Optional[datetime]
    activa: bool

    # Campo calculado: ¿el token sigue vigente?
    token_valido: bool = False