"""add species/breed/color reference tables + pregnancy intake flag

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'species_types',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('label_ar', sa.String(length=80), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('code'),
    )
    op.create_table(
        'breeds',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'animal_colors',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('name'),
    )


def downgrade():
    op.drop_table('animal_colors')
    op.drop_table('breeds')
    op.drop_table('species_types')
