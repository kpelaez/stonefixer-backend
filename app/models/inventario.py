"""
app/models/inventario.py

TEMPORAL (sep-2026): snapshots diarios de stock traídos de Finnegans.
Viven en la base de StoneFixer para la presentación; migrar al lakehouse
(ver work item en Plane) y eliminar esta tabla.

Granularidad: 1 fila por fecha + depósito + rubro + familia.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import UniqueConstraint, DateTime
from sqlmodel import Field, SQLModel


class InventarioSnapshot(SQLModel, table=True):
    __tablename__ = "inventario_snapshot"
    __table_args__ = (
        UniqueConstraint("fecha", "deposito_id", "rubro", "familia", name="uq_inventario_snapshot_clave"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    fecha: date = Field(index=True)
    deposito_id: int
    deposito: str = Field(max_length=200)
    # "" en vez de NULL: en PostgreSQL dos NULL nunca son iguales, así que
    # el UniqueConstraint no detectaría duplicados con rubro o familia vacíos.
    rubro: str = Field(default="", max_length=200)
    familia: str = Field(default="", max_length=200)
    unidades: Decimal = Field(max_digits=18, decimal_places=4)
    importe_usd: Decimal = Field(max_digits=18, decimal_places=2)
    importe_ars: Decimal = Field(max_digits=20, decimal_places=2)
    creado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )