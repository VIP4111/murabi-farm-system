"""فحوصات دورية تلقائية + إدارة بنود الفحص (بند إضافي، طلبك الصريح:
"المفروض تجيله إشعار تنبيه أو مهمة بشكل تلقائي... النظام يقوم بهذا
الطلب" + "صاحب الحلال يستطيع الحذف والاستبدال والاضافة")."""
from datetime import date, timedelta

from app.extensions import db
from app.models import CheckupItemPreset, Disease, VetVisit, Doctor, Task
from app.core import auto_checkup_service as svc
from tests.factories import make_animal, make_barn


def _seed_presets():
    CheckupItemPreset.seed_defaults()


def test_owner_can_add_edit_delete_checkup_item(app, logged_in_client):
    resp = logged_in_client.post("/settings/checkup-items/new", data={"text": "فحص الأسنان"},
                                  follow_redirects=True)
    assert resp.status_code == 200
    item = CheckupItemPreset.query.filter_by(text="فحص الأسنان").first()
    assert item is not None

    resp = logged_in_client.post(f"/settings/checkup-items/{item.id}/edit",
                                  data={"text": "فحص الأسنان واللثة", "is_active": "on"},
                                  follow_redirects=True)
    assert resp.status_code == 200
    assert CheckupItemPreset.query.get(item.id).text == "فحص الأسنان واللثة"

    resp = logged_in_client.post(f"/settings/checkup-items/{item.id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert CheckupItemPreset.query.get(item.id) is None


def test_manual_checkup_screen_forbidden_for_doctor(app, client):
    from app.models import Role, User
    doctor_role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="دكتور اختبار", phone="0500099101", role_id=doctor_role.id, language="ar")
    doctor.set_password("pass1234")
    db.session.add(doctor)
    db.session.commit()

    animal = make_animal(animal_no="ACHK-01")
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.post(f"/animals/{animal.id}/checkup-request", data={"items": ["فحص الحرارة والنبض"]})
    assert resp.status_code == 403


def test_disease_rule_generates_checkup_and_does_not_duplicate_within_cooldown(app):
    _seed_presets()
    animal = make_animal(animal_no="ACHK-02")
    db.session.add(Disease(animal_id=animal.id, disease_name="مرض اختبار", date=date.today(), status="active"))
    db.session.commit()

    generated = svc.generate_automatic_checkups(today=date.today())
    assert generated == 1
    tasks = Task.query.filter_by(animal_id=animal.id, source_type=svc.SOURCE_DISEASE).all()
    assert len(tasks) == len(CheckupItemPreset.active_texts())
    assert all(t.status == "pending" and t.target_role == "doctor" for t in tasks)

    # نفس اليوم/يوم بعده — داخل نافذة الـ3 أيام، ما يتكرر.
    generated_again = svc.generate_automatic_checkups(today=date.today() + timedelta(days=1))
    assert generated_again == 0
    assert Task.query.filter_by(animal_id=animal.id, source_type=svc.SOURCE_DISEASE).count() == len(tasks)


def test_disease_rule_regenerates_after_cooldown_window(app):
    _seed_presets()
    animal = make_animal(animal_no="ACHK-03")
    db.session.add(Disease(animal_id=animal.id, disease_name="مرض اختبار", date=date.today(), status="active"))
    db.session.commit()
    svc.generate_automatic_checkups(today=date.today())
    # نزوّر تاريخ إنشاء المهام القديمة لتكون قبل 4 أيام (تجاوزت نافذة الـ3 أيام).
    old_tasks = Task.query.filter_by(animal_id=animal.id, source_type=svc.SOURCE_DISEASE).all()
    for t in old_tasks:
        t.created_at = t.created_at - timedelta(days=4)
    db.session.commit()

    generated = svc.generate_automatic_checkups(today=date.today())
    assert generated == 1


def test_routine_rule_generates_for_animal_with_no_recent_checkup(app):
    _seed_presets()
    animal = make_animal(animal_no="ACHK-04")
    generated = svc.generate_automatic_checkups(today=date.today())
    assert generated == 1
    assert Task.query.filter_by(animal_id=animal.id, source_type=svc.SOURCE_ROUTINE).count() == len(CheckupItemPreset.active_texts())


def test_routine_rule_skips_animal_with_recent_vet_visit(app):
    _seed_presets()
    animal = make_animal(animal_no="ACHK-05")
    doctor = Doctor(name="دكتور اختبار")
    db.session.add(doctor)
    db.session.commit()
    db.session.add(VetVisit(date=date.today() - timedelta(days=5), doctor_id=doctor.id, animal_id=animal.id))
    db.session.commit()

    generated = svc.generate_automatic_checkups(today=date.today())
    assert generated == 0
    assert Task.query.filter_by(animal_id=animal.id, source_type=svc.SOURCE_ROUTINE).count() == 0


def test_routine_rule_ignores_animal_already_covered_by_disease_rule_same_run(app):
    """رأس فيه مرض مفتوح يتولّد له فحص "مرض" — ما يتولّد له فحص "دوري"
    زيادة بنفس التشغيلة، حتى لو ما له فحص من 30 يوم أصلاً."""
    _seed_presets()
    animal = make_animal(animal_no="ACHK-06")
    db.session.add(Disease(animal_id=animal.id, disease_name="مرض اختبار", date=date.today(), status="active"))
    db.session.commit()

    svc.generate_automatic_checkups(today=date.today())
    assert Task.query.filter_by(animal_id=animal.id, source_type=svc.SOURCE_ROUTINE).count() == 0
    assert Task.query.filter_by(animal_id=animal.id, source_type=svc.SOURCE_DISEASE).count() > 0
