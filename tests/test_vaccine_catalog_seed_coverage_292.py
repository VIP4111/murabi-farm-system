"""بند إضافي 292 — طلبك الصريح "كملها الثلاثة كاملة": كتالوج التحصين
المرجعي (بند 290) كان يُزرع تلقائياً بس عند فتح شاشة "الصيدلية" —
لو أول شي فتحته المالك بعد التحديث شاشة تحصين مباشرة، الأصناف الثلاثة
ما تكون موجودة بعد. صار يُزرع من كل شاشة تعرض/تختار لقاح فعلياً."""
from app.models import Pharmacy
from factories import make_animal


def test_vaccinations_new_seeds_catalog(app, logged_in_client):
    assert Pharmacy.query.filter_by(medicine_class="vaccine").count() == 0
    resp = logged_in_client.get("/health/vaccinations/new")
    assert resp.status_code == 200
    assert Pharmacy.query.filter_by(medicine_class="vaccine").count() == 3


def test_vaccination_schedule_new_seeds_catalog(app, logged_in_client):
    assert Pharmacy.query.filter_by(medicine_class="vaccine").count() == 0
    resp = logged_in_client.get("/health/vaccination-schedule/new")
    assert resp.status_code == 200
    assert Pharmacy.query.filter_by(medicine_class="vaccine").count() == 3


def test_bulk_vaccination_action_seeds_catalog(app, logged_in_client):
    animal = make_animal(animal_no="VC-292")
    assert Pharmacy.query.filter_by(medicine_class="vaccine").count() == 0
    resp = logged_in_client.post("/animals/bulk/select", data={
        "bulk_action": "vaccination", "animal_ids": [str(animal.id)],
    })
    assert resp.status_code == 200
    assert Pharmacy.query.filter_by(medicine_class="vaccine").count() == 3
