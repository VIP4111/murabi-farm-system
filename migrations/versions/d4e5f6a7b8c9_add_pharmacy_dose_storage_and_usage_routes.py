"""add pharmacy default_dose_ml, storage_condition, and usage_routes table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-28 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('pharmacy', schema=None) as batch_op:
        batch_op.add_column(sa.Column('default_dose_ml', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('storage_condition', sa.String(length=20), nullable=True))

    op.create_table(
        'usage_routes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('name'),
    )


def downgrade():
    op.drop_table('usage_routes')
    with op.batch_alter_table('pharmacy', schema=None) as batch_op:
        batch_op.drop_column('storage_condition')
        batch_op.drop_column('default_dose_ml')
