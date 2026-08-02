"""بند إضافي 96 — دفعات شراء الدواء بتاريخها الخاص (FIFO عند الخصم) +
تسجيل عملية شراء عبر الموقع. قبل هذا البند كل شراء جديد كان يُضاف صمتاً
لرقم Pharmacy.available_qty الإجمالي بدون أي أثر لتاريخ الشراء/الانتهاء."""
from datetime import date, timedelta

from app.extensions import db
from app.models import PharmacyBatch
from factories import make_pharmacy


def _add_batch(pharmacy, purchase_date, quantity, expiry_date=None):
    b = PharmacyBatch(pharmacy_id=pharmacy.id, purchase_date=purchase_date,
                       quantity=quantity, remaining_qty=quantity, expiry_date=expiry_date)
    db.session.add(b)
    db.session.commit()
    return b


def test_add_stock_increases_available_qty(app):
    p = make_pharmacy(available_qty=10)
    p.add_stock(5)
    assert p.available_qty == 15


def test_deduct_consumes_oldest_batch_first(app):
    p = make_pharmacy(available_qty=30)
    old = _add_batch(p, date.today() - timedelta(days=20), 10)
    new = _add_batch(p, date.today() - timedelta(days=5), 20)

    p.deduct_stock(12)
    db.session.commit()

    db.session.refresh(old)
    db.session.refresh(new)
    assert old.remaining_qty == 0  # استُنفدت أول (الأقدم)
    assert new.remaining_qty == 18  # انخصم منها الباقي (2) بس


def test_deduct_ignores_shortfall_when_batches_undertrack_available_qty(app):
    # دواء مخزونه أُضيف قبل استخدام الدفعات (تعديل يدوي قديم) — ما له
    # أي دفعة، بس available_qty يبقى المرجع الرسمي ولازم الخصم ينجح عادي.
    p = make_pharmacy(available_qty=10)
    p.deduct_stock(4)
    assert p.available_qty == 6


def test_purchase_form_creates_batch_and_updates_stock(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    p = make_pharmacy(available_qty=5)

    page = client.get(f"/health/pharmacy/{p.id}/purchase")
    csrf = page.data.decode().split('name="csrf_token" value="')[1].split('"')[0]

    resp = client.post(f"/health/pharmacy/{p.id}/purchase", data={
        "csrf_token": csrf, "purchase_date": str(date.today()),
        "quantity": "20", "expiry_date": str(date.today() + timedelta(days=100)),
        "unit_price": "3.5",
    })
    assert resp.status_code == 302

    db.session.refresh(p)
    assert p.available_qty == 25
    batches = PharmacyBatch.query.filter_by(pharmacy_id=p.id).all()
    assert len(batches) == 1
    assert batches[0].quantity == 20
    assert batches[0].remaining_qty == 20


def test_expiry_alert_uses_earliest_batch_date(app):
    from app.core.alerts_service import get_alerts
    p = make_pharmacy(name="دواء بدفعات", available_qty=20)
    _add_batch(p, date.today() - timedelta(days=10), 5, expiry_date=date.today() + timedelta(days=2))
    _add_batch(p, date.today() - timedelta(days=1), 15, expiry_date=date.today() + timedelta(days=200))

    alerts = get_alerts()
    matching = [a for a in alerts if "دواء بدفعات" in a["label"]]
    assert len(matching) == 1
    assert "بتاريخ" in matching[0]["detail"]


def test_expiry_alert_ignores_fully_consumed_batch(app):
    from app.core.alerts_service import get_alerts
    p = make_pharmacy(name="دواء دفعته خلصت", available_qty=0)
    b = _add_batch(p, date.today() - timedelta(days=10), 5, expiry_date=date.today() + timedelta(days=1))
    b.remaining_qty = 0
    db.session.commit()

    alerts = get_alerts()
    matching = [a for a in alerts if "دواء دفعته خلصت" in a["label"]]
    assert len(matching) == 0
