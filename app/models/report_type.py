"""
قائمة "نوع البلاغ" القابلة للتوسّع (بند إضافي 150) — طلبك عبر ROADMAP.md:
"نظام خيارات موحّدة ومترجمة (قوائم أعراض/أنواع بلاغ قابلة للتوسيع من
المالك)". نفس فلسفة `UsageRoute`/`Breed`/`AnimalColor` بالضبط: جدول
صغير + زر "+ إضافة" (`medical_options.manage`) بدل الأربع خيارات
الثابتة اللي كانت مكتوبة مباشرة بقالب `report_form.html` (وكان زر
"+" الموجود أصلاً يضيف خيار بالمتصفح فقط بجافاسكربت — يختفي بأول
تحديث صفحة، بدون أي حفظ فعلي). `Report.report_type` يبقى نص حر
بالجدول (بدون FK) — هذا الجدول مرجع اقتراحات فقط.
"""
from datetime import datetime, timezone
from flask_babel import get_locale
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class ReportType(db.Model):
    __tablename__ = "report_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    # بند إصلاح (فحص عميق — طلبك: "تأكد من باقي الشاشات ما فيهم نفس
    # المشكلة" بعد بلاغ أعراض المساعد التشخيصي) — نفس الثغرة بالضبط:
    # "نوع البلاغ" (مرض/مشكلة/صيانة/أخرى) اللي يستخدمه كل عامل برفع
    # بلاغ، ما كان له أي ترجمة إطلاقاً. نفس نمط `DiseaseType`/`Breed`/
    # `AnimalColor`/`Symptom` بالضبط.
    name_en = db.Column(db.String(60), nullable=True)
    created_at = db.Column(db.DateTime, default=_now)

    def display_label(self) -> str:
        if self.name_en and str(get_locale()) != "ar":
            return self.name_en
        return self.name

    @classmethod
    def seed_defaults(cls) -> None:
        defaults = {"مرض": "Disease", "مشكلة": "Problem", "صيانة": "Maintenance", "أخرى": "Other"}
        for n, n_en in defaults.items():
            existing = cls.query.filter_by(name=n).first()
            if not existing:
                db.session.add(cls(name=n, name_en=n_en))
            elif not existing.name_en:
                existing.name_en = n_en
        db.session.commit()
