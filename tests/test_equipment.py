"""بند إضافي 108 — مستودع المعدات، نفس بنية العلف/الصيدلية بالضبط
(رصيد + حركات وارد/صادر). ما كان له أي جدول أو شاشة بالنظام قبل هذا."""
from app.extensions import db
from app.models import Equipment, EquipmentMovement
from app.equipment import equipment_service as svc
from factories import make_equipment, make_barn


def test_record_movement_in_increases_stock(app):
    item = make_equipment(available_qty=5)
    svc.record_movement(item=item, movement_type="in", quantity=10)
    assert item.available_qty == 15
    assert EquipmentMovement.query.filter_by(equipment_id=item.id, movement_type="in").count() == 1


def test_record_movement_out_decreases_stock(app):
    barn = make_barn()
    item = make_equipment(available_qty=20)
    svc.record_movement(item=item, movement_type="out", quantity=6, barn_id=barn.id)
    assert item.available_qty == 14


def test_record_movement_out_rejects_more_than_available(app):
    item = make_equipment(available_qty=3)
    try:
        svc.record_movement(item=item, movement_type="out", quantity=10)
        assert False, "expected ValueError"
    except ValueError:
        pass
    assert item.available_qty == 3


def test_consumption_stats_reflects_out_movements(app):
    item = make_equipment(available_qty=50)
    svc.record_movement(item=item, movement_type="out", quantity=5)
    stats = svc.consumption_stats(item)
    assert stats["consumed_day"] == 5
    assert stats["consumed_month"] == 5


def test_items_list_route(app, logged_in_client):
    make_equipment(name="مطرقة اختبار")
    resp = logged_in_client.get("/equipment/items")
    assert resp.status_code == 200
    assert "مطرقة اختبار" in resp.data.decode()


def test_checkout_records_borrower_and_deducts_stock(app, owner):
    item = make_equipment(available_qty=5)
    mv = svc.record_movement(item=item, movement_type="out", quantity=1, borrowed_by_id=owner.id)
    assert mv.borrowed_by_id == owner.id
    assert mv.returned_at is None
    assert item.available_qty == 4


def test_return_item_restores_stock_and_stamps_returned_at(app, owner):
    item = make_equipment(available_qty=5)
    mv = svc.record_movement(item=item, movement_type="out", quantity=1, borrowed_by_id=owner.id)
    svc.return_item(mv)
    assert mv.returned_at is not None
    assert item.available_qty == 5


def test_return_item_rejects_double_return(app, owner):
    item = make_equipment(available_qty=5)
    mv = svc.record_movement(item=item, movement_type="out", quantity=1, borrowed_by_id=owner.id)
    svc.return_item(mv)
    try:
        svc.return_item(mv)
        assert False, "expected ValueError"
    except ValueError:
        pass
    assert item.available_qty == 5  # ما زاد مرتين


def test_return_item_rejects_non_borrow_movement(app):
    item = make_equipment(available_qty=5)
    mv = svc.record_movement(item=item, movement_type="out", quantity=1)  # صرف نهائي، بدون استعارة
    try:
        svc.return_item(mv)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_outstanding_borrows_excludes_returned(app, owner):
    item = make_equipment(available_qty=5)
    mv1 = svc.record_movement(item=item, movement_type="out", quantity=1, borrowed_by_id=owner.id)
    svc.record_movement(item=item, movement_type="out", quantity=1, borrowed_by_id=owner.id)
    svc.return_item(mv1)
    outstanding = svc.outstanding_borrows(item)
    assert len(outstanding) == 1
    assert outstanding[0].id != mv1.id


def test_movement_return_route(app, logged_in_client, owner):
    item = make_equipment(available_qty=5)
    mv = svc.record_movement(item=item, movement_type="out", quantity=1, borrowed_by_id=owner.id)
    resp = logged_in_client.post(f"/equipment/movements/{mv.id}/return")
    assert resp.status_code == 302
    db.session.refresh(mv)
    assert mv.returned_at is not None


def test_family_view_shows_outstanding_borrow(app, logged_in_client, owner):
    item = make_equipment(name="مطرقة استعارة اختبار", available_qty=5)
    svc.record_movement(item=item, movement_type="out", quantity=1, borrowed_by_id=owner.id)
    resp = logged_in_client.get("/family-view")
    body = resp.data.decode()
    assert "مطرقة استعارة اختبار" in body
    assert "مستعارة حالياً" in body
    assert owner.name in body


def test_items_new_route_creates_item(app, logged_in_client):
    page = logged_in_client.get("/equipment/items/new")
    csrf = page.data.decode().split('name="csrf_token" value="')[1].split('"')[0]
    resp = logged_in_client.post("/equipment/items/new", data={
        "csrf_token": csrf, "name": "مقص اختبار", "available_qty": "3",
    })
    assert resp.status_code == 302
    assert Equipment.query.filter_by(name="مقص اختبار").first() is not None
