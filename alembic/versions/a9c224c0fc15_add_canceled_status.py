"""add_canceled_status

Revision ID: a9c224c0fc15
Revises: add_soft_delete_tech_asset
Create Date: 2025-12-27 23:06:03.912119

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9c224c0fc15'
down_revision: Union[str, Sequence[str], None] = 'add_soft_delete_tech_asset'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agregar el nuevo valor 'canceled' al enum AssignmentStatus
    op.execute("""
        ALTER TYPE assignmentstatus ADD VALUE IF NOT EXISTS 'canceled'
    """)


def downgrade() -> None:
    """Downgrade schema."""
    pass
