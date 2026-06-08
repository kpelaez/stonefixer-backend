"""inventario_stock: tablas de relevamiento, series, diferencias y ajustes

Revision ID: a1b2c3d4e5f6
Revises: <poner aquí el revision ID de la última migración existente>
Create Date: 2025-06-06

INSTRUCCIONES:
  1. Ajustar `down_revision` con el ID real de la última migración.
  2. Ejecutar: alembic upgrade head
"""

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
revision = "a1b2c3d4e5f6"
down_revision = "7e3674ff80d3"
branch_labels = None
depends_on = None
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # ------------------------------------------------------------------
    # inventario_relevamiento
    # ------------------------------------------------------------------
    op.create_table(
        "inventario_relevamiento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proveedor", sa.String(length=100), nullable=False),
        sa.Column("mes_ciclo", sa.String(length=7), nullable=False),
        sa.Column("estado", sa.String(), nullable=False, server_default="pendiente"),
        sa.Column("creado_por_user_id", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_series_omni", sa.Integer(), nullable=True),
        sa.Column("total_codigos_finn", sa.Integer(), nullable=True),
        sa.Column("scraping_iniciado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scraping_finalizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scraping_error", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["creado_por_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inventario_relevamiento_proveedor",
        "inventario_relevamiento",
        ["proveedor"],
    )
    op.create_index(
        "ix_inventario_relevamiento_mes_ciclo",
        "inventario_relevamiento",
        ["mes_ciclo"],
    )

    # ------------------------------------------------------------------
    # inventario_relevamiento_serie
    # ------------------------------------------------------------------
    op.create_table(
        "inventario_relevamiento_serie",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("relevamiento_id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=50), nullable=False),
        sa.Column("descripcion", sa.String(length=200), nullable=True),
        sa.Column("empresa", sa.String(length=100), nullable=True),
        sa.Column("serie", sa.String(length=100), nullable=False),
        sa.Column("lote", sa.String(length=100), nullable=True),
        sa.Column("vencimiento", sa.String(length=20), nullable=True),
        sa.Column("deposito", sa.String(length=100), nullable=True),
        sa.Column("estado_sistema", sa.String(), nullable=False, server_default="alta"),
        sa.Column("en_transito", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("cant_finnegans", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("resultado_fisico", sa.String(), nullable=True),
        sa.Column("observaciones", sa.String(length=500), nullable=True),
        sa.Column("cargado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cargado_por_user_id", sa.Integer(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["relevamiento_id"], ["inventario_relevamiento.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["cargado_por_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inv_serie_relevamiento_id",
        "inventario_relevamiento_serie",
        ["relevamiento_id"],
    )
    op.create_index(
        "ix_inv_serie_codigo",
        "inventario_relevamiento_serie",
        ["codigo"],
    )
    op.create_index(
        "ix_inv_serie_serie",
        "inventario_relevamiento_serie",
        ["serie"],
    )

    # ------------------------------------------------------------------
    # inventario_relevamiento_diferencia
    # ------------------------------------------------------------------
    op.create_table(
        "inventario_relevamiento_diferencia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("relevamiento_id", sa.Integer(), nullable=False),
        sa.Column("serie_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("descripcion", sa.String(length=500), nullable=False),
        sa.Column("cant_omnimedica", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("cant_finnegans", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("diferencia", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("generado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["relevamiento_id"], ["inventario_relevamiento.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["serie_id"], ["inventario_relevamiento_serie.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inv_dif_relevamiento_id",
        "inventario_relevamiento_diferencia",
        ["relevamiento_id"],
    )

    # ------------------------------------------------------------------
    # inventario_relevamiento_ajuste
    # ------------------------------------------------------------------
    op.create_table(
        "inventario_relevamiento_ajuste",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("relevamiento_id", sa.Integer(), nullable=False),
        sa.Column("diferencia_id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=50), nullable=False),
        sa.Column("descripcion_ajuste", sa.String(length=500), nullable=False),
        sa.Column("cant_ajuste", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("estado", sa.String(), nullable=False, server_default="pendiente"),
        sa.Column("autorizado_por_user_id", sa.Integer(), nullable=True),
        sa.Column("autorizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aplicado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nota", sa.String(length=500), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["relevamiento_id"], ["inventario_relevamiento.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["diferencia_id"], ["inventario_relevamiento_diferencia.id"]
        ),
        sa.ForeignKeyConstraint(["autorizado_por_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inv_ajuste_relevamiento_id",
        "inventario_relevamiento_ajuste",
        ["relevamiento_id"],
    )


def downgrade() -> None:
    op.drop_table("inventario_relevamiento_ajuste")
    op.drop_table("inventario_relevamiento_diferencia")
    op.drop_table("inventario_relevamiento_serie")
    op.drop_table("inventario_relevamiento")