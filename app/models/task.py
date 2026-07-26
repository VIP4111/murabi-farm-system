from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Task(db.Model):
    """
    مهمة عامل — يدوية (يوزّعها الدكتور مباشرة) أو مقترحة تلقائياً (تحتاج
    مراجعة الدكتور أولاً: موافقة/تأجيل/حذف، حسب دورة الحياة المتفق عليها).
    الحذف من الدكتور مو نهائي — يتحوّل لصندوق مراجعة صاحب الحلال حصرياً.
    """
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    task_type = db.Column(db.String(32), default="custom", nullable=False)
    # custom / isolation_check / weighing / vaccination_due / feed_switch / doctor_review / shearing

    status = db.Column(db.String(32), default="pending", nullable=False)
    # suggested / pending / in_progress / done / postponed / deleted_pending_review / cancelled

    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assignee = db.relationship("User", foreign_keys=[assignee_id])

    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=True)
    barn = db.relationship("Barn")
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True)
    animal = db.relationship("Animal")

    due_date = db.Column(db.Date)
    requires_photo = db.Column(db.Boolean, default=False, nullable=False)

    source_type = db.Column(db.String(32))
    source_id = db.Column(db.Integer)

    # مهام "علاج مخطَّط" (بند إضافي 50) — لو معبّاة، هذي المهمة تحمل خطة
    # علاج فعلية (دواء + جرعة) بانتظار "تأكيد التنفيذ": اختصار معبّى
    # مسبقاً لنموذج التسجيل الطبي الحقيقي (زيارة/تطعيم/مرض) حسب
    # `planned_treatment_kind`. الخصم الفعلي من الصيدلية ما يصير إلا
    # هناك (بند 46) — تخزين الخطة هنا صفر تأثير على المخزون بحد ذاته.
    planned_pharmacy_id = db.Column(db.Integer, db.ForeignKey("pharmacy.id"), nullable=True)
    planned_pharmacy = db.relationship("Pharmacy")
    planned_quantity = db.Column(db.Float, nullable=True)
    planned_treatment_kind = db.Column(db.String(16), nullable=True)  # vet_visit / disease / vaccination

    # تسلسل المهام (بند 21) — لو معبّى، هذي المهمة "مقفلة" ولا يقدر
    # العامل يبدأها/يُنجزها لين المهمة السابقة تصير status=done.
    depends_on_task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=True)
    depends_on = db.relationship("Task", remote_side=[id])

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    completion_note = db.Column(db.Text)
    completion_evidence_image_url = db.Column(db.String(255))

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)
