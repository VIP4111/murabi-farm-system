"""بند إصلاح (فحص عميق — طلبك: "كلهم نفس المشكله لا تبرر ولا تسولف حل
مشكلة التعريب"، صور حية لمستخدم إنجليزي: صفحة دورة الإنتاج، دليل
المربي المبتدئ، سلالة الحيوان، فئة الدواء) — كل هذي شاشات كانت عربي
بحت بدون أي `_()`/`display_label()` رغم إن الحساب لغته إنجليزي."""
from app.extensions import db
from app.models import Role, User
from app.models.checklist import ChecklistItem
from app.models.animal_options import Breed
from app.models.pharmacy import Pharmacy
from app.core import cycle_engine
from tests.factories import make_animal
from flask_babel import force_locale


def _english_owner(phone="0500099501"):
    role = Role.query.filter_by(name="owner").first()
    owner = User(name="English Owner", phone=phone, role_id=role.id, language="en")
    owner.set_password("pass1234")
    db.session.add(owner)
    db.session.commit()
    return owner


def test_cycle_engine_missing_items_translated_to_english(app):
    animal = make_animal(animal_no="EN-WF-1")
    wf = cycle_engine.get_or_create_workflow(animal)
    with force_locale("en"):
        passed, missing = cycle_engine._gate_quarantine(animal, wf)
    assert not passed
    assert "Health check, vet visit, or vaccination" in missing


def test_route_labels_translate_via_gettext(app):
    with force_locale("en"):
        from flask_babel import gettext as _
        assert _(cycle_engine.ROUTE_LABELS["fattening"]) == "Fattening"


def test_animal_workflow_screen_shows_english_stage_for_english_owner(app, client):
    owner = _english_owner()
    animal = make_animal(animal_no="EN-WF-2")
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get(f"/animals/{animal.id}/workflow")
    assert resp.status_code == 200
    assert "اختيار المصدر".encode() not in resp.data
    assert b"Source selection" in resp.data


def test_checklist_item_display_title_translates(app):
    item = ChecklistItem(code="t1", title="عنوان تجريبي", title_en="Test title",
                          description="وصف", description_en="Description")
    db.session.add(item)
    db.session.commit()
    with force_locale("en"):
        assert item.display_title() == "Test title"
        assert item.display_description() == "Description"
    with force_locale("ar"):
        assert item.display_title() == "عنوان تجريبي"


def test_default_breed_has_english_seed(app):
    Breed.seed_defaults()
    goat = Breed.query.filter_by(name="ماعز").first()
    assert goat is not None
    with force_locale("en"):
        assert goat.display_label() == "Goat"


def test_pharmacy_medicine_class_labels_locale_aware(app):
    with force_locale("en"):
        assert Pharmacy.medicine_class_labels()["vaccine"] == "Vaccine / immunization"
    with force_locale("ar"):
        assert Pharmacy.medicine_class_labels()["vaccine"] == "لقاح/تحصين"


def test_pharmacy_list_screen_shows_english_medicine_class(app, client):
    owner = _english_owner(phone="0500099502")
    p = Pharmacy(name="Test Vaccine", medicine_class="vaccine", available_qty=1, unit_price=1)
    db.session.add(p)
    db.session.commit()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/health/pharmacy")
    assert resp.status_code == 200
    assert b"Vaccine" in resp.data
