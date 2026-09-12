"""اختبار بند التصميم (طلبك "١و٢و٣" — شاشات المالية/الصيدلية/التقريع):
كل شاشة صار فيها شارة (chip) ملوّنة بدل نص عادي — نتحقق إن كلاس
الـCSS الخاص بكل شاشة موجود فعلاً بالصفحة المعروضة."""
from datetime import date

from app.extensions import db
from app.models.finance import Finance
from app.models.repro import Mating
from tests.factories import make_animal, make_barn, make_pharmacy


def test_finance_list_shows_op_type_chip(logged_in_client):
    rec = Finance(date=date.today(), operation_type="sale", item="بيع رأس", amount=500)
    db.session.add(rec)
    db.session.commit()

    resp = logged_in_client.get("/finance/")
    assert resp.status_code == 200
    assert b"op-type-chip" in resp.data


def test_pharmacy_list_shows_pharm_chip(logged_in_client):
    make_pharmacy()

    resp = logged_in_client.get("/health/pharmacy")
    assert resp.status_code == 200
    assert b"pharm-chip" in resp.data


def test_matings_list_shows_mate_chip(logged_in_client):
    barn = make_barn()
    female = make_animal(animal_no="F-01", gender="أنثى", barn_id=barn.id)
    mating = Mating(date=date.today(), female_id=female.id, barn_id=barn.id)
    db.session.add(mating)
    db.session.commit()

    resp = logged_in_client.get("/repro/matings")
    assert resp.status_code == 200
    assert b"mate-chip" in resp.data
