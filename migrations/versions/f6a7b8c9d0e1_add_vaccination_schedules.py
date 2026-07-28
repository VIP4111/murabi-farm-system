"""add vaccination_schedules table (تقويم التحصينات، بند إضافي 63)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-28 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'vaccination_schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('barn_id', sa.Integer(), sa.ForeignKey('barns.id'), nullable=False),
        sa.Column('pharmacy_id', sa.Integer(), sa.ForeignKey('pharmacy.id'), nullable=False),
        sa.Column('planned_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='scheduled'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('vaccination_schedules')
