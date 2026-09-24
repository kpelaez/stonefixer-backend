"""
app/models/integracion.py

Registro de cada ejecución de un proceso que consulta sistemas externos
(Finnegans). Sirve para saber si los datos están al día y, si no, por qué.

REGLA: `mensaje` nunca debe contener URLs, tokens ni credenciales.
"""
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


class IntegracionEjecucion(SQLModel, table=True):
    __tablename__ = "integracion_ejecucion"

    id: Optional[int] = Field(default=None, primary_key=True)
    proceso: str = Field(max_length=100, index=True)       # ej. "inventario_snapshot"
    fecha_datos: Optional[date] = None                      # qué día se intentó cargar
    iniciado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    finalizado_en: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    estado: str = Field(max_length=20)                      # "ok" | "error"
    tipo_error: Optional[str] = Field(default=None, max_length=30)  # "credenciales" | "finnegans" | "datos" | "otro"
    mensaje: Optional[str] = Field(default=None, max_length=500)
    filas: Optional[int] = None