"""
كتالوج أسماء الأدوية (بند إضافي 62، 2026-07-28) — قائمة اقتراحات أسماء
تُصفَّى بفورم الدواء حسب "فئة الدواء" المختارة، بزر "+" (`medical_options.manage`)
لإضافة اسم غير موجود — نفس نمط `UsageRoute`/`Breed`/`AnimalColor` بالضبط.
منفصل تماماً عن صفوف `Pharmacy` نفسها (اللي تمثّل دفعات مخزون فعلية) —
هذا مجرد مرجع أسماء معروفة يسرّع تكرار إدخال نفس الدواء لاحقاً.
"""
from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class DrugCatalogEntry(db.Model):
    __tablename__ = "drug_catalog_entries"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    medicine_class = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)
