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
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class ReportType(db.Model):
    __tablename__ = "report_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    @classmethod
    def seed_defaults(cls) -> None:
        if cls.query.count() > 0:
            return
        for n in ("مرض", "مشكلة", "صيانة", "أخرى"):
            db.session.add(cls(name=n))
        db.session.commit()
