"""تجميع كل إضافات Flask بمكان واحد، عشان نتفادى استيراد دائري بين الملفات."""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_babel import Babel
from flask_wtf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
babel = Babel()
# حماية CSRF (بند إضافي 93، 2026-08-02 — التحليل الثالث) — قبل هذا
# البند ما كان فيه أي رمز CSRF بأي فورم، والحماية الوحيدة كانت
# SESSION_COOKIE_SAMESITE=Lax (بند 87) اللي تخفف الخطر بس ما تلغيه.
# CSRFProtect يتحقق تلقائياً من كل POST/PUT/DELETE.
csrf = CSRFProtect()


def run_once_per_app(key: str, fn) -> None:
    """يشغّل `fn()` مرة وحدة بس لكل تطبيق Flask شغّال (علم على
    `current_app.extensions`، مو متغيّر عالمي بذاكرة العملية).

    بند إصلاح أداء — بلاغ مستخدم حقيقي: "ضعف بالتصفح غير سريع". السبب
    نمط تكرَّر بعدة مسارات (`animals_new`/`animals_edit`،
    `batches_new`، `team.report_form`، `health.pharmacy_new`/
    `pharmacy_edit`): كل واحد يستدعي دالة `seed_defaults()` مباشرة —
    كل واحدة عدة استعلامات idempotent-check تسلسلية للقاعدة (فحص "هل
    هذا الاسم موجود؟" لكل قيمة افتراضية على حدة) — رغم إنها عملياً ما
    تحتاج تضيف أي شي بعد أول مرة تشتغل فيها المزرعة. النتيجة: عدة رحلات
    ذهاب وإياب زايدة لقاعدة البيانات (Neon) على كل فتحة صفحة، تتراكم مع
    زيادة عدد "الشاشات المصابة" بنفس النمط.

    الحل: أول طلب بعد إقلاع كل تطبيق يسوي الفحص الحقيقي مرة وحدة، وأي
    طلب بعده لنفس التطبيق يتخطاه فوراً بدون أي استعلام. علم بمستوى
    التطبيق (مو العملية) عمداً — عشان كل اختبار آلي يبني تطبيق وقاعدة
    بيانات جديدين تماماً (`tests/conftest.py`)، فالعلم يتصفّر معه
    طبيعياً بدل ما يتسرّب بين الاختبارات لو كان متغيّراً عالمياً ثابتاً.
    و"ضبط المصنع" (`factory_reset_service.py`) يمسح هذي الأعلام صراحة
    بعد ما يمسح كل الجداول، عشان أول زيارة بعده تعيد تعبئة القوائم
    المرجعية الأساسية صح."""
    from flask import current_app
    flag_key = f"_run_once_{key}"
    if current_app.extensions.get(flag_key):
        return
    fn()
    current_app.extensions[flag_key] = True
