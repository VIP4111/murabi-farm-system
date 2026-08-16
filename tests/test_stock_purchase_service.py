"""بند إضافي 203 — طلبك: زر "شراء" موحّد داخل "مكوّنات العلف" و"المعدات"
يزيد المخزون ويسجّل العملية المالية بضغطة وحدة، بدل الدخول من "حركة
المخزون" و"المالية ← عملية جديدة" كل مرة لحالها."""
from datetime import date

from app.extensions import db
from app.models import Role, User, Feed, Equipment, Finance, FeedMovement, EquipmentMovement


def _make_owner(phone="0599999160"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك اختبار الشراء الموحّد", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_feed_purchase_increases_stock_and_creates_finance_entry(app, client):
    owner = _make_owner()
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    feed = Feed(name="شعير اختبار الشراء الموحّد", unit="كجم", available_qty=10, status="active")
    db.session.add(feed)
    db.session.commit()

    client.post("/feed/purchase", data={
        "feed_id": feed.id, "date": "2026-08-16", "quantity": "50", "unit_price": "3.5",
    })

    db.session.refresh(feed)
    assert feed.available_qty == 60
    assert feed.unit_price == 3.5

    mv = FeedMovement.query.filter_by(feed_id=feed.id).first()
    assert mv is not None
    assert mv.movement_type == "in"
    assert mv.quantity == 50

    fin = Finance.query.filter_by(item="شعير اختبار الشراء الموحّد").first()
    assert fin is not None
    assert fin.operation_type == "purchase"
    assert fin.category == "أعلاف"
    assert fin.amount == 175.0


def test_equipment_purchase_increases_stock_and_creates_finance_entry(app, client):
    owner = _make_owner(phone="0599999161")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    item = Equipment(name="مقص اختبار الشراء الموحّد", unit="قطعة", available_qty=2, status="active")
    db.session.add(item)
    db.session.commit()

    client.post("/equipment/purchase", data={
        "equipment_id": item.id, "date": "2026-08-16", "quantity": "3", "unit_price": "40",
    })

    db.session.refresh(item)
    assert item.available_qty == 5
    assert item.unit_price == 40

    mv = EquipmentMovement.query.filter_by(equipment_id=item.id).first()
    assert mv is not None
    assert mv.movement_type == "in"

    fin = Finance.query.filter_by(item="مقص اختبار الشراء الموحّد").first()
    assert fin is not None
    assert fin.operation_type == "purchase"
    assert fin.category == "معدات"
    assert fin.amount == 120.0


def test_feed_purchase_requires_finance_permission(app, client):
    """صلاحية إدارة العلف وحدها ما تكفي — الشراء ينشئ عملية مالية فعلية."""
    role = Role.query.filter_by(name="worker").first()
    if role is None:
        return
    user = User(name="عامل بلا صلاحية مالية", phone="0599999162", role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    client.post("/login", data={"phone": user.phone, "password": "test1234"})

    feed = Feed(name="علف بلا صلاحية", unit="كجم", available_qty=10, status="active")
    db.session.add(feed)
    db.session.commit()

    resp = client.post("/feed/purchase", data={
        "feed_id": feed.id, "date": "2026-08-16", "quantity": "5", "unit_price": "2",
    }, follow_redirects=True)
    db.session.refresh(feed)
    assert feed.available_qty == 10
