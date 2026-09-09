from datetime import datetime, timezone
from flask_babel import get_locale
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


# بند إصلاح (فحص عميق — طلبك: "افحص جميع النوافذ بعمق") — عناوين
# المهام اليومية التلقائية الأربعة الثابتة بالكود (`daily_task_service.
# _rule_definitions`) كانت تُكتب بـ`Task.title`/`Task.notes` عربي بحت
# **وقت الإنشاء**، فتبقى مجمَّدة بتلك اللغة للأبد بغض النظر عن لغة
# مين يشوف المهمة لاحقاً — عكس بقية الإصلاحات بهذي الجلسة (التي تُحسب
# وقت العرض). الحل هنا مختلف عمداً: عمود `title_key` ثابت يُخزَّن فقط
# لهذي المهام الأربعة المعروفة (`None` لأي مهمة ثانية — يدوية، أو من
# `DailyTaskTemplate` نص حر يكتبه صاحب الحلال بنفسه) — `display_title()`/
# `display_notes()` يترجمان حسب لغة العارض الحالية لو `title_key`
# موجود، وإلا يرجعان `title`/`notes` الخام كما هي (سلوك قديم محفوظ).
TASK_TITLE_TRANSLATIONS = {
    "daily_isolation_review": {
        "title_ar": "🚧 مراجعة العزل والحجر",
        "title_en": "🚧 Isolation & quarantine review",
        "notes_ar": "راجع الحيوانات الجديدة أو المريضة في حظيرة العزل قبل خلطها بالقطيع.",
        "notes_en": "Review new or sick animals in the isolation barn before mixing them with the herd.",
    },
    "daily_newborn_review": {
        "title_ar": "🍼 متابعة المواليد والرضاعة",
        "title_en": "🍼 Newborn & nursing follow-up",
        "notes_ar": "تأكد من رضاعة اللبأ ونشاط المواليد الجدد (عمر أقل من 30 يوماً).",
        "notes_en": "Make sure newborns (under 30 days old) are nursing colostrum and active.",
    },
    "daily_weaning_review": {
        "title_ar": "⚖️ مراجعة الفطام والفرز",
        "title_en": "⚖️ Weaning & sorting review",
        "notes_ar": "راجع الحملان بعمر الفطام (45-110 يوماً) وفرزها حسب الوزن والجنس.",
        "notes_en": "Review lambs at weaning age (45-110 days) and sort them by weight and sex.",
    },
    "daily_withdrawal_review": {
        "title_ar": "💊 مراجعة الحالات المرضية المفتوحة",
        "title_en": "💊 Open disease case review",
        "notes_ar": "تأكد من عدم وجود علاج مفتوح بلا متابعة، وفترة السحب مسجّلة قبل أي بيع.",
        "notes_en": "Make sure no open treatment is left unfollowed, and withdrawal periods are recorded before any sale.",
    },
}


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

    # بند إصلاح أداء (فحص "سرعة التصفح") — يُفلتَر عليه بشاشة "تنبيهاتي"
    # وقوائم مهام العامل المقيَّد بحظيرة، بدون فهرس سابق (عكس `assignee_id`/
    # `animal_id` بنفس الجدول اللي عندهما فهرس أصلاً).
    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=True, index=True)
    barn = db.relationship("Barn")
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True, index=True)
    animal = db.relationship("Animal")

    due_date = db.Column(db.Date, index=True)
    # موعد وقت محدد (بند إضافي 278) — لمهام حسّاسة بالوقت (حالياً وجبات
    # العلف المجدولة فقط، `feeding_schedule_service.py`)، عكس `due_date`
    # اللي على مستوى اليوم بس. فاضي لكل بقية أنواع المهام — الأصل غياب
    # موعد وقت محدد، لا صفر افتراضي زي الموعد نفسه ساعة 00:00.
    due_time = db.Column(db.Time, nullable=True)
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

    # تقييم جودة يدوي اختياري لمهمة مُنجزة (بند إضافي 229) — يضاف
    # بعد ما صاحب الحلال/الدكتور/الممرض يراجع المهمة فعلياً (مثلاً
    # يشيك العليقة بعد "إضافة علف")، بجانب النقطة التلقائية بتقرير
    # الأداء الشامل. "weak"/"medium"/"excellent" — الملاحظة إلزامية
    # بس لو "weak" (واجهة، مو قيد قاعدة بيانات).
    quality_rating = db.Column(db.String(16), nullable=True)
    quality_rating_note = db.Column(db.Text, nullable=True)
    quality_rated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    quality_rated_by = db.relationship("User", foreign_keys=[quality_rated_by_id])
    quality_rated_at = db.Column(db.DateTime, nullable=True)

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    # انظر `TASK_TITLE_TRANSLATIONS` أعلى الملف — يبقى `None` لأي مهمة
    # عادية (يدوية أو نص حر)، ما يغيّر أي سلوك قديم.
    title_key = db.Column(db.String(64), nullable=True)

    def display_title(self) -> str:
        entry = TASK_TITLE_TRANSLATIONS.get(self.title_key)
        if entry and str(get_locale()) != "ar":
            return entry["title_en"]
        return self.title

    def display_notes(self) -> str | None:
        entry = TASK_TITLE_TRANSLATIONS.get(self.title_key)
        if entry and str(get_locale()) != "ar":
            return entry["notes_en"]
        return self.notes


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
