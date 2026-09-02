from sqlmodel import Session, text
from typing import Optional
from app.models.venta_mes import VentaMesKpis
import logging

logger = logging.getLogger(__name__)

def get_venta_mes_kpis(
    db: Session,
    anio: int,
    mes: Optional[int] = None,
) -> VentaMesKpis:
    query = text("""
        SELECT
            COALESCE(SUM(Ordenes_compra), 0) AS ordenes_compra
        FROM prod.kpi_panel_ejecutivo
        WHERE anio = :anio
          AND (:mes IS NULL OR mes = :mes)
    """)
    result = db.exec(query, params={"anio": anio, "mes": mes})
    row = result.first()

    return VentaMesKpis(
        ordenes_compra=float(row.ordenes_compra) if row and row.ordenes_compra is not None else 0.0,
    )