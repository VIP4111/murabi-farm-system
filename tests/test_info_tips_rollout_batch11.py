"""طلب "اكمل بدفعه كبيره" — دفعة رابعة من فقعات الشرح تغطي شاشات
التفاصيل: تفاصيل الرأس، تفاصيل دفعة البيع، تفاصيل المرض، تفاصيل برنامج
الشياع التوأمي، توزيع المستودعات، حركة مخزون العلف."""
from datetime import date

from app.extensions import db
from tests.factories import make_animal, make_disease_type, make_feed


def test_animal_detail_has_tip(app, logged_in_client):
    with app.app_context():
        a = make_animal(animal_no="TIP-AD-01")
        animal_id = a.id
    resp = logged_in_client.get(f"/animals/{animal_id}")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_lot_detail_has_tip(app, logged_in_client):
    with app.app_context():
        from app.models.sales_lot import SalesLot
        lot = SalesLot(name="دفعة اختبار الفقعات")
        db.session.add(lot)
        db.session.commit()
        lot_id = lot.id
    resp = logged_in_client.get(f"/finance/lots/{lot_id}")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_disease_type_detail_has_tip(app, logged_in_client):
    with app.app_context():
        dt = make_disease_type(name="مرض اختبار الفقعات")
        disease_id = dt.id
    resp = logged_in_client.get(f"/health/disease-types/{disease_id}")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_program_detail_has_tip(app, logged_in_client):
    with app.app_context():
        from app.models.repro import TwinEstrusProgram
        a = make_animal(animal_no="TIP-PD-01", gender="أنثى")
        prog = TwinEstrusProgram(ewe_id=a.id, start_date=date.today())
        db.session.add(prog)
        db.session.commit()
        program_id = prog.id
    resp = logged_in_client.get(f"/repro/programs/{program_id}")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_item_breakdown_has_tip(app, logged_in_client):
    with app.app_context():
        f = make_feed(name="علف اختبار الفقعات")
        item_id = f.id
    resp = logged_in_client.get(f"/warehouses/item/feed/{item_id}")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_feed_movements_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/feed/movements")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1
