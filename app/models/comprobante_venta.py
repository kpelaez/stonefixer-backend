"""
app/models/comprobante_venta.py

Modelos de solo lectura para prod.comprobante_venta_cabecera y
prod.comprobante_venta_detalle. Alimentan la sección
"Producto(s) Vendido(s)" del OTDetalleModal.

Join: comprobante_venta_cabecera.transaccion_id
      == comprobante_venta_detalle.transaccion_id
      == cont_marg_gen.transaccion_id_factura
"""
from sqlmodel import SQLModel, Field
from datetime import date
from decimal import Decimal
from typing import Optional


class ComprobanteVentaCabecera(SQLModel, table=True):
    __tablename__ = "comprobante_venta_cabecera"
    __table_args__ = {"schema": "prod"}

    transaccion_id: int = Field(primary_key=True)
    transaccion_subtipo_id: int
    subtipo_nombre: Optional[str] = None
    fecha: Optional[date] = None
    fecha_comprobante: date
    comprobante: str
    cliente: Optional[str] = None
    condicion_pago: Optional[str] = None
    vendedor: Optional[str] = None
    moneda: Optional[str] = None
    cotizacion: Optional[Decimal] = None
    sucursal: Optional[str] = None
    total_bruto: Optional[Decimal] = None
    total_conceptos: Optional[Decimal] = None
    percepciones: Optional[Decimal] = None
    total: Optional[Decimal] = None


class ComprobanteVentaDetalle(SQLModel, table=True):
    __tablename__ = "comprobante_venta_detalle"
    __table_args__ = {"schema": "prod"}

    comprobante_venta_detalle_id: int = Field(primary_key=True)
    transaccion_id: int = Field(foreign_key="prod.comprobante_venta_cabecera.transaccion_id")
    transaccion_item_id: int
    codigo_producto: Optional[str] = None
    producto: Optional[str] = None
    cantidad: Optional[Decimal] = None
    unidad_venta: Optional[str] = None
    precio: Optional[Decimal] = None
    gravado_por_tasa_impositiva: Optional[Decimal] = None
    importe: Optional[Decimal] = None
    porcentaje_impositivo: Optional[Decimal] = None
    familia: Optional[str] = None
    subfamilia: Optional[str] = None