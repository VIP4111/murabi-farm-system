"""ملخص يومي موحّد بتيليجرام (بند إضافي 238) — بند 4 من خطة الـ4 نقاط
الواقعية بعد مراجعة مقترح "التحويل شبه الآلي". قبل هذا، الملخص اليومي
كان موجود بصيغة بريد بس (بند 160، المرحلة ج) — إشعارات تيليجرام كانت
كلها لحظية متفرقة لكل حدث على حدة (توزيع مهمة، بلاغ، نقص مخزون...)،
بدون رسالة واحدة تجمع صورة اليوم كاملة.

نفس فلسفة `daily_email_report_service.py` بالضبط — يعيد استخدام نفس
دالة بناء المحتوى (`build_report_email`) بدل تكرار منطق التجميع،
ويعتمد حارس منفصل (`last_daily_telegram_report_sent`) عشان فشل قناة
وحدة (بريد أو تيليجرام) ما يوقف الثانية."""
from datetime import date

from flask_babel import gettext as _

from app.extensions import db
from app.core import telegram_service


def send_daily_report_now() -> int:
    """يبعث الملخص الآن لكل مستخدم فعّال عنده Chat ID مسجَّل وصلاحية
    `reports.manage` (نفس نطاق تقرير البريد بالضبط) — يرجّع عدد
    الرسائل اللي نجح إرسالها فعلياً.

    **بند إضافي (2026-08-30)** — نفس إصلاح تقرير البريد بالضبط: نبني
    نسخة منفصلة (نص + أزرار) لكل لغة موجودة فعلاً بين المستلمين
    (`force_locale`)، مو نسخة عربية واحدة للجميع."""
    from flask_babel import force_locale
    from app.models import User
    from app.core.daily_email_report_service import build_report_email, gather_report_data

    recipients = [
        u for u in User.query.filter(User.telegram_chat_id.isnot(None), User.is_active_account.is_(True)).all()
        if u.has_permission("reports.manage")
    ]
    sent = 0
    for lang in {u.language or "ar" for u in recipients}:
        with force_locale(lang):
            # بند إضافي 303 — `build_report_email` صارت ترجع (عنوان،
            # نص، HTML)؛ تيليجرام يستخدم نسخة النص العادي بس.
            subject, body, _html = build_report_email()
            text = f"{subject}\n\n{body}"

            # بند إضافي 304 — أزرار تفاعلية حقيقية تحت الرسالة. أزرار
            # رابط مباشر (URL) — تيليجرام يرفض أزرار بدون رابط https
            # كامل، فلو `RENDER_EXTERNAL_URL` غير مضبوط (تطوير محلي)
            # نتجاهل الأزرار تماماً بدل ما نبعث رسالة بأزرار مكسورة.
            reply_markup = None
            d = gather_report_data()
            if d["base_url"]:
                abs_fn = d["abs"]
                reply_markup = telegram_service.inline_keyboard([
                    (_("🚨 عرض التنبيهات (%(n)s)", n=len(d['alerts'])), abs_fn("/alerts")),
                    (_("📋 مراجعة المهام (%(n)s)", n=d['tasks']['total']), abs_fn("/team/tasks")),
                    (_("💬 فتح المساعد الذكي"), abs_fn("/assistant/")),
                ])

        for user in recipients:
            if (user.language or "ar") == lang and telegram_service.notify_user(user, text, reply_markup=reply_markup):
                sent += 1
    return sent


def generate_daily_telegram_report_if_needed() -> None:
    from app.models import FarmSettings
    today = date.today()
    settings = FarmSettings.get()
    if settings.last_daily_telegram_report_sent == today:
        return
    send_daily_report_now()
    settings.last_daily_telegram_report_sent = today
    db.session.commit()
