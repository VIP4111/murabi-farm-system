import os
from flask import Flask, send_from_directory, request, abort, render_template
from flask_login import current_user
from flask_babel import lazy_gettext as _l
from app.config import Config
from app.extensions import db, migrate, login_manager, babel, csrf

# لغات RTL بين اللغات المدعومة (بند إضافي، 2026-07-23) — العربي فقط
# حالياً. الأمهرية والهندية بأبجديتيهما الأصليتين LTR رغم إنها لغات
# غير أوروبية، فما تحتاج قلب اتجاه.
RTL_LANGUAGES = {"ar"}


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # UPLOAD_DIR افتراضياً جوّا static/uploads (نفس مكانه القديم بالضبط)
    # لو ما انضبط env var — يُحسم هنا لأنه يحتاج app.static_folder
    # الجاهز (بند إضافي 77).
    if not app.config.get("UPLOAD_DIR"):
        app.config["UPLOAD_DIR"] = os.path.join(app.static_folder, "uploads")

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    def select_locale():
        # لغة المستخدم المسجّل دخوله (User.language) هي المصدر الأساسي —
        # ما نعتمد على لغة المتصفح عشان نفس الحساب يشتغل بنفس اللغة على
        # أي جهاز. قبل تسجيل الدخول (شاشة /login) نستخدم اختيار الجلسة
        # المؤقت (زر اللغة بصفحة الدخول نفسها) لو موجود — بدونه عربي
        # افتراضياً، لأن العامل غير الناطق بالعربي يحتاج يقرأ حقول
        # الدخول نفسها بلغته قبل ما يوصل لأي شاشة بعد الدخول.
        from flask import session, has_request_context
        # حارس سياق الطلب (بند إضافي 165) — بعض دوال الخدمة (تقارير)
        # تستدعي نصوصاً مترجَمة بشكل كسول (`_l()`) من اختبارات وحدة بلا
        # طلب HTTP فعلي، فـ`current_user` ما يكون متاحاً — نرجع عربي
        # افتراضياً بدل ما ننهار، نفس سلوك "بدون تسجيل دخول" أصلاً.
        if not has_request_context():
            return "ar"
        if current_user.is_authenticated and current_user.language in app.config["SUPPORTED_LANGUAGES"]:
            return current_user.language
        if session.get("lang") in app.config["SUPPORTED_LANGUAGES"]:
            return session["lang"]
        return "ar"

    babel.init_app(app, default_locale="ar", locale_selector=select_locale)

    @app.context_processor
    def inject_locale_dir():
        from flask_babel import get_locale
        lang = str(get_locale())
        return {"html_lang": lang, "html_dir": "rtl" if lang in RTL_LANGUAGES else "ltr"}

    @app.context_processor
    def inject_theme():
        # الوضع الليلي/النهاري الشخصي (بند إضافي 158) — تفضيل محفوظ
        # بحساب المستخدم، نفس فلسفة اللغة أعلاه بالضبط.
        theme = current_user.theme if current_user.is_authenticated else "light"
        return {"html_theme": theme}


    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.auth import auth_bp
    from app.core import core_bp
    from app.health import health_bp
    from app.finance import finance_bp
    from app.repro import repro_bp
    from app.team import team_bp
    from app.feed import feed_bp
    from app.reports import reports_bp
    from app.ostrich import ostrich_bp
    from app.assistant import assistant_bp
    from app.climate import climate_bp
    from app.batches import batches_bp
    from app.warehouses import warehouses_bp
    from app.equipment import equipment_bp
    from app.onboarding import onboarding_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(core_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(repro_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(feed_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(ostrich_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(climate_bp)
    app.register_blueprint(batches_bp)
    app.register_blueprint(warehouses_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(onboarding_bp)

    from app.cli import register_cli
    register_cli(app)

    from app.core.scheduler import init_scheduler, catch_up_daily_tasks_before_request
    init_scheduler(app)

    if not app.config.get("TESTING"):
        @app.before_request
        def _catch_up_daily_tasks():
            # بند إضافي 89 (نقطة 6) — تدارك لو الـCron الداخلي فاته
            # (Render المجاني نايم وقت الساعة 3 فجراً)، بدل ما نعتمد
            # على توقيت دقيق قد ما يصير أصلاً. فشل هذا الفحص عمداً ما
            # يوقف الطلب نفسه — مجرد تدارك أفضلية، مو مسار حرج.
            try:
                catch_up_daily_tasks_before_request()
            except Exception as e:
                app.logger.warning("catch_up_daily_tasks_before_request failed: %s", e)
                # بند إصلاح — "Internal Server Error" بعد ما السيرفر
                # ينام فترة (Render المجاني) ويرجع يفوق: أول اتصال
                # لقاعدة البيانات بعد الخمول أحياناً يفشل (Neon يقفل
                # الاتصالات الخاملة تلقائياً). الفشل هنا كان يُبتلع
                # صمتاً بـ`except` فوق — بس بدون `rollback()`، جلسة
                # SQLAlchemy تبقى "معطوبة" (PendingRollbackError) لبقية
                # هذا الطلب نفسه، فأي استعلام حقيقي بعدها بنفس الطلب
                # (بالشاشة اللي طلبها المستخدم فعلياً) يفشل بخطأ سيرفر
                # عام، رغم إن هذا الفحص التداركي نفسه مفروض غير حرج.
                from app.extensions import db
                db.session.rollback()

    # قيم `_l()` بدل نص عربي خام (بند إضافي 74، 2026-07-31) — عشان
    # ar_status/ar_task_type تترجم فعلياً للأمهرية/الهندية/الإنجليزية
    # بشاشات العامل المترجمة (كانت قبل كذا تطلع عربي دايماً بغض النظر
    # عن لغة المستخدم، وهذا سبب رئيسي لتداخل الكلمتين اللي لاحظه المستخدم).
    STATUS_LABELS_AR = {
        "active": _l("نشط"),
        "inactive": _l("غير نشط"),
        "sold": _l("مباع"),
        "dead": _l("نافق"),
        "unpaid": _l("غير مدفوع"),
        "paid": _l("مدفوع"),
        "closed": _l("مغلق"),
        "deleted": _l("محذوف/مؤرشف"),
        "out_of_order": _l("ترتيب غير منتظم"),
        "new": _l("جديد"),
        "postponed": _l("مؤجّل"),
        "executed_pending_review": _l("منفّذ — بانتظار المراجعة"),
        "suggested": _l("مقترحة"),
        "in_progress": _l("قيد التنفيذ"),
        "done": _l("منجزة"),
        "deleted_pending_review": _l("بانتظار مراجعة المالك"),
        "completed": _l("مكتمل"),
        "cancelled": _l("ملغى"),
        "pending": _l("قيد الانتظار"),
        "eligible": _l("مؤهّلة"),
        "not_eligible": _l("غير مؤهّلة"),
        "confirmed": _l("مؤكّدة"),
        "failed": _l("فشلت"),
        # بند إصلاح — دفعات البيع (SaleLot.status) كانت تطلع "open"
        # حرفياً بالإنجليزي بشاشة "دفعات البيع" (finance/lots_list.html)
        # بغض النظر عن لغة المستخدم، لأن القالب يطبع `lot.status` خام
        # بدون فلتر `ar_status` أصلاً.
        "open": _l("مفتوحة"),
        "archived": _l("مؤرشفة"),
    }

    # بند إصلاح — نفس فئة فجوة "open" بدفعات البيع: حقل "الشدة" بشاشة
    # تسجيل مرض (health/disease_form.html وbulk_action_form.html، خيار
    # 'disease') يخزّن قيمة إنجليزية ثابتة (light/medium/severe)
    # كـ`Disease.severity`، وكذا شاشة تعرضها خام بدون ترجمة
    # (health/diseases_list.html، health/dashboard.html، animal_detail.html).
    # قاموس مستقل عن STATUS_LABELS_AR (مو مدموج فيه) لأن "light" تُستخدم
    # أصلاً بقيمة ثانية غير مرتبطة (`User.theme`) — دمجهما بنفس القاموس
    # يخاطر بتسريب ترجمة خاطئة لو "الوضع الفاتح" استُخدم يوماً مع نفس الفلتر.
    DISEASE_SEVERITY_LABELS_AR = {
        "light": _l("بسيطة"),
        "medium": _l("متوسطة"),
        "severe": _l("شديدة"),
    }

    @app.template_filter("ar_severity")
    def ar_severity(value):
        return DISEASE_SEVERITY_LABELS_AR.get(value, value)

    @app.template_filter("ar_status")
    def ar_status(value):
        return STATUS_LABELS_AR.get(value, value)

    # أسماء عربية لأنواع المهام (بند إضافي 66، 2026-07-28) — نفس نمط
    # STATUS_LABELS_AR بالضبط. القائمة الكاملة الفعلية لكل القيم
    # المستخدمة عبر الكود (isolation_service/protocol_service/
    # animal_service/batch_service/daily_task_service/pregnancy_care_service/
    # climate_service/core.routes/task_service) — بدون هذا كان يطلع النص
    # الخام (مثال "daily_husbandry") مباشرة بشاشة المهام.
    TASK_TYPE_LABELS_AR = {
        "custom": _l("مهمة عامة"),
        "isolation_check": _l("فحص عزل"),
        "doctor_review": _l("مراجعة الدكتور"),
        "cord_antisepsis": _l("تعقيم السرّة"),
        "selenium_dose": _l("جرعة سيلينيوم"),
        "colostrum_check": _l("متابعة اللبأ/الرضاعة"),
        "weighing": _l("وزن"),
        "vaccination_due": _l("تحصين مستحق"),
        "feed_switch": _l("تبديل علف"),
        "abortion_sampling": _l("أخذ عينات إجهاض"),
        "abortion_barn_monitor": _l("مراقبة حظيرة بعد إجهاض"),
        "protocol_step": _l("خطوة بروتوكول علاج"),
        "batch_spray": _l("رش وقائي (دفعة)"),
        "batch_initial_vaccination": _l("تحصين مبدئي (دفعة)"),
        "move_to_pregnant_barn": _l("نقل لحظيرة الحوامل"),
        "batch_tagging_check": _l("فحص ترقيم (دفعة)"),
        "batch_feed_link": _l("ربط علف (دفعة)"),
        "daily_husbandry": _l("رعاية يومية"),
        "late_pregnancy_care": _l("رعاية حمل متأخر"),
        "planned_treatment": _l("علاج مخطَّط"),
        "reweigh_followup": _l("متابعة إعادة وزن"),
        "heat_feed_timing": _l("تعديل توقيت العلف (إجهاد حراري)"),
        "heat_water_additive": _l("إضافة ماء (إجهاد حراري)"),
        "heat_ventilation": _l("فحص تهوية (إجهاد حراري)"),
        "heat_shade": _l("فحص تظليل (إجهاد حراري)"),
        "shearing": _l("جزّ صوف"),
        "sonar_recheck": _l("إعادة فحص سونار"),
        "protocol_effectiveness_review": _l("تقييم فعالية العلاج"),
        "isolation_release_check": _l("تأكيد انتهاء العزل"),
        "withdrawal_reminder": _l("تذكير انتهاء فترة سحب الدواء"),
        "feeding_schedule": _l("وجبة علف مجدولة"),
        "barn_physiology_move": _l("نقل حظيرة (حالة فسيولوجية)"),
        "animal_data_completion": _l("إكمال بيانات حيوان"),
        # بند إضافي (2026-08-31) — لُقِطت أثناء الفحص: outbreak_review
        # (app/core/outbreak_service.py) كانت الوحيدة الناقصة من هذا
        # القاموس بين كل أنواع المهام المسجَّلة — عنوانها كان يبقى
        # عربياً خاماً دايماً بغض النظر عن لغة المشاهد.
        "outbreak_review": _l("مراجعة احتمال عدوى منتشرة"),
    }

    @app.template_filter("ar_task_type")
    def ar_task_type(value):
        return TASK_TYPE_LABELS_AR.get(value, value)

    # بند إضافي (2026-08-30) — طلبك الصريح بعد بلاغك: "التنبيهات والمهام
    # طلعت عند الدكتور بالعربي" (الدكتور مسجَّل إنجليزي بحسابه). السبب
    # الجذري: عنوان المهمة (`Task.title`) نص عربي كامل يُبنى ويُخزَّن
    # حرفياً وقت الإنشاء بعشرات الأماكن بالكود (isolation_service،
    # protocol_service، animal_service، batch_service، daily_task_service،
    # pregnancy_care_service، climate_service، core.routes، task_service)
    # — تعديل كل هذي الأماكن لتخزين نص قابل للترجمة كان شغلاً ضخماً
    # وخطراً حقيقياً (احتمال نسيان مكان). الحل الأسلم المكافئ: نعيد بناء
    # العنوان المعروض **وقت العرض** من حقول موجودة أصلاً ودائماً مضبوطة
    # صح بغض النظر عن نص `title` الخام — `task_type` (له ترجمة جاهزة
    # بـTASK_TYPE_LABELS_AR فوق) + رقم الحيوان/اسم الحظيرة المرتبطة
    # (بيانات محايدة لغوياً أو من اختيار المستخدم نفسه، مو نص نظام).
    # المهام "العامة" (custom) نص حر كتبه إنسان بنفسه — نتركها كما هي،
    # نفس منطق عدم ترجمة اسم الحظيرة/الحيوان. "daily_husbandry" استثناء
    # مهم مماثل: كل قواعد المهام اليومية (`DailyTaskTemplate`، قابلة
    # للتعديل من الواجهة بواسطة صاحب الحلال) تشترك بنفس task_type
    # الواحد هذا — التمييز الحقيقي بينها (تنظيف/سقاية/فحص...) موجود
    # بـ`title` نفسه فقط، فاستبداله بترجمة عامة واحدة "رعاية يومية" كان
    # يفقد المعلومة الفعلية بدل ما يترجمها (خلل حقيقي لقيناه أثناء
    # الاختبار، صحّحناه هنا).
    _RAW_TITLE_TASK_TYPES = {"custom", "daily_husbandry"}

    def task_display_title(task):
        if not task or task.task_type in _RAW_TITLE_TASK_TYPES or task.task_type not in TASK_TYPE_LABELS_AR:
            return task.title if task else ""
        label = str(TASK_TYPE_LABELS_AR[task.task_type])
        ref = task.animal.animal_no if task.animal else (task.barn.display_name() if task.barn else None)
        return f"{label} — {ref}" if ref else label

    app.jinja_env.globals["task_display_title"] = task_display_title

    # أنواع بلاغ معروفة (بند إضافي 74) — نفس القيم الفعلية المستخدمة عبر
    # WORKER_REPORT_CATEGORIES (app/team/routes.py) وقائمة report_form.html
    # الافتراضية. القيمة المخزّنة بـReport.report_type تبقى عربي دايماً؛
    # أي نوع بلاغ مخصّص كتبه المستخدم يدوياً (زر "+ إضافة") يرجع كما هو
    # بدون ترجمة (fallback آمن، نفس أسلوب ar_status/ar_task_type).
    REPORT_TYPE_LABELS_AR = {
        "حالة طارئة": _l("حالة طارئة"),
        "حالة صحية": _l("حالة صحية"),
        "نقل للعزل": _l("نقل للعزل"),
        "تغذية / عليقة": _l("تغذية / عليقة"),
        "بيض / حضانة نعام": _l("بيض / حضانة نعام"),
        "مرض": _l("مرض"),
        "مشكلة": _l("مشكلة"),
        "صيانة": _l("صيانة"),
        "أخرى": _l("أخرى"),
    }

    @app.template_filter("ar_report_type")
    def ar_report_type(value):
        return REPORT_TYPE_LABELS_AR.get(value, value)

    # سجل التدقيق (بند إضافي 192) — `AuditLog.action` و`AuditLog.entity_type`
    # كانا يُعرَضان بمفاتيح الكود الخام (report.accept، user.edit، Animal...)
    # بدل نص عربي مقروء — نفس أسلوب ar_status/ar_report_type بالضبط: قاموس
    # ثابت + fallback آمن (قيمة غير معروفة ترجع كما هي، ما تختفي بصمت).
    AUDIT_ACTION_LABELS_AR = {
        "animal.bulk_barn_move": _l("نقل حظائر جماعي"),
        "animal.bulk_isolation": _l("عزل جماعي"),
        "animal.bulk_purchase": _l("شراء دفعة جماعي"),
        "animal.bulk_purpose": _l("تحديد غرض جماعي"),
        "animal.create": _l("إضافة حيوان"),
        "animal.death": _l("تسجيل نفوق"),
        "animal.delete": _l("حذف حيوان"),
        "animal.edit": _l("تعديل بيانات حيوان"),
        "animal.enter_isolation": _l("دخول عزل"),
        "animal.exit_isolation": _l("خروج من عزل"),
        "animal.sale_cancelled_restore": _l("استرجاع بيع ملغى"),
        "animal.sell": _l("بيع حيوان"),
        "backup.create": _l("إنشاء نسخة احتياطية"),
        "barn.create": _l("إضافة حظيرة"),
        "barn.update": _l("تعديل حظيرة"),
        "batch.advance_single_animal": _l("تقديم رأس بالدفعة"),
        "batch.advance_stage": _l("تقديم مرحلة الدفعة"),
        "batch.create": _l("إنشاء دفعة"),
        "batch.distribute": _l("توزيع دفعة"),
        "batch.hold_animal": _l("إيقاف رأس بالدفعة"),
        "batch.release_hold": _l("فك إيقاف رأس بالدفعة"),
        "daily_task_template.create": _l("إضافة قالب مهمة يومية"),
        "daily_task_template.toggle": _l("تفعيل/إيقاف قالب مهمة يومية"),
        "disease.close": _l("إغلاق حالة مرضية"),
        "disease.create": _l("تسجيل حالة مرضية"),
        "disease_symptom_link.create": _l("ربط مرض بعرض"),
        "disease_symptom_link.delete": _l("حذف ربط مرض بعرض"),
        "disease_symptom_link.update": _l("تعديل ربط مرض بعرض"),
        "disease_symptom_link.wizard_batch": _l("ربط أعراض بمرض (دفعة)"),
        "emergency_symptom.create": _l("إضافة عرض طوارئ"),
        "emergency_symptom.delete": _l("حذف عرض طوارئ"),
        "feed.ca_phosphorus_override": _l("تجاوز تحذير كالسيوم/فسفور"),
        "feed.concentrate_increase_override": _l("تجاوز تحذير زيادة المركّزات"),
        "feed_ration.create": _l("إضافة وصفة علف"),
        "finance.cancel": _l("إلغاء حركة مالية"),
        "health.redose_override": _l("تجاوز تحذير إعادة جرعة"),
        "ostrich_egg.fail": _l("تسجيل فشل بيضة"),
        "ostrich_egg.hatch": _l("تسجيل فقس بيضة"),
        "pharmacy.purchase": _l("شراء دواء"),
        "pregnancy.abortion": _l("تسجيل إجهاض"),
        "protocol.create": _l("إنشاء بروتوكول علاج"),
        "report.accept": _l("قبول بلاغ"),
        "report.cancel": _l("إلغاء بلاغ"),
        "report.close": _l("إغلاق بلاغ"),
        "report.delete_final": _l("حذف بلاغ نهائي"),
        "report.execute": _l("تنفيذ بلاغ"),
        "report.postpone": _l("تأجيل بلاغ"),
        "report.resume": _l("استئناف بلاغ"),
        "report.submit": _l("رفع بلاغ"),
        "report.transfer": _l("تحويل بلاغ"),
        "role.create": _l("إنشاء مسمّى وظيفي"),
        "role.update_permissions": _l("تعديل صلاحيات مسمّى وظيفي"),
        "sales_lot.create": _l("إنشاء دفعة بيع"),
        "sales_lot.delete": _l("حذف دفعة بيع"),
        "service.toggle": _l("تفعيل/إيقاف خدمة"),
        "simulation_data.purge": _l("حذف بيانات محاكاة"),
        "sonar.bulk_create": _l("تسجيل سونار جماعي"),
        "task.approve": _l("اعتماد مهمة مقترحة"),
        "task.assign": _l("تعيين مهمة"),
        "task.cancel_active": _l("إلغاء مهمة نشطة"),
        "task.complete": _l("إنجاز مهمة"),
        "task.complete_via_treatment": _l("إنجاز مهمة عبر تنفيذ علاج"),
        "task.delete_final": _l("حذف مهمة نهائي"),
        "task.fail": _l("تسجيل تعذّر مهمة"),
        "task.owner_restore": _l("استرجاع مهمة محذوفة"),
        "task.postpone": _l("تأجيل مهمة"),
        "task.postpone_active": _l("تأجيل مهمة نشطة"),
        "task.soft_delete": _l("حذف مهمة (بانتظار مراجعة)"),
        "user.create": _l("إضافة مستخدم"),
        "user.edit": _l("تعديل مستخدم"),
        "user.toggle": _l("تفعيل/إيقاف مستخدم"),
        "vaccination.create": _l("تسجيل تحصين"),
        "vaccination_schedule.create": _l("إضافة جدول تحصين"),
        "vet_visit.create": _l("تسجيل زيارة بيطرية"),
        "warehouse.transfer": _l("تحويل بين مستودعين"),
        "mating.create": _l("تسجيل تقريع"),
    }

    AUDIT_ENTITY_LABELS_AR = {
        "Animal": _l("حيوان"), "Barn": _l("حظيرة"), "Task": _l("مهمة"),
        "Report": _l("بلاغ"), "Disease": _l("حالة مرضية"), "VetVisit": _l("زيارة بيطرية"),
        "Vaccination": _l("تحصين"), "Finance": _l("حركة مالية"), "User": _l("مستخدم"),
        "Role": _l("مسمّى وظيفي"), "Mating": _l("تقريع"), "Pregnancy": _l("حمل"),
        "AnimalBatch": _l("دفعة حيوانات"), "SalesLot": _l("دفعة بيع"),
        "FeedRation": _l("وصفة علف"), "Pharmacy": _l("دواء"), "TreatmentProtocol": _l("بروتوكول علاج"),
        "OstrichEgg": _l("بيضة نعام"), "ServiceToggle": _l("خدمة"), "EmergencySymptom": _l("عرض طوارئ"),
        "DiseaseSymptomLink": _l("ربط مرض-عرض"), "DailyTaskTemplate": _l("قالب مهمة يومية"),
        "VaccinationSchedule": _l("جدول تحصين"), "Warehouse": _l("مستودع"),
    }

    @app.template_filter("ar_audit_action")
    def ar_audit_action(value):
        return AUDIT_ACTION_LABELS_AR.get(value, value)

    @app.template_filter("ar_audit_entity")
    def ar_audit_entity(value):
        return AUDIT_ENTITY_LABELS_AR.get(value, value)

    # تحويل حالة المهمة إلى إحدى 5 حالات شارة موحّدة (نظام تصميم
    # claude.ai/design، بند إضافي 76) — Task.status له أكثر من 5 قيمة
    # فعلية، فهذا تجميع بصري بس (fallback "pending" الأكثر حياداً)،
    # القيمة الفعلية المخزّنة ما تتغيّر. عُمِّم لكل قيم STATUS_LABELS_AR
    # (بند إضافي 80، إعادة استخدام المكوّنات) — مو مقصور على المهام بس،
    # عشان أي شاشة ثانية (بلاغات، أدوية، بروتوكولات...) تقدر تستخدم نفس
    # الشارة الموحّدة بدل تكرار منطق التلوين بكل قالب.
    STATUS_BADGE_STATE = {
        "pending": "pending", "suggested": "pending", "postponed": "pending",
        "executed_pending_review": "pending", "new": "pending", "unpaid": "pending",
        "in_progress": "active", "active": "active", "eligible": "active",
        "done": "completed", "completed": "completed", "paid": "completed",
        "closed": "completed", "sold": "completed", "confirmed": "completed",
        "failed": "overdue", "out_of_order": "overdue",
        "cancelled": "cancelled", "deleted_pending_review": "cancelled", "deleted": "cancelled",
        "inactive": "cancelled", "dead": "cancelled", "not_eligible": "cancelled",
    }

    @app.template_filter("status_badge_state")
    def status_badge_state(value):
        return STATUS_BADGE_STATE.get(value, "pending")

    @app.template_filter("task_badge_state")
    def task_badge_state(value):
        return STATUS_BADGE_STATE.get(value, "pending")

    @app.template_filter("from_json")
    def from_json(value):
        # لتفكيك رسائل flash بصيغة JSON — تنبيهات Toast السياقية (بند
        # إضافي 230، app/core/toast_service.py).
        import json
        return json.loads(value)

    @app.template_filter("chat_format")
    def chat_format(value):
        # المستخدم اشتكى إن ردود المساعد الذكي أحياناً تطلع فيها **نجوم**
        # حرفية بدل تنسيق عريض — رغم تعليمات النظام لنماذج الذكاء
        # الاصطناعي بعدم استخدام ماركداون، النماذج أحياناً تخالف
        # التعليمة. هذا الفلتر طبقة حماية إضافية على مستوى العرض: يهرّب
        # الـHTML أولاً (أمان)، ثم يحوّل **نص** لعريض حقيقي بدل تركه نجوم.
        import re
        from markupsafe import Markup, escape
        if not value:
            return Markup("")
        escaped = str(escape(value))
        formatted = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        return Markup(formatted)

    # بند إصلاح — بلاغ مستخدم بصورة شاشة: ضغط "الإعدادات" بحساب الدكتور
    # (ما عنده صلاحية settings.manage افتراضياً — تصرف صحيح ومتعمَّد) طلعت
    # له صفحة بيضا بنص إنجليزي خام من Flask ("Forbidden... read-protected")
    # بدل رسالة عربية مفهومة توضّح السبب. صفحات 403/404 عربية بنفس هوية
    # النظام البصرية، بدون أي تغيير بمنطق الصلاحيات نفسه — القيد يبقى
    # صحيحاً، بس الرسالة تصير مفهومة بدل خطأ تقني خام يخوّف المستخدم.
    @app.errorhandler(403)
    def forbidden_error(e):
        return render_template(
            "error_page.html", icon="🚫",
            title=_l("ما تملك صلاحية الوصول لهذي الشاشة"),
            message=_l("هذي الشاشة محجوبة عن دورك الوظيفي الحالي — لو تحتاجها فعلياً، اطلب من صاحب الحلال يضيف الصلاحية المناسبة من (الإعدادات ← الأدوار والصلاحيات)."),
        ), 403

    @app.errorhandler(404)
    def not_found_error(e):
        return render_template(
            "error_page.html", icon="🔍",
            title=_l("الصفحة غير موجودة"),
            message=_l("الرابط اللي فتحته غير صحيح أو الصفحة انحذفت — تأكد من الرابط أو ارجع للرئيسية."),
        ), 404

    @app.route("/_healthz")
    def health():
        # فحص تقني بسيط لتشغيل السيرفر - غير مرتبط بوحدة الصحة البيطرية
        # (app/health/) عمداً لتفادي تضارب الأسماء بين الاثنين.
        return {"status": "ok"}

    @app.route("/uploads/<path:subpath>")
    def uploaded_file(subpath):
        # بند إضافي 77 — يقدّم الملفات المرفوعة من UPLOAD_DIR القابل
        # للتوجيه (بدل الاعتماد على static/ دايماً)، عشان لو انضبط على
        # قرص دائم، الروابط المولَّدة حديثاً (/uploads/...) تشتغل بغض
        # النظر عن مكان التخزين الفعلي. نفس مستوى الحماية القديم بالضبط
        # (بدون تسجيل دخول — نفس سلوك static/ من الأساس، الحماية الوحيدة
        # كانت وما زالت اسم ملف عشوائي UUID غير قابل للتخمين).
        return send_from_directory(app.config["UPLOAD_DIR"], subpath)

    @app.route("/telegram/webhook", methods=["POST"])
    @csrf.exempt
    def telegram_webhook():
        # المرحلة أ من بند إضافي 160: أوامر تيليجرام تفاعلية — تيليجرام
        # يبعث نبضة POST هنا لكل رسالة يوصل البوت. `secret_token` (مشتق
        # من التوكن نفسه، بدون متغير بيئة إضافي) يتأكد إن النبضة من
        # تيليجرام فعلاً، مو من أي طرف ثالث يعرف الرابط.
        from app.core import telegram_service
        expected = telegram_service.webhook_secret()
        got = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not expected or got != expected:
            abort(403)
        from app.core import telegram_commands_service
        try:
            telegram_commands_service.handle_update(request.get_json(silent=True) or {})
        except Exception as e:
            app.logger.warning("telegram_webhook failed: %s", e)
        return {"ok": True}

    if not app.config.get("TESTING"):
        external_url = os.environ.get("RENDER_EXTERNAL_URL")
        if external_url:
            try:
                from app.core import telegram_service
                telegram_service.set_webhook(external_url.rstrip("/") + "/telegram/webhook")
            except Exception as e:
                app.logger.warning("telegram set_webhook failed: %s", e)

    @app.route("/sw.js")
    def service_worker():
        # لازم يُقدَّم من جذر الموقع (/sw.js) مو من /static/sw.js — نطاق
        # الـService Worker الافتراضي يقتصر على المسار اللي يُقدَّم منه،
        # وشاشات العامل (بند 27) تحت / و/team/ محتاجة يتحكم فيها كلها.
        response = send_from_directory(os.path.join(app.static_folder), "sw.js", mimetype="application/javascript")
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        return response

    return app
