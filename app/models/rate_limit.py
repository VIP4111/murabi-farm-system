from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class RateLimitHit(db.Model):
    """سجل طلبات لتحديد المعدل (بند إضافي 119) — مخزَّن بقاعدة البيانات
    عمداً، مو ذاكرة بايثون داخل العملية: السيرفر الفعلي يشتغل بأكثر من
    عملية worker (`gunicorn --workers 2`، نفس سبب بند 86 لقفل الدخول) —
    عدّاد بالذاكرة يحسب كل عملية لحالها، فيسمح فعلياً بضعف الحد المسموح.
    الصفوف القديمة تُنظَّف تلقائياً عند كل فحص (`check_and_record`)."""
    __tablename__ = "rate_limit_hits"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    key = db.Column(db.String(64), nullable=False)  # مثال: "report_submit"
    created_at = db.Column(db.DateTime, default=_now)
