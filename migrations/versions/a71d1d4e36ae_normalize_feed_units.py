"""normalize feed units to fixed list (بند إضافي 202)

Revision ID: a71d1d4e36ae
Revises: 96d1ccfef967
Create Date: 2026-08-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a71d1d4e36ae'
down_revision = '96d1ccfef967'
branch_labels = None
depends_on = None


# تطبيع بيانات فقط (بند إضافي 202) — ما فيه تغيير هيكلي على العمود
# نفسه (يبقى String(32))، بس القيم الحرة القديمة ("كيلو"، "كيلوجرام"،
# فاضي...) تتحوّل للقيمة الثابتة الصحيحة — عشان أي صنف مُدخَل قبل هذا
# البند يتوافق فوراً مع منطق تجميع "الأصناف البديلة" بتقرير طلب الشراء
# (بند 156) اللي يقارن الوحدة حرفياً.
VARIANTS_TO_CANONICAL = {
    "كيلو": "كجم", "كيلوجرام": "كجم", "كيلو جرام": "كجم", "كغم": "كجم",
    "kg": "كجم", "Kg": "كجم", "KG": "كجم",
    "طن": "طن", "Ton": "طن", "ton": "طن",
    "لتر": "لتر", "Liter": "لتر", "liter": "لتر", "لترات": "لتر",
    "مل": "مل", "مليلتر": "مل", "ml": "مل", "ML": "مل",
    "كيس": "كيس", "اكياس": "كيس", "أكياس": "كيس", "كياس": "كيس",
}


def upgrade():
    conn = op.get_bind()
    feeds = sa.table("feeds", sa.column("id", sa.Integer), sa.column("unit", sa.String))
    rows = conn.execute(sa.text("SELECT id, unit FROM feeds")).fetchall()
    for row_id, unit in rows:
        canonical = VARIANTS_TO_CANONICAL.get((unit or "").strip(), None)
        if canonical is None:
            canonical = "كجم" if not unit or unit.strip() not in ("كجم", "طن", "لتر", "مل", "كيس") else unit.strip()
        if canonical != unit:
            conn.execute(feeds.update().where(feeds.c.id == row_id).values(unit=canonical))


def downgrade():
    # لا يوجد رجوع منطقي — القيم الأصلية الحرة غير محفوظة بمكان ثانٍ.
    pass
