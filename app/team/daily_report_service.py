"""التقرير اليومي (بند إضافي، طلبك الصريح: "ابي كل عامل يدخل... ويكتب
التقرير اليومي ويرسله... هو يرسله بلغته وأنا يوصلني بالعربي") — شاشة
مستقلة عن نظام "البلاغات" (Report): سجل يومي حر بدون دورة حياة، تقرير
واحد باليوم لكل عضو، يُترجَم تلقائياً للعربي عبر Gemini قبل ما يوصل
صاحب الحلال."""
from datetime import date

from app.extensions import db
from app.models import DailyReport, User, Role


def submit_or_update(*, author, text: str) -> DailyReport:
    """يُنشئ تقرير اليوم لو أول مرة، أو يعدّل نفس السجل لو العضو أرسل
    تقريراً ثانياً بنفس اليوم — تقرير واحد باليوم لكل عضو (قيد فريد
    بالموديل نفسه، هذا فحص تطبيقي إضافي يمنع محاولة `INSERT` مكرَّرة
    ترمي IntegrityError)."""
    lang = author.language or "ar"
    today = date.today()
    report = DailyReport.query.filter_by(author_id=author.id, report_date=today).first()

    arabic_text = text if lang == "ar" else _translate(text)

    if report:
        report.author_text = text
        report.author_lang = lang
        report.arabic_text = arabic_text
    else:
        report = DailyReport(
            author_id=author.id, report_date=today,
            author_text=text, author_lang=lang, arabic_text=arabic_text,
        )
        db.session.add(report)
    db.session.commit()

    _notify_owner(report)
    return report


def _translate(text: str) -> str | None:
    from app.assistant import llm_bridge
    return llm_bridge.translate_to_arabic(text)


def _notify_owner(report: DailyReport) -> None:
    """إشعار فوري لصاحب الحلال بس (طلبك: "يوصلني بالعربي") — نفس نمط
    `report_service.submit_report` (تيليجرام + بريد)، بدون احتياج
    `force_locale`/تعدد لغات هنا لأن المستلم صاحب الحلال حصراً، والنص
    عربي دائماً (`display_text()`)."""
    from app.core import telegram_service, email_service

    owners = User.query.join(Role).filter(
        User.is_active_account.is_(True), Role.name == "owner",
    ).all()
    from flask_babel import gettext as _
    text = _("📝 تقرير يومي من %(name)s", name=report.author.name) + f"\n{report.display_text()}"
    for owner in owners:
        if owner.id == report.author_id:
            continue
        if owner.telegram_chat_id:
            telegram_service.notify_user(owner, text)
        if owner.email:
            email_service.notify_user(owner, _("📝 تقرير يومي جديد"), text)
