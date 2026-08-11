"""دليل المربي المبتدئ ومحرك التوجيه اليومي/الأسبوعي (بند إضافي 168)
— قائمة تحقق ديناميكية تتغيّر حسب مرحلة القطيع الفعلية (تجهيز/شياع/
حمل/ولادة/تسمين، بمعزل عن "عام" الثابت دائماً)، مو قائمة واحدة ثابتة
للجميع. مصدرها هنا بيانات ابتدائية بالكود (seed idempotent بـ
`flask seed`، نفس فلسفة DEFAULT_EMERGENCY_SYMPTOMS) — قابلة للتوسيع
لاحقاً من لوحة إدارة بدون كود، لكن هذا البند يبني المحرك والمحتوى
الافتراضي أولاً."""
from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class ChecklistItem(db.Model):
    __tablename__ = "checklist_items"

    # عام: يظهر دائماً بغض النظر عن حالة القطيع. البقية تظهر بس لو
    # المرحلة المقابلة فعلاً نشطة بالمزرعة الآن (`checklist_service.active_stages`).
    STAGES = ["general", "prep", "estrus", "pregnancy", "birth", "fattening"]
    FREQUENCIES = ["once", "daily", "weekly"]
    # "all" = يظهر لكل الأدوار. "beginner" وسم إضافي مستقل عن الدور
    # الوظيفي — يُفلتَر بمعزل عنها حسب `User.is_beginner`.
    ROLES = ["owner", "doctor", "worker", "beginner", "all"]

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    stage = db.Column(db.String(16), default="general", nullable=False)
    frequency = db.Column(db.String(16), default="once", nullable=False)
    target_role = db.Column(db.String(16), default="all", nullable=False)
    title = db.Column(db.String(220), nullable=False)
    description = db.Column(db.Text)
    # الشرح التثقيفي ("ليش؟") — منفصل عمداً عن `description` (وش تسوي
    # بالضبط) — يشرح المنطق البيولوجي/التشغيلي وراء البند، يظهر بس
    # لمن يفتحه (طيّة قابلة للطي بالواجهة) عشان ما يثقل القائمة اليومية
    # لمن أصلاً يعرف السبب (بند إضافي 170).
    rationale = db.Column(db.Text)
    link_endpoint = db.Column(db.String(100))
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)


class ChecklistCompletion(db.Model):
    """إنجاز مستخدم لعنصر دليل خلال فترة معيّنة — `period_key` يحدد
    الفترة: 'once' ثابت للعناصر لمرة وحدة، أو تاريخ اليوم (ISO) لليومي،
    أو تاريخ بداية الأسبوع (ISO) للأسبوعي — يسمح بإعادة ظهور نفس
    العنصر تلقائياً بالفترة التالية بدون أي مهمة تنظيف يدوية."""
    __tablename__ = "checklist_completions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User")
    checklist_item_id = db.Column(db.Integer, db.ForeignKey("checklist_items.id"), nullable=False)
    checklist_item = db.relationship("ChecklistItem")
    period_key = db.Column(db.String(16), nullable=False)
    completed_at = db.Column(db.DateTime, default=_now)

    __table_args__ = (
        db.UniqueConstraint("user_id", "checklist_item_id", "period_key", name="uq_checklist_completion"),
    )
