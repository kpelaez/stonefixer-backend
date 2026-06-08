# app/models/inventario_stock.py
"""
Modelos SQLModel para el módulo Inventario de Stock.

Tablas:
  - inventario_relevamiento          → cabecera del ciclo
  - inventario_relevamiento_serie    → 1 fila por serie extraída
  - inventario_relevamiento_diferencia → análisis post-conteo
  - inventario_relevamiento_ajuste   → ajustes autorizados en Finnegans

Convenciones del proyecto:
  - Enums como `str, Enum` + sa_column=Column(String) para evitar
    el procesador nativo de PostgreSQL en SQLAlchemy.
  - Timestamps en UTC con `datetime.now(timezone.utc)`.
  - FK explícitas con `foreign_key=` en Field.
  - Read-schemas en el mismo archivo, Create/Update en schemas/.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from sqlalchemy import String
from sqlmodel import Column, Field, Relationship, SQLModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EstadoRelevamiento(str, Enum):
    PENDIENTE = "pendiente"         # creado, sin scraping
    EXTRAYENDO = "extrayendo"       # scraper corriendo (background task)
    LISTO = "listo"                 # scraping OK, planilla lista para descargar
    EN_CONTEO = "en_conteo"         # equipo cargando resultados físicos
    ANALIZADO = "analizado"         # diferencias generadas
    CERRADO = "cerrado"             # acta firmada


class EstadoSerie(str, Enum):
    """Estado reportado por Omnimedica"""
    ALTA = "alta"
    KIT = "kit"                     # en tránsito (kit con número)


class ResultadoFisico(str, Enum):
    PRESENTE = "presente"
    EN_TRANSITO = "en_transito"
    NO_ENCONTRADA = "no_encontrada"


class TipoDiferencia(str, Enum):
    CANT_OMNI_VS_FINN = "cant_omni_vs_finn"     # cantidad no coincide entre sistemas
    SERIE_NO_ENCONTRADA = "serie_no_encontrada"  # serie no apareció en conteo físico
    INGRESO_NO_REGISTRADO = "ingreso_no_reg"     # físicamente presente, no en sistema
    LOTE_POR_VENCER = "lote_por_vencer"          # vencimiento < 90 días


class EstadoAjuste(str, Enum):
    PENDIENTE = "pendiente"
    AUTORIZADO = "autorizado"
    RECHAZADO = "rechazado"
    APLICADO = "aplicado"


# ---------------------------------------------------------------------------
# inventario_relevamiento  (cabecera del ciclo)
# ---------------------------------------------------------------------------


class InventarioRelevamientoBase(SQLModel):
    proveedor: str = Field(max_length=100, description="Nombre del proveedor / empresa")
    mes_ciclo: str = Field(
        max_length=7,
        description="Mes del ciclo en formato YYYY-MM",
        regex=r"^\d{4}-\d{2}$",
    )


class InventarioRelevamiento(InventarioRelevamientoBase, table=True):
    __tablename__ = "inventario_relevamiento"

    id: Optional[int] = Field(default=None, primary_key=True)

    estado: EstadoRelevamiento = Field(
        default=EstadoRelevamiento.PENDIENTE,
        sa_column=Column(String, nullable=False, default="pendiente"),
    )

    # Auditoría
    creado_por_user_id: int = Field(foreign_key="user.id")
    creado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    actualizado_en: Optional[datetime] = Field(default=None)

    # Metadata del scraping
    total_series_omni: Optional[int] = Field(default=None)
    total_codigos_finn: Optional[int] = Field(default=None)
    scraping_iniciado_en: Optional[datetime] = Field(default=None)
    scraping_finalizado_en: Optional[datetime] = Field(default=None)
    scraping_error: Optional[str] = Field(default=None, max_length=500)

    # Relaciones
    series: List["InventarioRelevamientoSerie"] = Relationship(
        back_populates="relevamiento"
    )
    diferencias: List["InventarioRelevamientoDiferencia"] = Relationship(
        back_populates="relevamiento"
    )
    ajustes: List["InventarioRelevamientoAjuste"] = Relationship(
        back_populates="relevamiento"
    )


class InventarioRelevamientoRead(InventarioRelevamientoBase):
    id: int
    estado: EstadoRelevamiento
    creado_por_user_id: int
    creado_en: datetime
    actualizado_en: Optional[datetime]
    total_series_omni: Optional[int]
    total_codigos_finn: Optional[int]
    scraping_iniciado_en: Optional[datetime]
    scraping_finalizado_en: Optional[datetime]
    scraping_error: Optional[str]


# ---------------------------------------------------------------------------
# inventario_relevamiento_serie  (1 fila por número de serie)
# ---------------------------------------------------------------------------


class InventarioRelevamientoSerieBase(SQLModel):
    relevamiento_id: int = Field(foreign_key="inventario_relevamiento.id", index=True)

    # Datos de Omnimedica
    codigo: str = Field(max_length=50, index=True)
    descripcion: Optional[str] = Field(default=None, max_length=200)
    empresa: Optional[str] = Field(default=None, max_length=100)
    serie: str = Field(max_length=100, index=True)
    lote: Optional[str] = Field(default=None, max_length=100)
    vencimiento: Optional[str] = Field(default=None, max_length=20)
    deposito: Optional[str] = Field(default=None, max_length=100)
    estado_sistema: EstadoSerie = Field(
        sa_column=Column(String, nullable=False, default="alta"),
    )
    en_transito: bool = Field(default=False)

    # Datos de Finnegans (por código de referencia)
    cant_finnegans: Optional[Decimal] = Field(default=None, decimal_places=2)

    # Resultado del conteo físico (cargado manualmente por el usuario)
    resultado_fisico: Optional[ResultadoFisico] = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    observaciones: Optional[str] = Field(default=None, max_length=500)
    cargado_en: Optional[datetime] = Field(default=None)
    cargado_por_user_id: Optional[int] = Field(default=None, foreign_key="user.id")


class InventarioRelevamientoSerie(InventarioRelevamientoSerieBase, table=True):
    __tablename__ = "inventario_relevamiento_serie"

    id: Optional[int] = Field(default=None, primary_key=True)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    relevamiento: Optional["InventarioRelevamiento"] = Relationship(
        back_populates="series"
    )


class InventarioRelevamientoSerieRead(InventarioRelevamientoSerieBase):
    id: int
    creado_en: datetime


# ---------------------------------------------------------------------------
# inventario_relevamiento_diferencia  (análisis post-conteo)
# ---------------------------------------------------------------------------


class InventarioRelevamientoDiferenciaBase(SQLModel):
    relevamiento_id: int = Field(foreign_key="inventario_relevamiento.id", index=True)
    serie_id: Optional[int] = Field(default=None, foreign_key="inventario_relevamiento_serie.id")

    tipo: TipoDiferencia = Field(
        sa_column=Column(String, nullable=False),
    )
    descripcion: str = Field(max_length=500)

    # Snapshot de cantidades al momento del análisis
    cant_omnimedica: Optional[Decimal] = Field(default=None, decimal_places=2)
    cant_finnegans: Optional[Decimal] = Field(default=None, decimal_places=2)
    diferencia: Optional[Decimal] = Field(default=None, decimal_places=2)


class InventarioRelevamientoDiferencia(InventarioRelevamientoDiferenciaBase, table=True):
    __tablename__ = "inventario_relevamiento_diferencia"

    id: Optional[int] = Field(default=None, primary_key=True)
    generado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    relevamiento: Optional["InventarioRelevamiento"] = Relationship(
        back_populates="diferencias"
    )


class InventarioRelevamientoDiferenciaRead(InventarioRelevamientoDiferenciaBase):
    id: int
    generado_en: datetime


# ---------------------------------------------------------------------------
# inventario_relevamiento_ajuste  (ajustes autorizados en Finnegans)
# ---------------------------------------------------------------------------


class InventarioRelevamientoAjusteBase(SQLModel):
    relevamiento_id: int = Field(foreign_key="inventario_relevamiento.id", index=True)
    diferencia_id: int = Field(foreign_key="inventario_relevamiento_diferencia.id")

    codigo: str = Field(max_length=50)
    descripcion_ajuste: str = Field(max_length=500)
    cant_ajuste: Decimal = Field(decimal_places=2)


class InventarioRelevamientoAjuste(InventarioRelevamientoAjusteBase, table=True):
    __tablename__ = "inventario_relevamiento_ajuste"

    id: Optional[int] = Field(default=None, primary_key=True)

    estado: EstadoAjuste = Field(
        default=EstadoAjuste.PENDIENTE,
        sa_column=Column(String, nullable=False, default="pendiente"),
    )

    # Auditoría
    autorizado_por_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    autorizado_en: Optional[datetime] = Field(default=None)
    aplicado_en: Optional[datetime] = Field(default=None)
    nota: Optional[str] = Field(default=None, max_length=500)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    relevamiento: Optional["InventarioRelevamiento"] = Relationship(
        back_populates="ajustes"
    )


class InventarioRelevamientoAjusteRead(InventarioRelevamientoAjusteBase):
    id: int
    estado: EstadoAjuste
    autorizado_por_user_id: Optional[int]
    autorizado_en: Optional[datetime]
    aplicado_en: Optional[datetime]
    nota: Optional[str]
    creado_en: datetime