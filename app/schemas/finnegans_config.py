# app/schemas/finnegans_config.py
"""
Schemas de request/response para la configuración de Finnegans.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FinnegansConfigCreate(BaseModel):
    """Payload para cargar o actualizar credenciales desde la UI de SF."""
    client_id: str = Field(min_length=1, max_length=200)
    client_secret: str = Field(
        min_length=1,
        description="Se cifra con Fernet antes de persistir. Nunca se devuelve.",
    )


class FinnegansTokenStatus(BaseModel):
    """Estado del token actual — para mostrar en la UI de SF."""
    tiene_token: bool
    token_valido: bool
    token_expires_at: Optional[datetime]
    finnegans_user: Optional[str]
    domain: Optional[str]
    minutos_restantes: Optional[int] = Field(
        default=None,
        description="Minutos hasta que expira el token. None si no hay token.",
    )


class FinnegansConfigResponse(BaseModel):
    """Respuesta completa del endpoint de config — sin campos sensibles."""
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
    token_status: FinnegansTokenStatus