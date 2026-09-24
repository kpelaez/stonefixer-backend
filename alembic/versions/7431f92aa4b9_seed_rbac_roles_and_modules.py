"""seed rbac roles and modules

Revision ID: 7431f92aa4b9
Revises: 4b61180face2
Create Date: 2026-09-12 23:40:33.967906

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision: str = '7431f92aa4b9'
down_revision: Union[str, Sequence[str], None] = '4b61180face2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


roles_table = table('roles',
    column('id', sa.Integer),
    column('name', sa.String),
    column('hierarchy_level', sa.Integer),
    column('description', sa.String),
)

modules_table = table('modules',
    column('id', sa.Integer),
    column('code', sa.String),
    column('name', sa.String),
)

ROLES_SEED = [
    {'id': 1, 'name': 'Analista', 'hierarchy_level': 1, 'description': 'Rol operativo de base'},
    {'id': 2, 'name': 'Jefe', 'hierarchy_level': 2, 'description': 'Supervisión de equipo o área'},
    {'id': 3, 'name': 'Gerente', 'hierarchy_level': 3, 'description': 'Gestión de sector'},
    {'id': 4, 'name': 'Director', 'hierarchy_level': 4, 'description': 'Visión estratégica, acceso a dashboards'},
    {'id': 5, 'name': 'Administrador', 'hierarchy_level': 5, 'description': 'Acceso total al sistema'},
]

MODULES_SEED = [
    {'id': 1, 'code': 'inventario', 'name': 'Inventario y Mantenimiento'},
    {'id': 2, 'code': 'turnos', 'name': 'Turnos'},
    {'id': 3, 'code': 'horas_extra', 'name': 'Horas Extra'},
    {'id': 4, 'code': 'dashboards', 'name': 'Dashboards'},
    {'id': 5, 'code': 'usuarios', 'name': 'Usuarios'},
    {'id': 6, 'code': 'informes_stock', 'name': 'Informes de Stock'},
    {'id': 7, 'code': 'informes_rrhh', 'name': 'Informes de RRHH'},
]


def upgrade() -> None:
    op.bulk_insert(roles_table, ROLES_SEED)
    op.bulk_insert(modules_table, MODULES_SEED)


def downgrade() -> None:
    conn = op.get_bind()
    role_ids = tuple(r['id'] for r in ROLES_SEED)
    module_ids = tuple(m['id'] for m in MODULES_SEED)
    conn.execute(sa.text("DELETE FROM roles WHERE id IN :ids").bindparams(sa.bindparam('ids', expanding=True)), {'ids': role_ids})
    conn.execute(sa.text("DELETE FROM modules WHERE id IN :ids").bindparams(sa.bindparam('ids', expanding=True)), {'ids': module_ids})
