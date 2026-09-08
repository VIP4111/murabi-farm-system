from datetime import date as _date, datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class DailyReport(db.Model):
    """التقرير اليومي (بند إضافي، طلبك الصريح: "ابي كل عامل يدخل...
    ويكتب التقرير اليومي ويرسله... هو يرسله بلغته وأنا يوصلني بالعربي")
    — منفصل عمداً عن `Report` (البلاغات): هذا سجل يومي حر بدون دورة حياة
    (قبول/إغلاق)، مو تذكرة مشكلة مرتبطة بحيوان/حظيرة.

    ``author_text``/``author_lang`` = النص كما كتبه العضو بالضبط بلغته
    (نسخة مرجعية دائمة). ``arabic_text`` = ترجمة Gemini للعربي (أو نفس
    النص لو الكاتب أصلاً عربي، أو None لو الترجمة فشلت/Gemini غير مفعَّل
    — الشاشة تعرض النص الأصلي حينها بدل ما تخفي التقرير كامل).

    قيد فريد (``author_id`` + ``report_date``): تقرير واحد باليوم لكل
    عضو — إرسال ثانٍ بنفس اليوم يعدّل نفس السجل بدل ما يكرره (طلبك
    الضمني: شاشة بسيطة، مو أرشيف لمسودات متكررة)."""
    __tablename__ = "daily_reports"

    id = db.Column(db.Integer, primary_key=True)

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    author = db.relationship("User")

    report_date = db.Column(db.Date, default=_date.today, nullable=False)

    author_text = db.Column(db.Text, nullable=False)
    author_lang = db.Column(db.String(8), nullable=False)
    arabic_text = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        db.UniqueConstraint("author_id", "report_date", name="uq_daily_report_author_date"),
    )

    def display_text(self) -> str:
        return self.arabic_text or self.author_text
