"""بند إضافي 208 — اختبارات مسار الجرد (فورم + سجل)، تكملة
tests/test_inventory_count_service.py اللي يغطي منطق الحساب مباشرة."""
from app.extensions import db
from app.models import Role, User, Feed, Finance


def _make_owner(phone="0599999210"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك اختبار مسار الجرد", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_count_form_shows_current_balance(app, client):
    owner = _make_owner()
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    feed = Feed(name="شعير اختبار مسار الجرد", unit="كجم", available_qty=40, unit_price=2.0, status="active")
    db.session.add(feed)
    db.session.commit()

    resp = client.get(f"/warehouses/item/feed/{feed.id}/count")
    body = resp.data.decode()
    assert "40" in body
    assert "الرصيد المحسوب بالنظام" in body


def test_submitting_deficit_count_updates_stock_and_appears_in_history(app, client):
    owner = _make_owner(phone="0599999211")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    feed = Feed(name="شعير اختبار مسار الجرد 2", unit="كجم", available_qty=40, unit_price=2.0, status="active")
    db.session.add(feed)
    db.session.commit()

    client.post(f"/warehouses/item/feed/{feed.id}/count", data={
        "count_date": "2026-08-17", "actual_qty": "30", "note": "جرد اختبار",
    })

    db.session.refresh(feed)
    assert feed.available_qty == 30
    assert Finance.query.filter_by(category="هالك", item=feed.name).count() == 1

    resp = client.get("/warehouses/inventory-counts")
    body = resp.data.decode()
    assert "شعير اختبار مسار الجرد 2" in body
    assert "جرد اختبار" in body
