"""تجميع كل إضافات Flask بمكان واحد، عشان نتفادى استيراد دائري بين الملفات."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_babel import Babel
from flask_wtf import CSRFProtect

_RIYADH_TZ = ZoneInfo("Asia/Riyadh")


def farm_today() -> date:
    """بحث "منطق الأعمال" (2026-09-06) — طوال المشروع (163 موضع) كان
    `date.today()` يعتمد على توقيت السيرفر (UTC على Render)، بدون أي
    تحويل لتوقيت السعودية (UTC+3). النتيجة: كل ليلة، من 12:00 صباحاً
    لين 3:00 صباحاً بتوقيت السعودية، "تاريخ اليوم" بالسيرفر لسا اليوم
    اللي فات — يأثر على حساب أيام العزل/الحجر واستحقاق التنبيهات وتوليد
    المهام اليومية بهامش خطأ 3 ساعات كل ليلة.

    نقطة مركزية بس (قرارك الصريح: إصلاح محدود الأثر بدل استبدال شامل
    لكل الـ163 موضع دفعة وحدة) — استُخدمت بأهم نقطتين: الجدولة اليومية
    (`app/core/scheduler.py`) وحساب أيام الحجر الصحي (`cycle_engine.
    _gate_quarantine`). بقية `date.today()` بالمشروع بقيت كما هي عمداً."""
    return datetime.now(_RIYADH_TZ).date()


def farm_now_naive() -> datetime:
    """بند إصلاح (مراجعة "أكواد الخلفية") — نفس مشكلة `farm_today()`
    بالضبط لقيناها بمكان ثانٍ فاتنا وقتها: `daily_task_service.
    generate_daily_husbandry_tasks()` يستدعي `datetime.now()` (بدون
    منطقة زمنية — وقت السيرفر الخام، UTC على Render) عشان يقرر الساعة
    اللي تبدأ منها توليد مهام الغد مسبقاً (`EVENING_PREVIEW_HOUR = 18`،
    بند إضافي 72 بطلبك الصريح: "من 6 مساءً"). بتوقيت UTC، "الساعة 6"
    فعلياً تعني 9 مساءً بتوقيت السعودية — الميزة كانت تشتغل متأخرة
    3 ساعات كل ليلة عن الوقت اللي طلبته بالضبط. حتى `scheduler.py` (بعد
    إصلاح `farm_today()` للتاريخ) كان لسا يمرّر `datetime.now()` الخام
    لهذي الدالة بالذات — الإصلاح السابق ما غطاها.

    ترجع وقت الرياض *بدون* معلومة منطقة زمنية (naive) عمداً — عشان
    تبقى متوافقة مباشرة مع كود موجود يقارنها بـ`date`/يستخدم `.hour`
    بدون تعقيد تحويل إضافي، نفس نمط بقية الدوال بالمشروع."""
    return datetime.now(_RIYADH_TZ).replace(tzinfo=None)


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
babel = Babel()

# بند إصلاح (فحص "مقاسات الجوال") — بلوغة عن رسالة "Please log in to
# access this page." تطلع بالإنجليزي الخام لما تفتح رابطاً مباشرة بدون
# تسجيل دخول (نفس فئة مشكلة صفحات 403/404/500/413 القديمة اللي صارت
# عربية — هذي كانت الوحيدة المتبقية لأنها رسالة Flask-Login الافتراضية،
# مو نص كتبناه إحنا بالكود، فما ظهرت بالفحوصات السابقة اللي بحثت عن
# نصوصنا نحن). `_l` (lazy) لأن هذا يتنفَّذ وقت استيراد الملف، قبل ما
# يكون فيه سياق تطبيق فعّال لترجمة فورية.
from flask_babel import lazy_gettext as _l
login_manager.login_message = _l("سجّل دخولك أولاً عشان توصل لهذي الصفحة.")
login_manager.login_message_category = "warning"
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
