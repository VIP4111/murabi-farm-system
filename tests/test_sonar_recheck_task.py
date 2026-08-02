"""بند إضافي 100 — تحويل تاريخ إعادة فحص السونار (recheck_date) لمهمة
فعلية. قبل هذا البند، الحقل كان يُدخَل بالفورم ويُخزَّن بدون أي أثر —
"بيانات ميتة" ما يذكّر أحد."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Task
from factories import make_animal, make_barn


def test_sonar_with_recheck_date_creates_task(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    barn = make_barn()
    ewe = make_animal(animal_no="SONAR-01", barn_id=barn.id)

    page = client.get("/repro/sonar/new")
    csrf = page.data.decode().split('name="csrf_token" value="')[1].split('"')[0]
    recheck = date.today() + timedelta(days=21)

    resp = client.post("/repro/sonar/new", data={
        "csrf_token": csrf, "ewe_id": str(ewe.id), "exam_date": str(date.today()),
        "result": "غير مؤكد", "recheck_date": str(recheck),
    })
    assert resp.status_code == 302

    task = Task.query.filter_by(task_type="sonar_recheck", animal_id=ewe.id).first()
    assert task is not None
    assert task.due_date == recheck
    assert task.status == "suggested"
    assert task.barn_id == barn.id


def test_sonar_without_recheck_date_creates_no_task(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    ewe = make_animal(animal_no="SONAR-02")

    page = client.get("/repro/sonar/new")
    csrf = page.data.decode().split('name="csrf_token" value="')[1].split('"')[0]

    resp = client.post("/repro/sonar/new", data={
        "csrf_token": csrf, "ewe_id": str(ewe.id), "exam_date": str(date.today()),
        "result": "حامل",
    })
    assert resp.status_code == 302

    task = Task.query.filter_by(task_type="sonar_recheck", animal_id=ewe.id).first()
    assert task is None
