"""مراجعة "أكواد الخلفية" (استكمال) — `stock_alert_service.check_
pharmacy_stock`/`check_feed_stock` تُستدعى بعد *كل* `deduct_stock()`
فعلي (كل توزيعة علف، كل جرعة دواء) — كانت بدون أي منع تكرار، عكس بقية
إشعارات النظام كلها. طالما الصنف تحت الحد الأدنى، كل استخدام جديد يبعث
إشعار تيليجرام جديد لنفس المشكلة بالضبط — عشرات الإشعارات المكرَّرة
خلال يوم أو يومين، لدرجة تخلي المستخدم يكتم إشعارات البوت كلها.

الإصلاح: `low_stock_alert_sent` على `Feed`/`Pharmacy` — إشعار واحد بس
طالما الوضع لسا نفسه، يُصفَّر تلقائياً عند أي تزويد فعلي (`add_stock`)
عشان لو رجع ينخفض تاني يُنبَّه من جديد."""
from unittest.mock import patch

from app.extensions import db
from app.core import stock_alert_service as svc
from factories import make_pharmacy, make_feed


def test_pharmacy_low_stock_alert_not_repeated_on_every_deduction(app, owner):
    owner.telegram_chat_id = "10"
    db.session.commit()
    pharmacy = make_pharmacy(available_qty=20)
    pharmacy.min_stock_qty = 10
    db.session.commit()

    with patch("app.core.telegram_service.notify_user") as mock_notify:
        pharmacy.deduct_stock(11)  # ينزل تحت الحد الأدنى (9 <= 10) — أول إشعار
        db.session.commit()
        svc.check_pharmacy_stock(pharmacy)
        pharmacy.deduct_stock(1)  # لسا تحت الحد الأدنى — ما يفترض يُعاد الإشعار
        db.session.commit()
        svc.check_pharmacy_stock(pharmacy)
        pharmacy.deduct_stock(1)  # نفس الشي مرة ثالثة
        db.session.commit()
        svc.check_pharmacy_stock(pharmacy)

    assert mock_notify.call_count == 1, "الإشعار تكرر رغم إن المشكلة لسا نفسها (لم تُحل)"


def test_pharmacy_low_stock_alert_resent_after_restock(app, owner):
    owner.telegram_chat_id = "11"
    db.session.commit()
    pharmacy = make_pharmacy(available_qty=5)
    pharmacy.min_stock_qty = 10
    db.session.commit()

    with patch("app.core.telegram_service.notify_user") as mock_notify:
        svc.check_pharmacy_stock(pharmacy)  # أول إشعار
        svc.check_pharmacy_stock(pharmacy)  # مكرَّر — يُتجاهل
        pharmacy.add_stock(50)  # تزويد فعلي — يصفّر العلم
        db.session.commit()
        pharmacy.deduct_stock(46)  # يرجع تحت الحد الأدنى (9 <= 10)
        db.session.commit()
        svc.check_pharmacy_stock(pharmacy)  # يُفترض إشعار جديد لأن الوضع "جديد"

    assert mock_notify.call_count == 2, "ما انبعث إشعار جديد بعد ما رجع المخزون ينخفض بعد تزويد فعلي"


def test_feed_low_stock_alert_not_repeated_on_every_deduction(app, owner):
    owner.telegram_chat_id = "12"
    db.session.commit()
    feed = make_feed(available_qty=100)
    feed.min_stock_qty = 30
    db.session.commit()

    with patch("app.core.telegram_service.notify_user") as mock_notify:
        feed.deduct_stock(75)  # 25 <= 30 — أول إشعار
        db.session.commit()
        svc.check_feed_stock(feed)
        feed.deduct_stock(5)  # لسا تحت الحد — ما يفترض يتكرر
        db.session.commit()
        svc.check_feed_stock(feed)

    assert mock_notify.call_count == 1, "إشعار نقص العلف تكرر رغم إن المشكلة لسا نفسها"
