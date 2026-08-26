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

from app.extensions import db
from app.core import telegram_service


def send_daily_report_now() -> int:
    """يبعث الملخص الآن لكل مستخدم فعّال عنده Chat ID مسجَّل وصلاحية
    `reports.manage` (نفس نطاق تقرير البريد بالضبط) — يرجّع عدد
    الرسائل اللي نجح إرسالها فعلياً."""
    from app.models import User
    from app.core.daily_email_report_service import build_report_email

    subject, body = build_report_email()
    text = f"{subject}\n\n{body}"
    sent = 0
    for user in User.query.filter(User.telegram_chat_id.isnot(None), User.is_active_account.is_(True)).all():
        if user.has_permission("reports.manage") and telegram_service.notify_user(user, text):
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
