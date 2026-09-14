"""ملخص يومي موحّد بإشعار Push (بند إضافي، طلبك: "ملخص يومي واحد
بإشعار") — نفس فلسفة daily_telegram_report_service.py بالضبط: قناة
مستقلة بحارس زمني خاص (`last_daily_push_report_sent`) عشان فشل قناة
وحدة (بريد/تيليجرام/Push) ما يوقف بقية القنوات، وتعيد استخدام نفس
مصدر الأرقام (`gather_report_data`) بدل حساب مستقل قد يفترق لاحقاً
عن نسخ البريد/تيليجرام.

بخلاف تيليجرام (يرسل النص الكامل المفصَّل)، إشعار Push مساحته محدودة
جداً بشاشة القفل — نبني ملخصاً قصيراً بس (عدد مهام متأخرة/مستحقة،
تنبيهات عاجلة، بلاغات مفتوحة)، مو النص الطويل نفسه."""
from app.extensions import db
from app.core import push_service


def _build_digest_title_and_body() -> tuple[str, str]:
    """يبني عنوان ونص الملخص بلغة الترجمة الحالية (المستدعي مسؤول عن
    فتح `force_locale` المناسب قبل الاستدعاء) — مستخرَجة هنا عشان
    `send_daily_report_now()` (حلقة كل اللغات) و`send_test_digest_to()`
    (بند إضافي، زر "إرسال ملخص تجريبي" بالإعدادات) يبنيان نفس المحتوى
    بالضبط بدون تكرار المنطق."""
    from flask_babel import gettext as _
    from app.core.daily_email_report_service import gather_report_data

    title = _("📊 ملخص مراح بو علي اليومي")
    d = gather_report_data()
    parts = []
    if d["tasks"]["overdue"]:
        parts.append(_("%(n)s مهمة متأخرة", n=d["tasks"]["overdue"]))
    if d["tasks"]["due_today"]:
        parts.append(_("%(n)s مستحقة اليوم", n=d["tasks"]["due_today"]))
    if d["urgent_alerts"]:
        parts.append(_("%(n)s تنبيه عاجل", n=len(d["urgent_alerts"])))
    if d["open_reports"]:
        parts.append(_("%(n)s بلاغ مفتوح", n=d["open_reports"]))
    body = "، ".join(parts) if parts else _("ولا شي يحتاج تصرّف عاجل اليوم 🎉")
    return title, body


def send_test_digest_to(user) -> bool:
    """زر "إرسال ملخص تجريبي الآن" بشاشة الإعدادات (بند إضافي، طلبك:
    "نعم ظيفها" بعد اقتراح إضافة اختبار يدوي) — يرسل نفس محتوى الملخص
    اليومي فوراً لهذا المستخدم بالذات، بدون انتظار دورة اليوم التالي
    وبدون فحص صلاحية `reports.manage` (اختبار تقني بحت، مو الإرسال
    التلقائي الحقيقي — الزر نفسه محمي بصلاحية الإعدادات أصلاً)."""
    from flask_babel import force_locale

    with force_locale(user.language or "ar"):
        title, body = _build_digest_title_and_body()
    return push_service.notify_user(user, title, body, url="/today")


def send_daily_report_now() -> int:
    """يبعث الملخص الآن لكل مستخدم فعّال عنده اشتراك Push مسجَّل
    وصلاحية `reports.manage` (نفس نطاق تقرير تيليجرام/البريد بالضبط)
    — يرجّع عدد الملخصات اللي نجح إرسالها فعلياً."""
    from flask_babel import force_locale
    from app.models import User, PushSubscription

    user_ids = {row[0] for row in db.session.query(PushSubscription.user_id).distinct().all()}
    if not user_ids:
        return 0
    recipients = [
        u for u in User.query.filter(User.id.in_(user_ids), User.is_active_account.is_(True)).all()
        if u.has_permission("reports.manage")
    ]
    if not recipients:
        return 0

    sent = 0
    for lang in {u.language or "ar" for u in recipients}:
        with force_locale(lang):
            title, body = _build_digest_title_and_body()
        for user in recipients:
            if (user.language or "ar") != lang:
                continue
            if push_service.notify_user(user, title, body, url="/today"):
                sent += 1
    return sent


def generate_daily_push_report_if_needed() -> None:
    from app.models import FarmSettings
    from app.extensions import farm_today

    today = farm_today()
    settings = FarmSettings.get()
    if settings.last_daily_push_report_sent == today:
        return
    if not push_service.vapid_configured():
        return
    send_daily_report_now()
    settings.last_daily_push_report_sent = today
    db.session.commit()
