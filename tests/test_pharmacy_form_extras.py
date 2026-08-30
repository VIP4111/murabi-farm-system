"""اختبارات إضافات فورم الدواء (بند إضافي 61): ظروف التخزين، الجرعة
الافتراضية للرأس، قائمة "طريقة الاستخدام" القابلة للتوسّع، وفئة دواء
جديدة "مطهرات وعلاجات موضعية"."""
from app.extensions import db
from app.models import Pharmacy, UsageRoute


def test_pharmacy_new_saves_storage_condition_and_default_dose(app, logged_in_client):
    resp = logged_in_client.post("/health/pharmacy/new", data={
        "name": "لقاح اختبار 61", "medicine_class": "vaccine",
        "storage_condition": "refrigerated", "default_dose_ml": "1.5",
    }, follow_redirects=True)
    assert resp.status_code == 200
    item = Pharmacy.query.filter_by(name="لقاح اختبار 61").one()
    assert item.storage_condition == "refrigerated"
    assert item.default_dose_ml == 1.5


def test_pharmacy_edit_updates_storage_condition_and_default_dose(app, logged_in_client):
    item = Pharmacy(name="دواء اختبار تعديل 61", status="active")
    db.session.add(item)
    db.session.commit()
    resp = logged_in_client.post(f"/health/pharmacy/{item.id}/edit", data={
        "name": item.name, "storage_condition": "frozen", "default_dose_ml": "2",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(item)
    assert item.storage_condition == "frozen"
    assert item.default_dose_ml == 2


def test_topical_disinfectant_is_a_valid_medicine_class(app):
    assert "topical_disinfectant" in Pharmacy.MEDICINE_CLASSES
    assert Pharmacy.MEDICINE_CLASS_LABELS_AR["topical_disinfectant"] == "مطهرات وعلاجات موضعية"


def test_usage_route_seed_defaults_creates_seven_routes_once(app):
    UsageRoute.seed_defaults()
    assert UsageRoute.query.count() == 7
    UsageRoute.seed_defaults()  # يتأكد إنه ما يكرر الزرع
    assert UsageRoute.query.count() == 7


def test_usage_routes_new_adds_and_rejects_duplicate(app, logged_in_client):
    resp = logged_in_client.post("/health/usage-routes/new", data={"name": "بخّاخ استنشاق خاص"},
                                  follow_redirects=True)
    assert resp.status_code == 200
    assert UsageRoute.query.filter_by(name="بخّاخ استنشاق خاص").count() == 1

    resp = logged_in_client.post("/health/usage-routes/new", data={"name": "بخّاخ استنشاق خاص"},
                                  follow_redirects=True)
    assert resp.status_code == 200
    assert UsageRoute.query.filter_by(name="بخّاخ استنشاق خاص").count() == 1
    assert "موجودة بالقائمة أصلاً".encode() in resp.data


def test_pharmacy_form_renders_usage_routes_and_storage_conditions(app, logged_in_client):
    resp = logged_in_client.get("/health/pharmacy/new")
    assert resp.status_code == 200
    assert "طريقة استخدام جديدة".encode() in resp.data or "usage-routes/new".encode() in resp.data
    assert "ظروف التخزين".encode() in resp.data


def test_dose_rules_json_includes_default_dose_ml_fallback(app, logged_in_client):
    item = Pharmacy(name="لقاح افتراضي 61", medicine_class="vaccine", default_dose_ml=3, status="active")
    db.session.add(item)
    db.session.commit()
    resp = logged_in_client.get(f"/health/pharmacy/{item.id}/dose-rules")
    assert resp.status_code == 200
    assert resp.get_json()["default_dose_ml"] == 3


# ---- بند إضافي (2026-08-30) — طلبك الصريح بعد شاشة الصلاحيات: "نفس
# الحركه ضيفها في من داخل اضافة دوا... دواعي الاستعمال" — دليل فئة
# الدواء (زر "ℹ️ دليل الدواء") صار يعرض ترجمة إنجليزية جنب العربي.

def test_medicine_class_guide_en_matches_arabic_classes_exactly():
    """كل فئة دواء عربية لازم يكون لها ترجمة إنجليزية مطابقة — صفر
    فئة ناقصة وصفر فئة زايدة، بنفس أسلوب فحص PERMISSIONS_EN."""
    from app.health.health_service import MEDICINE_CLASS_GUIDE, MEDICINE_CLASS_GUIDE_EN
    ar_keys = set(MEDICINE_CLASS_GUIDE.keys())
    en_keys = set(MEDICINE_CLASS_GUIDE_EN.keys())
    assert ar_keys == en_keys
    for key, guide in MEDICINE_CLASS_GUIDE_EN.items():
        assert guide.get("title") and guide.get("notes")


def test_pharmacy_new_page_ships_english_guide_dict_to_js(app, logged_in_client):
    resp = logged_in_client.get("/health/pharmacy/new")
    assert resp.status_code == 200
    assert b"MEDICINE_CLASS_GUIDE_EN" in resp.data
    assert b"Vaccine / immunization" in resp.data


def test_pharmacy_edit_page_ships_english_guide_dict_to_js(app, logged_in_client):
    item = Pharmacy(name="لقاح اختبار ترجمة", medicine_class="vaccine", status="active")
    db.session.add(item)
    db.session.commit()
    resp = logged_in_client.get(f"/health/pharmacy/{item.id}/edit")
    assert resp.status_code == 200
    assert b"MEDICINE_CLASS_GUIDE_EN" in resp.data
