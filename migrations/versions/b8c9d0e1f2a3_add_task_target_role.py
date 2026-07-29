"""add tasks.target_role (بند إضافي 68 — فلترة المهام حسب الدور)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-28 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('target_role', sa.String(length=32), nullable=True))


def downgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_column('target_role')
