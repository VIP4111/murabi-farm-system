"""بند إضافي 276 — طلبك الصريح بعد صورة الشاشة (مقص أظافر حيونات، رصيد
صفر، ما تعرف مين أخذها): (1) كل صرف لازم يسجّل مين استلمه، (2) خيار
حالة القطعة (سليمة/تحتاج صيانة) إلزامي وقت التسليم ووقت الاستلام —
"علشان اعرف اتخربت عند مين ومين اخر شخص استعمل المعدة"، (3) تنبيه
لصاحب الحلال لو معدة تحتاج صيانة."""
from app.extensions import db
from app.models import Equipment, EquipmentMovement
from app.equipment import equipment_service as svc
from app.core import alerts_service
from factories import make_equipment


def test_out_movement_without_recipient_route_rejected(app, logged_in_client):
    item = make_equipment(available_qty=5)
    page = logged_in_client.get(f"/equipment/items/{item.id}/movement")
    csrf = page.data.decode().split('name="csrf_token" value="')[1].split('"')[0]
    resp = logged_in_client.post(f"/equipment/items/{item.id}/movement", data={
        "csrf_token": csrf, "movement_type": "out", "quantity": "1",
    })
    assert resp.status_code == 302
    db.session.refresh(item)
    assert item.available_qty == 5  # ما انسحب شي، الحركة انرفضت


def test_condition_needs_maintenance_at_handout_flags_item(app, owner):
    item = make_equipment(available_qty=5)
    svc.record_movement(item=item, movement_type="out", quantity=1,
                         borrowed_by_id=owner.id, condition_at_handout="needs_maintenance")
    assert item.needs_maintenance is True


def test_condition_needs_maintenance_at_return_flags_item(app, owner):
    item = make_equipment(available_qty=5)
    mv = svc.record_movement(item=item, movement_type="out", quantity=1,
                              borrowed_by_id=owner.id, condition_at_handout="good")
    assert item.needs_maintenance is False
    svc.return_item(mv, condition_at_return="needs_maintenance")
    assert item.needs_maintenance is True
    assert mv.condition_at_return == "needs_maintenance"


def test_good_condition_roundtrip_does_not_flag(app, owner):
    item = make_equipment(available_qty=5)
    mv = svc.record_movement(item=item, movement_type="out", quantity=1,
                              borrowed_by_id=owner.id, condition_at_handout="good")
    svc.return_item(mv, condition_at_return="good")
    assert item.needs_maintenance is False


def test_no_return_expected_excluded_from_outstanding_borrows(app, owner):
    item = make_equipment(available_qty=5)
    svc.record_movement(item=item, movement_type="out", quantity=1,
                         borrowed_by_id=owner.id, no_return_expected=True)
    assert svc.outstanding_borrows(item) == []


def test_equipment_needs_maintenance_alert_shows_last_user(app, owner):
    item = make_equipment(name="مقص أظافر اختبار", available_qty=5)
    mv = svc.record_movement(item=item, movement_type="out", quantity=1,
                              borrowed_by_id=owner.id, condition_at_handout="good")
    svc.return_item(mv, condition_at_return="needs_maintenance")
    alerts = alerts_service.get_alerts()
    matching = [a for a in alerts if a["category"] == "معدة تحتاج صيانة"]
    assert len(matching) == 1
    assert "مقص أظافر اختبار" in matching[0]["label"]
    assert owner.name in matching[0]["detail"]


def test_clearing_needs_maintenance_removes_alert(app, owner):
    item = make_equipment(available_qty=5)
    mv = svc.record_movement(item=item, movement_type="out", quantity=1,
                              borrowed_by_id=owner.id, condition_at_handout="needs_maintenance")
    assert item.needs_maintenance is True
    item.needs_maintenance = False
    db.session.commit()
    alerts = alerts_service.get_alerts()
    assert not any(a["category"] == "معدة تحتاج صيانة" for a in alerts)


def test_items_list_shows_current_holder(app, logged_in_client, owner):
    item = make_equipment(name="فأس اختبار قائمة", available_qty=5)
    svc.record_movement(item=item, movement_type="out", quantity=1, borrowed_by_id=owner.id)
    resp = logged_in_client.get("/equipment/items")
    body = resp.data.decode()
    assert "فأس اختبار قائمة" in body
    assert owner.name in body


def test_movement_return_route_accepts_condition(app, logged_in_client, owner):
    item = make_equipment(available_qty=5)
    mv = svc.record_movement(item=item, movement_type="out", quantity=1, borrowed_by_id=owner.id)
    resp = logged_in_client.post(f"/equipment/movements/{mv.id}/return",
                                  data={"condition_at_return": "needs_maintenance"})
    assert resp.status_code == 302
    db.session.refresh(item)
    assert item.needs_maintenance is True
