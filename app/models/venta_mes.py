from sqlmodel import SQLModel
from typing import Optional

class VentaMesKpis(SQLModel):
    venta_total: float
    cantidad_ots: int
    data_asof: Optional[str] = None