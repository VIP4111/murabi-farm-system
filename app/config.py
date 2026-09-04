import os


def _normalize_database_url(url: str) -> str:
    """Render/Heroku يعطون رابط Postgres بصيغة قديمة `postgres://` —
    SQLAlchemy 1.4+ يرفضها ويطلب `postgresql://` صراحة. بدون هذا
    التطبيع، ربط قاعدة بيانات حقيقية يفشل بخطأ غامض عند أول طلب،
    بدل ما يشتغل مباشرة (بند إضافي 77، 2026-08-01)."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(
        os.environ.get("DATABASE_URL", "sqlite:///farm_system.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # إصلاح — بلاغ مستخدم حقيقي: "بعد ما حولنا لـNeon صارت لخبطة وضعف
    # بالسرعة". السبب المرجَّح: Neon (زي أي قاعدة بيانات serverless
    # مجانية) توقف الاتصال تلقائياً بعد فترة خمول قصيرة لتوفير الموارد.
    # بدون هذي الإعدادات، أول طلب بعد فترة هدوء كان يحاول يستخدم اتصال
    # قديم "ميت" من المجمّع (pool) — يفشل بخطأ غامض أو يتعلّق لثوانٍ قبل
    # ما SQLAlchemy يكتشف المشكلة ويعيد المحاولة، فيبان للمستخدم كبطء
    # ولخبطة عشوائية. الحل قياسي لأي قاعدة serverless (نفس التوصية
    # الرسمية من Neon وHeroku Postgres): `pool_pre_ping` يختبر الاتصال
    # بأمر خفيف قبل أي استخدام فعلي ويستبدله تلقائياً لو ميت (شفّاف
    # تماماً للمستخدم، بدون أي خطأ يوصله)، و`pool_recycle` يجدّد أي
    # اتصال قبل ما يوصل عمره لحد يقارب مهلة Neon نفسها. sqlite محلياً
    # ما تحتاج أي شي من هذا (اتصال بملف، صفر شبكة) — الإعدادات تُطبَّق
    # فقط لو قاعدة البيانات فعلياً عن بعد (postgres).
    if not SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 280,
        }

    # حماية كوكي الجلسة (بند إضافي 87، 2026-08-02، نقطة 5 من التحليل
    # الثاني) — قبل هذا ما كان فيه أي إعداد صريح، يعني كوكي الدخول ممكن
    # تُرسَل حتى بوصلة HTTP غير مشفّرة لو حد اعترض حركة الشبكة. نفعّلها
    # تلقائياً على Render (يضبط RENDER=true بنفسه، والموقع دايماً HTTPS
    # هناك)، وتبقى معطّلة محلياً/بالمعاينة عشان ما تكسر تسجيل الدخول على
    # http://localhost أثناء التطوير والاختبار.
    _on_render = os.environ.get("RENDER", "").lower() == "true"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true" if _on_render else "false").lower() == "true"
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # مجلد تخزين الملفات المرفوعة (صور بلاغات، ملاحظات صوتية، فواتير) —
    # بند إضافي 77، 2026-08-01. افتراضياً جوّا static/ (نفس السلوك
    # القديم تماماً، صفر تغيير بدون إعداد إضافي). لو فيه قرص دائم
    # (Persistent Disk) على المنصة، وجّه UPLOAD_DIR لمساره — يحمي
    # الملفات من الضياع عند كل إعادة نشر، بدون أي تعديل كود إضافي.
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR")  # None = يُحسم لاحقاً من static_folder

    # حد أقصى لحجم أي طلب (يشمل رفع الملاحظة الصوتية بنموذج البلاغ —
    # بند 28) — أول رفع ملفات فعلي بالمشروع، هامش آمن فوق حد الصوت
    # (8MB بـ`report_service.MAX_AUDIO_BYTES`) لبقية حقول الفورم.
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    OWNER_NAME = os.environ.get("OWNER_NAME", "صاحب الحلال")
    OWNER_PHONE = os.environ.get("OWNER_PHONE", "0500000000")
    OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "change-me-123")

    # اللغات المدعومة بواجهة العامل (قابلة للتوسعة لاحقاً من الإعدادات)
    SUPPORTED_LANGUAGES = ["ar", "en", "am", "hi"]
