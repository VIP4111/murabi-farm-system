import os
from flask import Flask, send_from_directory
from flask_login import current_user
from app.config import Config
from app.extensions import db, migrate, login_manager, babel

# لغات RTL بين اللغات المدعومة (بند إضافي، 2026-07-23) — العربي فقط
# حالياً. الأمهرية والهندية بأبجديتيهما الأصليتين LTR رغم إنها لغات
# غير أوروبية، فما تحتاج قلب اتجاه.
RTL_LANGUAGES = {"ar"}


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    def select_locale():
        # لغة المستخدم المسجّل دخوله (User.language) هي المصدر الأساسي —
        # ما نعتمد على لغة المتصفح عشان نفس الحساب يشتغل بنفس اللغة على
        # أي جهاز. قبل تسجيل الدخول (شاشة /login) نستخدم اختيار الجلسة
        # المؤقت (زر اللغة بصفحة الدخول نفسها) لو موجود — بدونه عربي
        # افتراضياً، لأن العامل غير الناطق بالعربي يحتاج يقرأ حقول
        # الدخول نفسها بلغته قبل ما يوصل لأي شاشة بعد الدخول.
        from flask import session
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

    from app.cli import register_cli
    register_cli(app)

    STATUS_LABELS_AR = {
        "active": "نشط",
        "inactive": "غير نشط",
        "sold": "مباع",
        "dead": "نافق",
        "unpaid": "غير مدفوع",
        "paid": "مدفوع",
        "closed": "مغلق",
        "deleted": "محذوف/مؤرشف",
        "out_of_order": "ترتيب غير منتظم",
        "new": "جديد",
        "postponed": "مؤجّل",
        "executed_pending_review": "منفّذ — بانتظار المراجعة",
        "suggested": "مقترحة",
        "in_progress": "قيد التنفيذ",
        "done": "منجزة",
        "deleted_pending_review": "بانتظار مراجعة المالك",
        "completed": "مكتمل",
        "cancelled": "ملغى",
        "pending": "قيد الانتظار",
        "eligible": "مؤهّلة",
        "not_eligible": "غير مؤهّلة",
        "confirmed": "مؤكّدة",
        "failed": "فشلت",
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
        "custom": "مهمة عامة",
        "isolation_check": "فحص عزل",
        "doctor_review": "مراجعة الدكتور",
        "cord_antisepsis": "تعقيم السرّة",
        "selenium_dose": "جرعة سيلينيوم",
        "colostrum_check": "متابعة اللبأ/الرضاعة",
        "weighing": "وزن",
        "vaccination_due": "تحصين مستحق",
        "feed_switch": "تبديل علف",
        "abortion_sampling": "أخذ عينات إجهاض",
        "abortion_barn_monitor": "مراقبة حظيرة بعد إجهاض",
        "protocol_step": "خطوة بروتوكول علاج",
        "batch_spray": "رش وقائي (دفعة)",
        "batch_initial_vaccination": "تحصين مبدئي (دفعة)",
        "move_to_pregnant_barn": "نقل لحظيرة الحوامل",
        "batch_tagging_check": "فحص ترقيم (دفعة)",
        "batch_feed_link": "ربط علف (دفعة)",
        "daily_husbandry": "رعاية يومية",
        "late_pregnancy_care": "رعاية حمل متأخر",
        "planned_treatment": "علاج مخطَّط",
        "reweigh_followup": "متابعة إعادة وزن",
        "heat_feed_timing": "تعديل توقيت العلف (إجهاد حراري)",
        "heat_water_additive": "إضافة ماء (إجهاد حراري)",
        "heat_ventilation": "فحص تهوية (إجهاد حراري)",
        "heat_shade": "فحص تظليل (إجهاد حراري)",
        "shearing": "جزّ صوف",
    }

    @app.template_filter("ar_task_type")
    def ar_task_type(value):
        return TASK_TYPE_LABELS_AR.get(value, value)

    @app.route("/_healthz")
    def health():
        # فحص تقني بسيط لتشغيل السيرفر - غير مرتبط بوحدة الصحة البيطرية
        # (app/health/) عمداً لتفادي تضارب الأسماء بين الاثنين.
        return {"status": "ok"}

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
