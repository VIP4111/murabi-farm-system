from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class Report(db.Model):
    """
    بلاغ (تذكرة) — دورة حياته: جديد → مقبول/مؤجل/ملغى → [لو مقبول] منفّذ
    بانتظار المراجعة → مغلق (= مؤرشف تلقائياً بنفس اللحظة).

    نقطة تصميم أساسية: حقل `manager_id` (الدكتور اللي استلم البلاغ) وحقل
    `executor_id` (اللي تحوّل له التنفيذ) منفصلان تماماً عن قصد — التنفيذ
    ممكن يتحوّل لأي عضو فريق، لكن الإغلاق يبقى حصراً لصاحب `manager_id`
    مهما تحوّلت التذكرة، حسب اتفاق صريح مع صاحب النظام (انظر app/team/report_service.py).
    """
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)

    # بند إصلاح (فحص أداء — طلبك: "فحص أداء/سرعة الموقع") — الأعمدة
    # التالية تُفلتَر عليها الاستعلامات مباشرة بكل زيارة لشاشات
    # "البلاغات"/"صفحة اليوم" (reports_list/today، app/team/routes.py)،
    # بعكس أعمدة Task المكافئة (assignee_id/created_by_id...) اللي كانت
    # مفهرَسة أصلاً — هذي بقيت بلا فهرسة تماماً منذ إنشاء الجدول. على
    # مزرعة فيها آلاف البلاغات المتراكمة، تتحول تدريجياً لمسح تسلسلي
    # كامل بكل مرة. index=True على كل عمود يُستخدم بفلترة مباشرة
    # (reporter_id, manager_id, executor_id, status) + العمودين
    # المرتبطين بالحيوان/الحظيرة (يُستخدمان بشاشة تفاصيل الحيوان
    # وتقارير الحظيرة). closer_id ما يُفلتَر عليه مباشرة بأي شاشة حالياً،
    # فبقي بلا فهرسة عمداً (فهرسة عمود بلا استعلام فعلي عليه تكلفة كتابة
    # صافية بلا فائدة قرائية).
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    reporter = db.relationship("User", foreign_keys=[reporter_id])

    report_type = db.Column(db.String(64))
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True, index=True)
    animal = db.relationship("Animal")
    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=True, index=True)
    barn = db.relationship("Barn")

    description = db.Column(db.Text, nullable=False)
    evidence_image_url = db.Column(db.String(255))
    evidence_audio_url = db.Column(db.String(255))

    status = db.Column(db.String(32), default="new", nullable=False, index=True)
    # new / accepted / postponed / cancelled / executed_pending_review / closed

    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    manager = db.relationship("User", foreign_keys=[manager_id])

    executor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    executor = db.relationship("User", foreign_keys=[executor_id])
    transfer_note = db.Column(db.Text)

    closer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    closer = db.relationship("User", foreign_keys=[closer_id])

    execution_note = db.Column(db.Text)
    execution_evidence_image_url = db.Column(db.String(255))
    execution_evidence_audio_url = db.Column(db.String(255))

    postpone_reason = db.Column(db.Text)
    cancel_reason = db.Column(db.Text)

    accepted_at = db.Column(db.DateTime)
    transferred_at = db.Column(db.DateTime)
    executed_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=_now)
