"""بند إضافي (2026-08-31) — فجوة "تعدد المستلمين بلغات مختلفة": أي
إشعار فوري (تيليجرام/بريد) يُبنى **مرة واحدة** بلغة الفاعل الحالي
(مُقدِّم البلاغ، الدكتور اللي وزّع مهمة...) ويُرسل حرفياً لكل مستلم —
نفس فجوة التقرير اليومي بالضبط، لقيت 7 مواقع إضافية بعد submit_report
الأصلي: outbreak_service, stock_alert_service, scheduled_care_notify_service,
health_service (طوارئ), core/routes (ولادة، بيع), repro/routes (تجاوز
قرابة), finance/routes (شذوذ مالي). الحل نفسه بكل مكان: `force_locale`
لكل لغة موجودة فعلياً بين المستلمين."""
from unittest.mock import patch

from app.extensions import db
from app.models import Role, User
from app.team import report_service
from factories import make_animal


def _make_user(name, phone, lang, permission_role="owner", telegram_chat_id=None):
    role = Role.query.filter_by(name=permission_role).first()
    user = User(name=name, phone=phone, role_id=role.id, language=lang, telegram_chat_id=telegram_chat_id)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_submit_report_notifies_each_recipient_in_their_own_language(app):
    reporter = _make_user("Reporter", "0599999300", "ar", permission_role="worker")
    ar_manager = _make_user("AR Manager", "0599999301", "ar", telegram_chat_id="301")
    en_manager = _make_user("EN Manager", "0599999302", "en", telegram_chat_id="302")

    sent = {}

    def _fake_notify(user, text, reply_markup=None):
        sent[user.id] = text
        return True

    with patch("app.core.telegram_service.notify_user", side_effect=_fake_notify):
        report_service.submit_report(reporter=reporter, description="بلاغ اختبار")

    assert "بلاغ جديد" in sent[ar_manager.id]
    assert "New report" in sent[en_manager.id]
    assert "بلاغ جديد" not in sent[en_manager.id]


def test_stock_shortage_notifies_each_recipient_in_their_own_language(app):
    from app.core import stock_alert_service
    from factories import make_pharmacy

    ar_doctor = _make_user("AR Doctor", "0599999303", "ar", permission_role="doctor", telegram_chat_id="303")
    en_doctor = _make_user("EN Doctor", "0599999304", "en", permission_role="doctor", telegram_chat_id="304")
    pharmacy = make_pharmacy(name="دواء اختبار نقص", available_qty=1)
    pharmacy.min_stock_qty = 5
    db.session.commit()

    sent = {}

    def _fake_notify(user, text, reply_markup=None):
        sent[user.id] = text
        return True

    with patch("app.core.telegram_service.notify_user", side_effect=_fake_notify):
        stock_alert_service.check_pharmacy_stock(pharmacy)

    assert "نقص مخزون" in sent[ar_doctor.id]
    assert "stock shortage" in sent[en_doctor.id]
