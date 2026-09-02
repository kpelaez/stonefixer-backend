"""
app/models/contribucion_marginal.py

Modelo de solo lectura para prod.cont_marg_gen (lakehouse).
Contiene datos de facturación ligados a pacientes/médicos — ver
consideración de acceso en el service antes de exponer el detalle nominal.
"""
from sqlmodel import SQLModel, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


class ContribucionMarginal(SQLModel, table=True):
    __tablename__ = "cont_marg_gen"
    __table_args__ = {"schema": "prod"}

    id: int = Field(primary_key=True)

    # Facturación
    fecha_factura: Optional[date] = None
    nro_factura: Optional[str] = None
    cliente: Optional[str] = None
    total_bruto_factura: Optional[Decimal] = None
    concepto_impositivo: Optional[Decimal] = None
    total_factura: Optional[Decimal] = None
    gastos_logisticos: Optional[Decimal] = None
    porcentaje_gastos_log: Optional[Decimal] = None

    # OT / Remito / Consumo
    fecha_ot: Optional[date] = None
    nro_ot: Optional[str] = None
    fecha_remito: Optional[date] = None
    nro_remito: Optional[str] = None
    fecha_consumo: Optional[date] = None
    nro_consumo: Optional[int] = None
    precio: Optional[Decimal] = None
    descripcion_ppp: Optional[str] = None
    estado_valorizacion: Optional[str] = None

    # Datos identificables — restringir en el service según rol
    paciente: Optional[str] = None
    institucion: Optional[str] = None
    tecnico: Optional[str] = None
    medico: Optional[str] = None
    medico_proctor: Optional[str] = None
    sucursal: Optional[str] = None

    # Nota de crédito
    fecha_nc: Optional[date] = None
    nro_nc: Optional[str] = None
    total_bruto_nc: Optional[Decimal] = None

    # KPIs calculados
    contribucion_marginal: Optional[Decimal] = None
    porcentaje_margen: Optional[Decimal] = None

    # Freshness — usar esta columna para mostrar "datos actualizados al
    # DD/MM HH:MM" en el frontend, en vez de solo confiar en el TTL del cache
    fecha_carga: datetime

    # Claves hacia las tablas normalizadas (usar estas para joins, no los
    # nro_* de texto de arriba — más rápido y sin riesgo de formato)
    transaccion_id_ot: Optional[int] = None
    transaccion_id_factura: Optional[int] = None
    transaccion_id_despacho: Optional[int] = None
    transaccion_id_consumo: Optional[int] = None
    transaccion_id_nc: Optional[int] = None