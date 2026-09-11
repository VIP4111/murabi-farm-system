from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class ContractTemplate(db.Model):
    """نموذج بنود عقد عمل حسب المسمى الوظيفي (بند إصلاح — طلبك الصريح:
    "كل مسمى وظيفي له بنود تختلف... سائق/عامل منزلي/عامل زراعي/راعي/
    عامل مقاولات نجار أو بناء أو حداد" ثم "نعم ابيك تبنيها وتعطيني
    صلاحية تعديل على البنود فيما بعد").

    `clauses_text` نص حر يعدّله صاحب الحلال بنفسه بالكامل (سطر لكل
    بند تقريباً) — عمداً بدون تقسيم لبنود منفصلة بجدول، عشان يبقى
    التعديل حر وبسيط (نسخ/لصق/إعادة صياغة) بدون تعقيد واجهة إضافية.
    النصوص المبدئية المزروعة (seed) مسودة عامة، لازم تُراجَع قانونياً
    قبل الاستخدام الفعلي — نفس التحذير المعروض بشاشة الطباعة."""
    __tablename__ = "contract_templates"

    id = db.Column(db.Integer, primary_key=True)
    job_title = db.Column(db.String(120), unique=True, nullable=False)
    clauses_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)
