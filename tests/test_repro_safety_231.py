"""بند إضافي 231 — ثلاث ثغرات مؤكدة بمراجعة تقنية للتقريع:
1) حد أدنى لعمر الفحل (فلترة صامتة، بدون تجاوز).
2) صلاحية منفصلة لتجاوز تحذير القرابة الوراثية — الدكتور يطلب،
   صاحب الحلال يقرر.
3) اقتراح نعاج جاهزة للتقريع وغير قريبة للفحل المختار."""
from datetime import date, timedelta

from app.extensions import db
from app.models import FarmSettings, Role, User, Mating, Task
from tests.factories import make_animal, make_barn


def _set_age(animal, days):
    animal.birth_date = date.today() - timedelta(days=days)
    db.session.commit()


def _doctor_client(client, app):
    role = Role.query.filter_by(name="doctor").first()
    u = User(name="دكتور اختبار", phone="0500099001", role_id=role.id, language="ar")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    client.post("/login", data={"phone": u.phone, "password": "pass1234"})
    return u


# ---------- بند 6: حد أدنى لعمر الفحل ----------

def test_young_male_excluded_from_mating_form(app, logged_in_client):
    fs = FarmSettings.get()
    young = make_animal(animal_no="RAM-YOUNG", gender="ذكر")
    _set_age(young, fs.min_male_breeding_age_days - 10)
    old = make_animal(animal_no="RAM-OLD", gender="ذكر")
    _set_age(old, fs.min_male_breeding_age_days + 10)

    resp = logged_in_client.get("/repro/matings/new")
    body = resp.data.decode()
    assert "RAM-OLD" in body
    assert "RAM-YOUNG" not in body


def test_male_with_unknown_age_not_excluded(app, logged_in_client):
    unknown = make_animal(animal_no="RAM-UNKNOWN", gender="ذكر")
    assert unknown.birth_date is None
    resp = logged_in_client.get("/repro/matings/new")
    assert "RAM-UNKNOWN" in resp.data.decode()


def test_save_rejected_if_male_id_bypasses_age_filter(app, logged_in_client):
    fs = FarmSettings.get()
    female = make_animal(animal_no="EWE-01", gender="أنثى")
    young = make_animal(animal_no="RAM-YOUNG2", gender="ذكر")
    _set_age(young, fs.min_male_breeding_age_days - 5)

    resp = logged_in_client.post("/repro/matings/new", data={
        "date": date.today().isoformat(), "female_id": str(female.id), "male_id": str(young.id),
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Mating.query.count() == 0
    assert "غير متاح للتقريع" in resp.data.decode()


# ---------- بند 2: صلاحية تجاوز القرابة ----------

def test_owner_can_override_relation_directly(app, logged_in_client):
    mother = make_animal(animal_no="MOM-01", gender="أنثى")
    son = make_animal(animal_no="SON-01", gender="ذكر", price=None)
    son.mother_id = mother.id
    db.session.commit()
    _set_age(son, 300)

    resp = logged_in_client.post("/repro/matings/new", data={
        "date": date.today().isoformat(), "female_id": str(mother.id), "male_id": str(son.id),
        "confirm_relation": "1",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Mating.query.count() == 1


def test_doctor_without_permission_creates_override_request_not_mating(app, client, owner):
    _doctor_client(client, app)
    mother = make_animal(animal_no="MOM-02", gender="أنثى")
    son = make_animal(animal_no="SON-02", gender="ذكر")
    son.mother_id = mother.id
    db.session.commit()
    _set_age(son, 300)

    resp = client.post("/repro/matings/new", data={
        "date": date.today().isoformat(), "female_id": str(mother.id), "male_id": str(son.id),
        "confirm_relation": "1", "override_reason": "سبب اختباري",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Mating.query.count() == 0, "ما يفترض يتسجّل تقريع مباشرة من دكتور بدون صلاحية التجاوز"
    assert Task.query.filter(Task.title.contains("طلب تجاوز قرابة وراثية")).count() == 1


def test_doctor_without_reason_is_blocked(app, client):
    _doctor_client(client, app)
    mother = make_animal(animal_no="MOM-03", gender="أنثى")
    son = make_animal(animal_no="SON-03", gender="ذكر")
    son.mother_id = mother.id
    db.session.commit()
    _set_age(son, 300)

    resp = client.post("/repro/matings/new", data={
        "date": date.today().isoformat(), "female_id": str(mother.id), "male_id": str(son.id),
        "confirm_relation": "1",
    }, follow_redirects=True)
    assert Mating.query.count() == 0
    assert "لازم تكتب سبب" in resp.data.decode()


# ---------- بند 7: اقتراح نعاج غير قريبة ----------

def test_suggest_unrelated_females_excludes_relatives(app, logged_in_client):
    fs = FarmSettings.get()
    ram = make_animal(animal_no="RAM-SUG", gender="ذكر")
    _set_age(ram, fs.min_male_breeding_age_days + 30)

    daughter = make_animal(animal_no="EWE-REL", gender="أنثى")
    daughter.father_id = ram.id
    _set_age(daughter, fs.min_breeding_age_days + 30)

    unrelated = make_animal(animal_no="EWE-FREE", gender="أنثى")
    _set_age(unrelated, fs.min_breeding_age_days + 30)

    resp = logged_in_client.get(f"/repro/matings/suggest-females?male_id={ram.id}")
    assert resp.status_code == 200
    animal_nos = [row["animal_no"] for row in resp.get_json()]
    assert "EWE-FREE" in animal_nos
    assert "EWE-REL" not in animal_nos
