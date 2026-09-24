"""seed rbac permissions and role_permissions matrix

Revision ID: 5627ccdcd258
Revises: 7431f92aa4b9
Create Date: 2026-09-12 23:52:49.569635

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision: str = '5627ccdcd258'
down_revision: Union[str, Sequence[str], None] = '7431f92aa4b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

permissions_table = table('permissions',
    column('id', sa.Integer),
    column('module_id', sa.Integer),
    column('action', sa.String),
)

role_permissions_table = table('role_permissions',
    column('role_id', sa.Integer),
    column('permission_id', sa.Integer),
)

# module_id según seed anterior: 1=inventario 2=turnos 3=horas_extra
# 4=dashboards 5=usuarios 6=informes_stock 7=informes_rrhh
PERMISSIONS_SEED = [
    {'id': 1,  'module_id': 1, 'action': 'view'},
    {'id': 2,  'module_id': 1, 'action': 'create'},
    {'id': 3,  'module_id': 1, 'action': 'edit'},
    {'id': 4,  'module_id': 1, 'action': 'delete'},
    {'id': 5,  'module_id': 2, 'action': 'view'},
    {'id': 6,  'module_id': 2, 'action': 'create'},
    {'id': 7,  'module_id': 2, 'action': 'edit'},
    {'id': 8,  'module_id': 2, 'action': 'delete'},
    {'id': 9,  'module_id': 3, 'action': 'view'},
    {'id': 10, 'module_id': 3, 'action': 'create'},
    {'id': 11, 'module_id': 3, 'action': 'approve'},
    {'id': 12, 'module_id': 4, 'action': 'view'},
    {'id': 13, 'module_id': 5, 'action': 'view'},
    {'id': 14, 'module_id': 5, 'action': 'create'},
    {'id': 15, 'module_id': 5, 'action': 'edit'},
    {'id': 16, 'module_id': 5, 'action': 'delete'},
    {'id': 17, 'module_id': 6, 'action': 'view'},
    {'id': 18, 'module_id': 6, 'action': 'create'},
    {'id': 19, 'module_id': 6, 'action': 'edit'},
    {'id': 20, 'module_id': 6, 'action': 'approve'},
    {'id': 21, 'module_id': 7, 'action': 'view'},
]

# role_id según seed anterior: 1=Analista 2=Jefe 3=Gerente 4=Director 5=Administrador
ROLE_PERMISSIONS_SEED = (
    [{'role_id': 1, 'permission_id': pid} for pid in [1, 5, 9, 10, 17]] +                                  # Analista
    [{'role_id': 2, 'permission_id': pid} for pid in [1, 2, 3, 5, 6, 7, 9, 10, 11, 17, 18, 19]] +          # Jefe
    [{'role_id': 3, 'permission_id': pid} for pid in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 17, 18, 19, 20]] +  # Gerente
    [{'role_id': 4, 'permission_id': pid} for pid in [1, 5, 9, 12, 17, 21]] +                               # Director
    [{'role_id': 5, 'permission_id': pid} for pid in range(1, 22)]                                          # Administrador: todo
)


def upgrade() -> None:
    op.bulk_insert(permissions_table, PERMISSIONS_SEED)
    op.bulk_insert(role_permissions_table, ROLE_PERMISSIONS_SEED)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM role_permissions"))
    conn.execute(sa.text("DELETE FROM permissions"))
