from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class FarmSettings(db.Model):
    """
    إعدادات زمنية عامة للمزرعة — صف واحد فقط (singleton، id=1 دائماً).
    القيم الافتراضية هنا مأخوذة من مواصفة المستخدم الرسمية، وقابلة للتعديل
    من شاشة الإعدادات بدون أي تعديل كود.
    """
    __tablename__ = "farm_settings"

    id = db.Column(db.Integer, primary_key=True)

    # هوية المزرعة لرأس الفاتورة (بند إضافي 75، 2026-07-31) — كلها اختيارية
    # عمداً، فراغها ما يمنع إصدار الفاتورة (يظهر بدون السطر الفاضي بس).
    farm_name = db.Column(db.String(160), nullable=True)
    farm_phone = db.Column(db.String(30), nullable=True)
    farm_address = db.Column(db.String(255), nullable=True)

    gestation_days = db.Column(db.Integer, default=150, nullable=False)
    sponge_duration_days = db.Column(db.Integer, default=14, nullable=False)
    ram_entry_after_sponge_days = db.Column(db.Integer, default=1, nullable=False)
    pre_birth_feed_change_days = db.Column(db.Integer, default=45, nullable=False)
    postpartum_feed_days = db.Column(db.Integer, default=45, nullable=False)
    male_sale_after_birth_days = db.Column(db.Integer, default=90, nullable=False)
    alert_before_days = db.Column(db.Integer, default=7, nullable=False)
    vaccination_repeat_days = db.Column(db.Integer, default=180, nullable=False)

    isolation_days = db.Column(db.Integer, default=7, nullable=False)
    doctor_check_hours = db.Column(db.Integer, default=48, nullable=False)
    postpartum_vaccination_days = db.Column(db.Integer, default=45, nullable=False)

    # فترة حجر الحيوان الوافد (شراء/هدية) قبل ما يدخل مرحلة الحجر والفحص —
    # قيمة اجتهادية مننا، مو من وثيقة المستخدم، لذا موثّقة هنا بشكل منفصل.
    quarantine_days = db.Column(db.Integer, default=21, nullable=False)

    # إعدادات تناسل الأم (بند 10.4 بالمواصفة) — تحدّد قائمة "أمهات جاهزة
    # للتقريع" (انظر app/core/animal_filters_service.py). قيم اجتهادية
    # مننا، مو من وثيقة المستخدم، لذا موثّقة هنا بشكل منفصل.
    min_breeding_age_days = db.Column(db.Integer, default=240, nullable=False)
    min_rest_after_birth_days = db.Column(db.Integer, default=60, nullable=False)

    # قائمة تهيئة النظام بالصفحة الرئيسية (بند إضافي، 2026-07-27) — تختفي
    # نهائياً بعد ما صاحب الحلال يضغط "تجاهل" بنفسه، بغض النظر هل خلّص
    # كل البنود أو لا (طلب صريح: "مرة وحدة بس، عندي أزرار تتكفل بهالموضوع").
    setup_checklist_dismissed = db.Column(db.Boolean, default=False, nullable=False)

    # محرك البيع الذكي (بند 19 بالمواصفة) — قيمك أنت بالضبط (2026-07-23):
    # الذكور يُباعون عادة بعمر 6 أشهر (180 يوم)، وسن الأضحية الشرعي
    # الأدنى للجذعة من الضأن هو 6 أشهر كاملة بالضبط (حديث "لا تذبحوا إلا
    # مسنة إلا أن يعسر عليكم فتذبحوا جذعة من الضأن") — حطينا هامش أمان
    # قليل فوق الحد الشرعي (195 يوم) عشان "فوق" الستة أشهر بالضبط كما
    # طلبت، قابل للتعديل. تأخر حمل الأنثى أكثر من شهرين (60 يوم) بدون
    # تقريع/حمل جديد = علامة بيع.
    target_profit_margin_percent = db.Column(db.Float, default=30.0, nullable=False)
    regular_sale_age_days = db.Column(db.Integer, default=180, nullable=False)
    udhiyah_min_age_days = db.Column(db.Integer, default=195, nullable=False)
    female_delayed_conception_days = db.Column(db.Integer, default=60, nullable=False)

    # شاشة التنبيهات (بند 20) — "بلاغ جديد بانتظار الاستلام لفترة طويلة".
    # قيمة اجتهادية مننا، مو من وثيقة المستخدم.
    report_stale_hours = db.Column(db.Integer, default=48, nullable=False)

    # وحدة النعام (بند 23) — مدة الحضانة القياسية لبيض النعام (ذكرت
    # 40-42 يوم، حطينا 42 كحد أعلى آمن، قابل للتعديل).
    ostrich_incubation_days = db.Column(db.Integer, default=42, nullable=False)

    # رادار المناخ والإجهاد الحراري (بند إضافي 49) — موقع واحد للمزرعة
    # كلها بقرارك الصريح، مو لكل حظيرة. فاضية افتراضياً لين المالك
    # يعبّيها بشاشة إعدادات المناخ — بدونها الميزة معطّلة بالكامل (ما
    # نخمّن موقعاً افتراضياً). حدود THI قيم عامة شائعة بأدبيات الإجهاد
    # الحراري للأبقار الحلوب (أقرب مرجع متوفر عمومياً)، تُطبَّق هنا
    # كتقريب عام للأغنام/الماعز لعدم توفر معيار رسمي خاص بها — قابلة
    # للتعديل من نفس الشاشة.
    farm_latitude = db.Column(db.Float, nullable=True)
    farm_longitude = db.Column(db.Float, nullable=True)
    thi_mild = db.Column(db.Float, default=72.0, nullable=False)
    thi_moderate = db.Column(db.Float, default=79.0, nullable=False)
    thi_severe = db.Column(db.Float, default=89.0, nullable=False)
    thi_emergency = db.Column(db.Float, default=98.0, nullable=False)

    # مهلة إعادة الوزن بعد تأكيد تنفيذ أي علاج مخطَّط (بند إضافي 50) —
    # تبدأ تُحسب فقط من لحظة "تأكيد التنفيذ" الفعلية (تحويل المهمة
    # لحالة "منجزة")، مو من لحظة اقتراح المهمة أو خطة العلاج.
    reweigh_followup_days = db.Column(db.Integer, default=14, nullable=False)

    # حارس منع تكرار جرعة الطفيليات (بند إضافي 50) — تحذير فقط يتيح
    # للطبيب التجاوز بسبب صريح مكتوب، مو حظراً نهائياً (قرارك الصريح).
    antiparasitic_redose_days = db.Column(db.Integer, default=30, nullable=False)

    # محرك القواعد الطبية/التغذوية الذكي (بند إضافي 51) — كل الحدود هنا
    # تحذير + تجاوز بسبب صريح (بقرارك).
    concentrate_increase_max_percent_weekly = db.Column(db.Float, default=10.0, nullable=False)
    concentrate_increase_window_days = db.Column(db.Integer, default=7, nullable=False)
    ca_phosphorus_target_ratio = db.Column(db.Float, default=2.0, nullable=False)
    ca_phosphorus_tolerance = db.Column(db.Float, default=0.5, nullable=False)
    abortion_barn_monitor_days = db.Column(db.Integer, default=14, nullable=False)

    # جدولة تلقائية حقيقية (بند إضافي 78، 2026-08-01) — يمنع تكرار توليد
    # المهام اليومية أكثر من مرة بنفس اليوم لو أكثر من عملية worker
    # بغانيكورن حاولت بنفس الوقت (حراسة بسيطة، مو قفل موزَّع مثالي —
    # المنطق نفسه بـdaily_task_service أصلاً idempotent فيصير احتياطاً
    # مزدوجاً، مو الحارس الوحيد).
    last_daily_tasks_auto_run = db.Column(db.Date, nullable=True)

    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    @classmethod
    def get(cls) -> "FarmSettings":
        settings = cls.query.get(1)
        if settings is None:
            settings = cls(id=1)
            db.session.add(settings)
            db.session.commit()
        return settings
