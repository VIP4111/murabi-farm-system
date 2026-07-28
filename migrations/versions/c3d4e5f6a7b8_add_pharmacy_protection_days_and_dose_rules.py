"""add pharmacy protection_days and pharmacy_dose_rules table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-28 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('pharmacy', schema=None) as batch_op:
        batch_op.add_column(sa.Column('protection_days', sa.Integer(), nullable=True))

    op.create_table(
        'pharmacy_dose_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('pharmacy_id', sa.Integer(), sa.ForeignKey('pharmacy.id'), nullable=False),
        sa.Column('age_from_days', sa.Integer(), nullable=False),
        sa.Column('age_to_days', sa.Integer(), nullable=False),
        sa.Column('dose_ml', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('pharmacy_dose_rules')
    with op.batch_alter_table('pharmacy', schema=None) as batch_op:
        batch_op.drop_column('protection_days')
