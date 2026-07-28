"""add drug_catalog_entries table, seeded from existing distinct pharmacy names

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-28 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'drug_catalog_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('medicine_class', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('name'),
    )

    # تعبئة أولية (بند إضافي 62) — كل اسم دواء مسجَّل فعلاً بالصيدلية
    # (حتى لو كرّر نفسه بأكثر من دفعة/صف) يدخل الكتالوج تلقائياً مرة
    # وحدة، عشان الأدوية الموجودة أصلاً تظهر كاقتراحات فوراً بدون ما
    # يحتاج الطبيب يعيد كتابتها يدوياً من الصفر.
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT DISTINCT name, medicine_class FROM pharmacy WHERE name IS NOT NULL"
    )).fetchall()
    seen = set()
    for name, medicine_class in rows:
        if name in seen:
            continue
        seen.add(name)
        conn.execute(
            sa.text("INSERT INTO drug_catalog_entries (name, medicine_class) VALUES (:name, :medicine_class)"),
            {"name": name, "medicine_class": medicine_class},
        )


def downgrade():
    op.drop_table('drug_catalog_entries')
