from sqlmodel import Session, text
from typing import Optional
from app.models.venta_mes import VentaMesKpis
import logging

logger = logging.getLogger(__name__)

def get_venta_mes_kpis(
    db: Session,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
) -> VentaMesKpis:
    query = text("""
        SELECT
            COALESCE(SUM(importe), 0) AS ordenes_compra,
            COUNT(*) AS cantidad_ots,
            MAX(data_asof)::text AS data_asof
        FROM prod.kpi_panel_ejecutivo
        WHERE (:fecha_desde IS NULL OR fecha_generacion >= :fecha_desde)
          AND (:fecha_hasta IS NULL OR fecha_generacion <= :fecha_hasta)
    """)
    result = db.exec(query, params={"fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta})
    row = result.first()

    return VentaMesKpis(
        venta_total=float(row.venta_total) if row else 0.0,
        cantidad_ots=int(row.cantidad_ots) if row else 0,
        data_asof=row.data_asof if row else None,
    )