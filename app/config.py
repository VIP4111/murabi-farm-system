import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///farm_system.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # حد أقصى لحجم أي طلب (يشمل رفع الملاحظة الصوتية بنموذج البلاغ —
    # بند 28) — أول رفع ملفات فعلي بالمشروع، هامش آمن فوق حد الصوت
    # (8MB بـ`report_service.MAX_AUDIO_BYTES`) لبقية حقول الفورم.
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    OWNER_NAME = os.environ.get("OWNER_NAME", "صاحب الحلال")
    OWNER_PHONE = os.environ.get("OWNER_PHONE", "0500000000")
    OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "change-me-123")

    # اللغات المدعومة بواجهة العامل (قابلة للتوسعة لاحقاً من الإعدادات)
    SUPPORTED_LANGUAGES = ["ar", "en", "am", "hi"]
