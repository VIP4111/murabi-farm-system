"""بند إصلاح (تصميم — طلبك: "شاشة الصحة (التطعيمات/الأمراض)" بعد
نموذج "سجل الحيوانات" المعتمَد) — عمود حالة ملوّن (متأخر/قادم) بشاشة
التطعيمات (كان بدون أي تمييز بصري)، وشارة شدة ملوّنة بشاشة الأمراض
(كانت نص عادي بدون لون)."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Vaccination
from tests.factories import make_animal


def test_vaccinations_list_shows_overdue_chip_for_past_due_date(app, logged_in_client):
    a = make_animal(animal_no="VAX-COLOR-01")
    v = Vaccination(
        animal_id=a.id, date=date.today() - timedelta(days=400), vaccine_name="لقاح تجريبي",
        next_due_date=date.today() - timedelta(days=30),
    )
    db.session.add(v)
    db.session.commit()

    resp = logged_in_client.get("/health/vaccinations")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "متأخر" in body


def test_vaccinations_list_shows_upcoming_chip_for_future_due_date(app, logged_in_client):
    a = make_animal(animal_no="VAX-COLOR-02")
    v = Vaccination(
        animal_id=a.id, date=date.today(), vaccine_name="لقاح تجريبي",
        next_due_date=date.today() + timedelta(days=30),
    )
    db.session.add(v)
    db.session.commit()

    resp = logged_in_client.get("/health/vaccinations")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "قادم" in body


def test_diseases_list_severity_chip_uses_colored_class(app, logged_in_client):
    a = make_animal(animal_no="DIS-COLOR-01")
    resp = logged_in_client.post("/health/diseases/new", data={
        "animal_id": a.id, "disease_name": "مرض اختبار الألوان",
        "date": "2026-01-01", "severity": "severe",
    })
    assert resp.status_code in (302, 200)

    resp = logged_in_client.get("/health/diseases")
    assert resp.status_code == 200
    assert "severity-chip" in resp.data.decode()
