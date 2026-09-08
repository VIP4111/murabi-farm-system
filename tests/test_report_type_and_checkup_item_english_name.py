"""بند إصلاح (فحص عميق — طلبك: "تأكد من باقي الشاشات ما فيهم نفس
المشكلة" بعد بلاغ أعراض المساعد التشخيصي) — نفس الفجوة بالضبط على
شاشتين إضافيتين: "نوع البلاغ" (ReportType) و"بنود الفحص"
(CheckupItemPreset)، نفس نمط `Symptom.name_en`/`display_label()`
(انظر tests/test_symptom_english_name.py)."""
from app.extensions import db
from app.models import ReportType, Role, User
from app.models.checkup_item_preset import CheckupItemPreset
from factories import make_animal
from flask_babel import force_locale


def test_report_type_display_label_returns_english_when_locale_not_arabic(app):
    rt = ReportType(name="مرض", name_en="Disease")
    db.session.add(rt)
    db.session.commit()
    with force_locale("en"):
        assert rt.display_label() == "Disease"


def test_report_type_display_label_falls_back_to_arabic_when_no_english(app):
    rt = ReportType(name="نوع بدون ترجمة")
    db.session.add(rt)
    db.session.commit()
    with force_locale("en"):
        assert rt.display_label() == "نوع بدون ترجمة"


def test_checkup_item_display_label_returns_english_when_locale_not_arabic(app):
    item = CheckupItemPreset(text="فحص الحرارة والنبض", text_en="Temperature & pulse check")
    db.session.add(item)
    db.session.commit()
    with force_locale("en"):
        assert item.display_label() == "Temperature & pulse check"


def test_checkup_item_label_map_falls_back_to_arabic_when_no_english(app):
    item = CheckupItemPreset(text="بند بدون ترجمة")
    db.session.add(item)
    db.session.commit()
    with force_locale("en"):
        assert CheckupItemPreset.label_map()["بند بدون ترجمة"] == "بند بدون ترجمة"


def test_report_form_screen_shows_english_report_types_for_english_worker(app, client):
    role = Role.query.filter_by(name="worker").first()
    worker = User(name="English Worker", phone="0500099401", role_id=role.id, language="en")
    worker.set_password("pass1234")
    db.session.add(worker)
    db.session.commit()

    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/team/reports/new")
    assert resp.status_code == 200
    assert b"Disease" in resp.data


def test_animal_detail_screen_shows_english_checkup_items_for_english_owner(app, client):
    role = Role.query.filter_by(name="owner").first()
    owner = User(name="English Owner", phone="0500099402", role_id=role.id, language="en")
    owner.set_password("pass1234")
    db.session.add(owner)
    animal = make_animal(animal_no="EN-CHK-1")
    db.session.add(animal)
    db.session.commit()

    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get(f"/animals/{animal.id}")
    assert resp.status_code == 200
    assert b"Temperature" in resp.data
