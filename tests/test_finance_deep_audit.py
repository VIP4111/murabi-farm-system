"""فحص شامل سطر بسطر — ميزة المالية.

4 مشاكل حقيقية اكتُشفت:
1. monthly_cost_per_head كانت تستخدم date.today() الخام (UTC) بدل
   farm_today() — آخر 3 ساعات من كل يوم سعودي تختار "الشهر الحالي"
   الخطأ.
2. target_amount بإنشاء دفعة بيع كان يُحفَظ بلا أي فحص.
3. N+1 على عدّ عناصر كل دفعة بشاشة "دفعات البيع".
4. N+1 على "الرأس المرتبط" بتصدير كل السجلات المالية.
"""
from contextlib import contextmanager
from datetime import date

from sqlalchemy import event

from app.core import finance_report_service
from app.extensions import db
from app.models import Animal, Finance
from app.models.animal import AnimalSource


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


def test_monthly_cost_per_head_uses_farm_today_not_raw_utc_today(app, monkeypatch):
    """نحاكي لحظة UTC متأخرة تكون لسا اليوم السابق بتوقيت الرياض —
    farm_today() المزيَّفة تُرجع شهراً مختلفاً كلياً عن date.today()
    الحقيقي، ونتأكد إن النتيجة تعتمد على farm_today()."""
    fake_farm_date = date(2030, 6, 15)
    monkeypatch.setattr("app.extensions.farm_today", lambda: fake_farm_date)

    rows = finance_report_service.monthly_cost_per_head(months=1)
    assert rows[0]["year"] == 2030
    assert rows[0]["month"] == 6


def test_lots_new_rejects_negative_target_amount(logged_in_client):
    animal = Animal(animal_no="FIN-1", source=AnimalSource.PURCHASE, gender="ذكر",
                     species="sheep_goat", status="active", lifecycle_stage="source",
                     purchase_date=date.today())
    db.session.add(animal)
    db.session.commit()

    resp = logged_in_client.post("/finance/lots/new", data={
        "name": "دفعة اختبار", "target_amount": "-500", "animal_ids": [str(animal.id)],
    }, follow_redirects=True)
    assert resp.status_code == 200
    from app.models import SalesLot
    assert SalesLot.query.filter_by(name="دفعة اختبار").first() is None, \
        "ما يفترض تُحفَظ دفعة بمبلغ مستهدف سالب"


def test_lots_list_query_count_does_not_scale_with_lot_count(logged_in_client):
    from app.models import SalesLot, SalesLotItem

    def _make_lot(no, n_items):
        lot = SalesLot(name=f"دفعة {no}", created_by_id=1)
        db.session.add(lot)
        db.session.flush()
        for i in range(n_items):
            animal = Animal(animal_no=f"FL-{no}-{i}", source=AnimalSource.PURCHASE, gender="ذكر",
                             species="sheep_goat", status="active", lifecycle_stage="source",
                             purchase_date=date.today())
            db.session.add(animal)
            db.session.flush()
            db.session.add(SalesLotItem(lot_id=lot.id, animal_id=animal.id))
        db.session.commit()

    for i in range(3):
        _make_lot(f"SMALL-{i}", 2)
    with count_queries() as small:
        logged_in_client.get("/finance/lots")

    for i in range(15):
        _make_lot(f"BIG-{i}", 2)
    with count_queries() as big:
        logged_in_client.get("/finance/lots")

    growth = big["n"] - small["n"]
    assert growth <= 3, (
        f"عدد الاستعلامات نما {growth} مع إضافة 15 دفعة — يدل على خلل "
        f"N+1 (صغير={small['n']}, كبير={big['n']})"
    )


def test_finance_export_query_count_does_not_scale_with_row_count(logged_in_client):
    def _make_finance_row(no):
        animal = Animal(animal_no=f"FX-{no}", source=AnimalSource.PURCHASE, gender="ذكر",
                         species="sheep_goat", status="active", lifecycle_stage="source",
                         purchase_date=date.today())
        db.session.add(animal)
        db.session.flush()
        db.session.add(Finance(date=date.today(), operation_type="expense", amount=10,
                                description="بند اختبار", related_animal_id=animal.id))
        db.session.commit()

    for i in range(3):
        _make_finance_row(f"SMALL-{i}")
    with count_queries() as small:
        logged_in_client.get("/finance/export")

    for i in range(15):
        _make_finance_row(f"BIG-{i}")
    with count_queries() as big:
        logged_in_client.get("/finance/export")

    growth = big["n"] - small["n"]
    assert growth <= 3, (
        f"عدد الاستعلامات نما {growth} مع إضافة 15 سجل مالي — يدل على "
        f"خلل N+1 (صغير={small['n']}, كبير={big['n']})"
    )
