"""
Add soft delete fields to tech_asset

Revision ID: add_soft_delete_tech_asset
Revises: 4e5d5a9d1060
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_soft_delete_tech_asset'
down_revision = '4e5d5a9d1060'  # Cambiar por tu última migración
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Agregar campos para soft-delete en la tabla tech_asset.
    
    Campos agregados:
    - deleted_at: Timestamp de cuándo se eliminó (NULL si no está eliminado)
    - deleted_by_user_id: ID del usuario que eliminó (para auditoría)
    """
    # Agregar columna deleted_at
    op.add_column(
        'tech_asset',
        sa.Column(
            'deleted_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Fecha de eliminación (soft-delete)'
        )
    )
    
    # Agregar columna deleted_by_user_id
    op.add_column(
        'tech_asset',
        sa.Column(
            'deleted_by_user_id',
            sa.Integer(),
            nullable=True,
            comment='ID del usuario que eliminó el activo'
        )
    )
    
    # Agregar foreign key a user
    op.create_foreign_key(
        'fk_tech_asset_deleted_by_user',
        'tech_asset',
        'user',
        ['deleted_by_user_id'],
        ['id'],
        ondelete='SET NULL'
    )
    
    # Crear índice para deleted_at (para filtrar eficientemente activos no eliminados)
    op.create_index(
        'idx_tech_asset_deleted_at',
        'tech_asset',
        ['deleted_at']
    )
    
    print("Campos de soft-delete agregados a tech_asset")


def downgrade() -> None:
    """
    Revertir los cambios (eliminar campos de soft-delete).
    """
    # Eliminar foreign key
    op.drop_constraint('fk_tech_asset_deleted_by_user', 'tech_asset', type_='foreignkey')
    
    # Eliminar índice
    op.drop_index('idx_tech_asset_deleted_at', table_name='tech_asset')
    
    # Eliminar columnas
    op.drop_column('tech_asset', 'deleted_by_user_id')
    op.drop_column('tech_asset', 'deleted_at')
    
    print("Campos de soft-delete eliminados de tech_asset")