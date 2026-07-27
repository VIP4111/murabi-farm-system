"""add task worker execution tracking (بند إضافي 54)

Revision ID: a1b2c3d4e5f6
Revises: c00c097d189a
Create Date: 2026-07-27 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'c00c097d189a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('accepted_by_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('duration_minutes', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('server_time_source', sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column('failed_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('failure_reason', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('voice_note_url', sa.String(length=255), nullable=True))
        batch_op.create_foreign_key(
            'fk_tasks_accepted_by_id_users', 'users', ['accepted_by_id'], ['id']
        )


def downgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tasks_accepted_by_id_users', type_='foreignkey')
        batch_op.drop_column('voice_note_url')
        batch_op.drop_column('failure_reason')
        batch_op.drop_column('failed_at')
        batch_op.drop_column('server_time_source')
        batch_op.drop_column('duration_minutes')
        batch_op.drop_column('accepted_by_id')
