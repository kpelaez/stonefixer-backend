"""
app/models/cobranza.py

Modelos de solo lectura para prod.cabecera_cobranzas y
prod.cobranza_detalle. Alimentan el KPI "Cobrado" del Panel Ejecutivo.
"""
from sqlmodel import SQLModel, Field
from datetime import date
from decimal import Decimal
from typing import Optional


class CabeceraCobranza(SQLModel, table=True):
    __tablename__ = "cabecera_cobranzas"
    __table_args__ = {"schema": "prod"}

    transaccion_id_cobranza: int = Field(primary_key=True)
    tipo_movimiento: str
    fecha_cobranza: date
    documento_cobranza: str
    comprobante: str
    tercero: Optional[str] = None
    cuit_tercero: Optional[str] = None
    empresa: Optional[str] = None
    estado: Optional[str] = None
    moneda: Optional[str] = None
    cotizacion: Optional[Decimal] = None
    descripcion: Optional[str] = None
    importe_total: Decimal
    importe_moneda_transaccion_total: Decimal
    importe_moneda_secundaria_total: Optional[Decimal] = None
    cantidad_detalles: int


class CobranzaDetalle(SQLModel, table=True):
    __tablename__ = "cobranza_detalle"
    __table_args__ = {"schema": "prod"}

    cobranza_detalle_id: int = Field(primary_key=True)
    transaccion_id_cobranza: int = Field(foreign_key="prod.cabecera_cobranzas.transaccion_id_cobranza")
    cuenta: str
    importe: Decimal
    importe_moneda_transaccion: Decimal
    importe_moneda_secundaria: Optional[Decimal] = None
    operacion_bancaria: Optional[str] = None
    numero_cuenta: Optional[str] = None
    cheque: Optional[str] = None
    fecha_emision_cheque: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    banco: Optional[str] = None
    cuit_librador: Optional[str] = None
    organizacion_documento_fisico: Optional[str] = None