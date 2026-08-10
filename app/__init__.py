import os
from flask import Flask, send_from_directory, request, abort
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
    }

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
    }

    @app.template_filter("ar_task_type")
    def ar_task_type(value):
        return TASK_TYPE_LABELS_AR.get(value, value)

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
