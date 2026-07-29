"""add tasks.sort_order (بند إضافي 67 — ترتيب عرض ثانوي حاسم)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-28 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_column('sort_order')
