# app/schemas/inventario_stock.py
"""
Schemas de request/response para el módulo Inventario de Stock.

Separados del modelo SQLModel para respetar SRP: los modelos pertenecen
a la capa de persistencia, los schemas a la capa de transporte.

Nota: los Read-schemas viven en models/inventario_stock.py (patrón del proyecto).
Aquí van Create, Update y schemas de response compuestos.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.inventario_stock import (
    EstadoAjuste,
    EstadoRelevamiento,
    InventarioRelevamientoAjusteRead,
    InventarioRelevamientoDiferenciaRead,
    InventarioRelevamientoRead,
    InventarioRelevamientoSerieRead,
    ResultadoFisico,
    TipoDiferencia,
)


# ---------------------------------------------------------------------------
# Relevamiento — Create / Update
# ---------------------------------------------------------------------------


class RelevamientoCreate(BaseModel):
    """Payload para iniciar un ciclo de relevamiento."""

    proveedor: str = Field(min_length=1, max_length=100)
    mes_ciclo: str = Field(
        description="Formato YYYY-MM",
        pattern=r"^\d{4}-\d{2}$",
    )

    @field_validator("proveedor")
    @classmethod
    def proveedor_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El proveedor no puede estar vacío")
        return v.strip()


# ---------------------------------------------------------------------------
# Estado del scraping (polling)
# ---------------------------------------------------------------------------


class ScrapingStatusResponse(BaseModel):
    """Respuesta del endpoint de polling para el background task."""

    relevamiento_id: int
    estado: EstadoRelevamiento
    total_series_omni: Optional[int] = None
    total_codigos_finn: Optional[int] = None
    scraping_iniciado_en: Optional[datetime] = None
    scraping_finalizado_en: Optional[datetime] = None
    scraping_error: Optional[str] = None
    porcentaje_completado: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Estimación de progreso del scraping (0-100)",
    )


# ---------------------------------------------------------------------------
# Series — filtros y paginación
# ---------------------------------------------------------------------------


class SeriesListParams(BaseModel):
    """Query params para listar series de un relevamiento."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)
    solo_pendientes: bool = Field(
        default=False,
        description="Si True, filtra solo series sin resultado físico cargado",
    )
    solo_diferencias: bool = Field(
        default=False,
        description="Si True, filtra solo series con diferencias detectadas",
    )


class SeriesListResponse(BaseModel):
    """Respuesta paginada de series."""

    total: int
    page: int
    page_size: int
    items: List[InventarioRelevamientoSerieRead]


# ---------------------------------------------------------------------------
# Carga de resultado físico
# ---------------------------------------------------------------------------


class ResultadoFisicoItem(BaseModel):
    """Un ítem del conteo físico para una serie específica."""

    serie_id: int
    resultado: ResultadoFisico
    observaciones: Optional[str] = Field(default=None, max_length=500)


class CargaResultadosFisicosRequest(BaseModel):
    """Carga masiva de resultados del conteo físico."""

    items: List[ResultadoFisicoItem] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def no_series_duplicadas(
        cls, items: List[ResultadoFisicoItem]
    ) -> List[ResultadoFisicoItem]:
        ids = [i.serie_id for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError("No puede haber series duplicadas en la misma carga")
        return items


class CargaResultadosResponse(BaseModel):
    actualizadas: int
    no_encontradas: List[int] = Field(
        default_factory=list,
        description="IDs de series no encontradas en la BD",
    )


# ---------------------------------------------------------------------------
# Análisis de diferencias
# ---------------------------------------------------------------------------


class AnalisisSummary(BaseModel):
    """Resumen del análisis post-conteo."""

    relevamiento_id: int
    total_diferencias: int
    por_tipo: dict[TipoDiferencia, int]
    diferencias: List[InventarioRelevamientoDiferenciaRead]


# ---------------------------------------------------------------------------
# Ajustes
# ---------------------------------------------------------------------------


class AjusteCreate(BaseModel):
    diferencia_id: int
    codigo: str = Field(min_length=1, max_length=50)
    descripcion_ajuste: str = Field(min_length=1, max_length=500)
    cant_ajuste: Decimal = Field(description="Positivo para ingreso, negativo para egreso")


class AjusteAutorizarRequest(BaseModel):
    nota: Optional[str] = Field(default=None, max_length=500)


class AjusteResponse(InventarioRelevamientoAjusteRead):
    """Extiende el read-schema con el nombre del autorizador."""

    autorizado_por_nombre: Optional[str] = None


# ---------------------------------------------------------------------------
# Response completo del relevamiento (con conteo de items)
# ---------------------------------------------------------------------------


class RelevamientoDetailResponse(InventarioRelevamientoRead):
    """Cabecera del relevamiento con totales calculados."""

    total_diferencias: int = 0
    total_ajustes_pendientes: int = 0
    total_ajustes_autorizados: int = 0
    creado_por_nombre: Optional[str] = None