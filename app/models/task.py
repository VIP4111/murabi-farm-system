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

    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    assignee = db.relationship("User", foreign_keys=[assignee_id])

    # الدور المستهدف (بند إضافي 68، 2026-07-28) — منفصل عمداً عن
    # assignee_id: مهمة "مقترحة" كثيراً ما ما لها شخص معيّن بعد (خصوصاً
    # لو الحظيرة بلا عامل مسؤول)، فيحتاج فلتر الدور معياراً يبقى شغّالاً
    # حتى قبل التعيين الفعلي. يخزّن `Role.name` (worker/doctor/accountant/
    # ...) — نص حر مو FK صارم، عشان يبقى مرناً مع أدوار مخصَّصة يضيفها
    # المالك لاحقاً من الإعدادات.
    target_role = db.Column(db.String(32), nullable=True)

    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=True)
    barn = db.relationship("Barn")
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True, index=True)
    animal = db.relationship("Animal")

    due_date = db.Column(db.Date, index=True)
    requires_photo = db.Column(db.Boolean, default=False, nullable=False)

    # ترتيب عرض ثانوي (بند إضافي 67، 2026-07-28) — لما أكثر من مهمة
    # يتشاركون نفس due_date (حالة المهام اليومية التلقائية بالذات)، ما
    # فيه معيار حاسم لترتيب عرضهم غير ترتيب الإدراج بقاعدة البيانات
    # (غير مضمون). رقم أصغر = يظهر أول — يُستخدم بالذات لفرض تسلسل
    # العمل الميداني المنطقي (تنظيف ← ماء/علف ← فحص القطيع)، صفر افتراضي
    # لبقية أنواع المهام (ما يأثّر على ترتيبها).
    sort_order = db.Column(db.Integer, default=0, nullable=False)

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

    # تتبّع تنفيذ العامل بدقة (بند 27.11 — كان موثّقاً كفجوة، أُغلق ببند
    # إضافي 54) — مين باشر التنفيذ فعلياً (قد يختلف عن assignee_id لو
    # عامل ثاني غطّى المناوبة)، مدة التنفيذ الفعلية بالدقائق، وحالة/سبب
    # التعذّر لو ما قدر العامل يُنجزها، مع ملاحظة صوتية منفصلة عن صورة
    # الدليل. server_time_source ثابت "server" على كل توقيت — توثيق إن
    # الوقت من ساعة السيرفر مو جهاز العامل (قد يكون غير دقيق أو معطَّل).
    accepted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    accepted_by = db.relationship("User", foreign_keys=[accepted_by_id])
    duration_minutes = db.Column(db.Integer)
    server_time_source = db.Column(db.String(16))

    failed_at = db.Column(db.DateTime)
    failure_reason = db.Column(db.String(64))
    voice_note_url = db.Column(db.String(255))

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)


class DailyTaskTemplate(db.Model):
    """قالب مهمة يومية متكررة يديره صاحب الحلال/الدكتور مباشرة من الواجهة
    (بند إضافي 107) — قبل هذا البند، المهام اليومية الثابتة (تنظيف/سقاية/
    فحص) كانت 3 قواعد مكتوبة بالكود نفسه (`daily_task_service._rule_
    definitions`)، وإضافة أو إيقاف أي وحدة منها يحتاج تعديل كود فعلي.
    القواعد "الذكية" الأربع الباقية (مراجعة عزل/مواليد/فطام/سحب دواء —
    تعتمد على شرط حي بحالة المزرعة، مو مجرد نص ثابت) بقيت بالكود عمداً،
    ما تحوّلت لقوالب."""
    __tablename__ = "daily_task_templates"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)
