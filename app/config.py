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
