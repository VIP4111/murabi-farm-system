from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class AnimalBatch(db.Model):
    """دفعة استقبال قطيع جديد (بند إضافي 52، جزء 2) — مسار 3 مراحل:
    1) حجر صحي وأوليات (تسجيل + عزل + رش + تحصين مبدئي) — تصير عند
    إنشاء الدفعة نفسها مباشرة. 2) ترقيم/فحص سلامة فردي. 3) توزيع على
    حظائر دائمة + ربط بنظام العليقة. التقدّم بين المراحل جماعي بضغطة
    زر واحدة (قرارك الصريح)، مع إمكانية عزل/استبعاد رأس مشتبه بها
    فردياً (`Animal.batch_hold_reason`) فتبقى بمرحلتها الحالية بينما
    تتقدّم بقية الدفعة السليمة معاً."""
    __tablename__ = "animal_batches"

    STAGE_QUARANTINE = 1   # حجر صحي وأوليات
    STAGE_TAGGING = 2      # ترقيم وفحص سلامة فردي
    STAGE_DISTRIBUTED = 3  # توزيع على حظائر دائمة + ربط عليقة (نهائي)

    SOURCES = ["purchase", "gift"]

    id = db.Column(db.Integer, primary_key=True)
    batch_no = db.Column(db.String(40), unique=True, nullable=False)
    source = db.Column(db.String(20), nullable=False)
    stage = db.Column(db.Integer, default=STAGE_QUARANTINE, nullable=False)
    arrival_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)

    animals = db.relationship("Animal", back_populates="batch")
