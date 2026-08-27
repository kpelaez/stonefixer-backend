"""add humand integration fields to asset_assignments

Revision ID: a416e32ffcd4
Revises: 902c807c3f2f
Create Date: 2026-08-23 18:56:52.300539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'a416e32ffcd4'
down_revision: Union[str, Sequence[str], None] = '902c807c3f2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('asset_assignments', sa.Column('humand_send_status', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('asset_assignments', sa.Column('humand_error_detail', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('asset_assignments', sa.Column('humand_last_attempt_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('asset_assignments', 'humand_last_attempt_at')
    op.drop_column('asset_assignments', 'humand_error_detail')
    op.drop_column('asset_assignments', 'humand_send_status')