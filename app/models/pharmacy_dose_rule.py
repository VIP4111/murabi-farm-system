"""
جدول "الجرعة حسب العمر" (بند إضافي، 2026-07-28) — يكتبه الدكتور/مدير
الصيدلية بنفسه مرة وحدة لكل دواء (نطاق عمر بالأيام + جرعة بالمل)، ونظام
التحصين الجماعي يبحث فيه لاحقاً عن النطاق المطابق لعمر كل رأس **ويعرضه
بس** — هذا بحث/مطابقة (lookup) بجدول كتبه إنسان، مو حساب أو اشتقاق جرعة
من معادلة عمر/وزن (قاعدة "المساعد قرار مو طبيب" — بند 13 — تبقى محترمة
بالكامل: كل رقم جرعة هنا كتبه الدكتور بنفسه، والنظام ما يخترع ولا رقم).
"""
from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class PharmacyDoseRule(db.Model):
    __tablename__ = "pharmacy_dose_rules"

    id = db.Column(db.Integer, primary_key=True)
    pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacy.id"), nullable=False)
    pharmacy = db.relationship("Pharmacy", backref=db.backref("dose_rules", order_by="PharmacyDoseRule.age_from_days"))

    age_from_days = db.Column(db.Integer, nullable=False)
    age_to_days = db.Column(db.Integer, nullable=False)
    dose_ml = db.Column(db.Float, nullable=False)

    created_at = db.Column(db.DateTime, default=_now)

    @staticmethod
    def find_dose(pharmacy_id: int, age_days: int | None) -> float | None:
        """يرجّع الجرعة المكتوبة مسبقاً للنطاق العمري المطابق، أو None لو
        العمر مجهول أو ما فيه نطاق مسجَّل يغطيه — بدون أي تقريب أو حساب."""
        if age_days is None:
            return None
        rule = (
            PharmacyDoseRule.query
            .filter(
                PharmacyDoseRule.pharmacy_id == pharmacy_id,
                PharmacyDoseRule.age_from_days <= age_days,
                PharmacyDoseRule.age_to_days >= age_days,
            )
            .first()
        )
        return rule.dose_ml if rule else None
