"""
app/models/ot.py

Modelos de solo lectura para prod.ot_cabecera y prod.ot_detalle.

ot_cabecera es la fuente AUTORITATIVA de paciente/médico/institución
(Kevin confirmó que cont_marg_gen va a angostarse a futuro y dejar de
tener estas columnas duplicadas — el service debe preferir ot_cabecera
desde ya, con fallback a cont_marg_gen mientras conviven ambas).

Join: ot_cabecera.transaccion_id == ot_detalle.transaccion_id
      == cont_marg_gen.transaccion_id_ot
"""
from sqlmodel import SQLModel, Field
from datetime import date
from decimal import Decimal
from typing import Optional


class OtCabecera(SQLModel, table=True):
    __tablename__ = "ot_cabecera"
    __table_args__ = {"schema": "prod"}

    transaccion_id: int = Field(primary_key=True)
    transaccion_subtipo_id: int
    fecha_comprobante: date
    comprobante: str
    cliente: Optional[str] = None
    condicion_pago: Optional[str] = None
    paciente: Optional[str] = None
    fecha_intervencion: Optional[date] = None
    medico: Optional[str] = None
    medico_proctor: Optional[str] = None
    institucion: Optional[str] = None
    oc_asociada: Optional[str] = None
    expediente: Optional[str] = None
    licitacion: Optional[str] = None
    vendedor: Optional[str] = None
    tecnico_1: Optional[str] = None
    total_bruto: Optional[Decimal] = None
    total_conceptos: Optional[Decimal] = None
    percepciones: Optional[Decimal] = None
    total: Optional[Decimal] = None
    moneda: Optional[str] = None
    cotizacion: Optional[Decimal] = None


class OtDetalle(SQLModel, table=True):
    __tablename__ = "ot_detalle"
    __table_args__ = {"schema": "prod"}

    ot_detalle_id: int = Field(primary_key=True)
    transaccion_id: int = Field(foreign_key="prod.ot_cabecera.transaccion_id")
    codigo_producto: str
    producto: str
    descripcion_item: Optional[str] = None
    cantidad: Decimal
    gravado: Optional[Decimal] = None
    gravado_por_tasa_impositiva: Optional[Decimal] = None
    porcentaje_impositivo: Optional[Decimal] = None