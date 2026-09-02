"""
app/models/consumo.py

Modelos de solo lectura para prod.cabecera_consumo y prod.consumo_detalle
(lakehouse). Alimentan la sección "Desglose de Productos Consumidos"
del OTDetalleModal.

Join: cabecera_consumo.transaccion_id_consumo == consumo_detalle.transaccion_id_consumo
      == cont_marg_gen.nro_consumo
"""
from sqlmodel import SQLModel, Field
from datetime import date
from decimal import Decimal
from typing import Optional


class CabeceraConsumo(SQLModel, table=True):
    __tablename__ = "cabecera_consumo"
    __table_args__ = {"schema": "prod"}

    transaccion_id_consumo: int = Field(primary_key=True)
    transaccion_subtipo_id: Optional[int] = None
    fecha_consumo: Optional[date] = None
    tipo_documento: Optional[str] = None
    numero_consumo: Optional[str] = None
    nro_remito: Optional[str] = None
    cliente_remito: Optional[str] = None
    importe_total: Optional[Decimal] = None


class ConsumoDetalle(SQLModel, table=True):
    __tablename__ = "consumo_detalle"
    __table_args__ = {"schema": "prod"}

    id_cons_prod: int = Field(primary_key=True)
    transaccion_id_consumo: int = Field(foreign_key="prod.cabecera_consumo.transaccion_id_consumo")
    producto: str
    precio: Decimal
    cantidad: Decimal
    unidad: str
    importe: Decimal