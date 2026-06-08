"""finnegans_config: tabla de credenciales y token OAuth2

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-07

INSTRUCCIONES:
  1. Verificar que down_revision = "a1b2c3d4e5f6" (la migración de inventario_stock)
  2. Ejecutar: alembic upgrade head
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finnegans_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=200), nullable=False),
        sa.Column("client_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finnegans_user", sa.String(length=200), nullable=True),
        sa.Column("domain", sa.String(length=200), nullable=True),
        sa.Column("server", sa.String(length=500), nullable=True),
        sa.Column("configurado_por_user_id", sa.Integer(), nullable=False),
        sa.Column("configurado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["configurado_por_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_finnegans_config_activa",
        "finnegans_config",
        ["activa"],
    )


def downgrade() -> None:
    op.drop_index("ix_finnegans_config_activa", table_name="finnegans_config")
    op.drop_table("finnegans_config")