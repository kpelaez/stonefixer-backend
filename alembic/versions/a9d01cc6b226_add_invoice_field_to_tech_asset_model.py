"""Add invoice field to tech_asset model

Revision ID: a9d01cc6b226
Revises: 
Create Date: 2025-08-31

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a9d01cc6b226'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Solo agregar la columna invoice, sin tocar otras tablas
    op.add_column('tech_asset', sa.Column('invoice', sa.String(length=255), nullable=True))

def downgrade() -> None:
    # Eliminar la columna invoice
    op.drop_column('tech_asset', 'invoice')