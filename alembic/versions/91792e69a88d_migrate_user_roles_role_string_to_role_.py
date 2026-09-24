"""migrate user_roles role string to role_id fk

Revision ID: 91792e69a88d
Revises: bbf10ee24857
Create Date: 2026-09-21 23:51:39.371525

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91792e69a88d'
down_revision: Union[str, Sequence[str], None] = 'bbf10ee24857'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mapeo rol legacy (string) -> role_id nuevo
ROLE_STRING_TO_ID = {
    'admin': 5,             # Administrador
    'manager': 3,            # Gerente
    'inventory_manager': 2,  # Jefe
    'user': 1,                # Analista
}


def upgrade() -> None:
    conn = op.get_bind()
    for role_string, role_id in ROLE_STRING_TO_ID.items():
        conn.execute(
            sa.text("UPDATE user_roles SET role_id = :role_id WHERE role = :role_string"),
            {"role_id": role_id, "role_string": role_string},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE user_roles SET role_id = NULL"))