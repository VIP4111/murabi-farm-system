"""فحص شامل سطر بسطر — ميزة المعدات.

مشاكل حقيقية اكتُشفت (نفس أنماط الأخطاء المتكرّرة بميزات سابقة هذي
الجلسة): حقول رقمية بلا فحص (سعر الوحدة، كمية الحركة، كمية الشراء،
قراءة المرافق)، N+1 على شاشة الأصناف، وتاريخ خام (UTC) بدل farm_today()
بحساب استحقاق الصيانة."""
from contextlib import contextmanager
from datetime import date

from sqlalchemy import event

from app.equipment import equipment_service as svc
from app.extensions import db
from app.models import Equipment
from app.models.asset import Asset


@contextmanager
def count_queries():
    counter = {"n": 0}

    def _on_execute(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    engine = db.session.get_bind()
    event.listen(engine, "before_cursor_execute", _on_execute)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _on_execute)


def test_items_new_rejects_negative_unit_price(logged_in_client):
    resp = logged_in_client.post("/equipment/items/new", data={
        "name": "معدة اختبار سعر سالب", "unit": "قطعة", "available_qty": "5",
        "min_stock_qty": "1", "unit_price": "-10",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Equipment.query.filter_by(name="معدة اختبار سعر سالب").first() is None


def test_items_movement_rejects_negative_quantity(logged_in_client):
    item = Equipment(name="معدة اختبار حركة", unit="قطعة", available_qty=10)
    db.session.add(item)
    db.session.commit()

    resp = logged_in_client.post(f"/equipment/items/{item.id}/movement", data={
        "movement_type": "out", "quantity": "-3",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(item)
    assert item.available_qty == 10, "كمية سالبة بحركة صادر ما يفترض تغيّر الرصيد إطلاقاً"


def test_assets_new_rejects_negative_interval_but_allows_zero(logged_in_client):
    resp = logged_in_client.post("/equipment/assets/new", data={
        "name": "أصل اختبار فترة سالبة", "maintenance_interval_days": "-5",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Asset.query.filter_by(name="أصل اختبار فترة سالبة").first() is None

    resp2 = logged_in_client.post("/equipment/assets/new", data={
        "name": "أصل اختبار بدون صيانة دورية", "maintenance_interval_days": "0",
    }, follow_redirects=True)
    assert resp2.status_code == 200
    saved = Asset.query.filter_by(name="أصل اختبار بدون صيانة دورية").first()
    assert saved is not None, "صفر قيمة صحيحة (بدون صيانة دورية مجدولة) ولازم تُحفَظ"
    assert saved.maintenance_interval_days == 0


def test_utilities_new_rejects_negative_quantity(logged_in_client):
    resp = logged_in_client.post("/equipment/utilities/new", data={
        "date": date.today().isoformat(), "utility_type": "electricity", "quantity": "-100",
    }, follow_redirects=True)
    assert resp.status_code == 200
    from app.models import UtilityReading
    assert UtilityReading.query.filter_by(quantity=-100).first() is None


def test_items_list_query_count_does_not_scale_with_item_count(logged_in_client):
    for i in range(3):
        db.session.add(Equipment(name=f"EQ-SMALL-{i}", unit="قطعة", available_qty=5))
    db.session.commit()
    with count_queries() as small:
        logged_in_client.get("/equipment/items")

    for i in range(20):
        db.session.add(Equipment(name=f"EQ-BIG-{i}", unit="قطعة", available_qty=5))
    db.session.commit()
    with count_queries() as big:
        logged_in_client.get("/equipment/items")

    growth = big["n"] - small["n"]
    assert growth <= 3, (
        f"عدد الاستعلامات نما {growth} مع إضافة 20 صنف — يدل على خلل N+1 "
        f"(صغير={small['n']}, كبير={big['n']})"
    )
