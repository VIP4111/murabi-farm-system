"""فحص شامل سطر بسطر — ميزة التكاثر.

مشاكل حقيقية اكتُشفت: عدد الأجنة/عمر الحمل بالأيام/جرعة الحقنة
الهرمونية كانت تُحفَظ بلا أي فحص (ورقم غير صالح يسقط بخطأ 500 مباشر
بدل رسالة واضحة)، N+1 على شاشات القوائم (تقريع/حمل/سونار/برامج)،
وتاريخ خام (UTC) بدل farm_today() بعدة مواضع."""
from contextlib import contextmanager
from datetime import date

from sqlalchemy import event

from app.extensions import db
from app.models import Mating, Pregnancy
from factories import make_animal


@contextmanager
def count_queries():
    counter = {"n": 0}

    def _on_execute(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    engine = db.session.get_bind()
    event.listen(engine, "before_cursor_execute", _on_execute)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _on_execute)


def test_pregnancies_new_rejects_absurd_embryo_count(logged_in_client):
    ewe = make_animal(animal_no="RP-1", gender="أنثى")
    resp = logged_in_client.post("/repro/pregnancies/new", data={
        "female_id": str(ewe.id), "date": date.today().isoformat(), "embryo_count": "99",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Pregnancy.query.filter_by(female_id=ewe.id).first() is None


def test_pregnancies_new_accepts_valid_embryo_count(logged_in_client):
    ewe = make_animal(animal_no="RP-2", gender="أنثى")
    resp = logged_in_client.post("/repro/pregnancies/new", data={
        "female_id": str(ewe.id), "date": date.today().isoformat(), "embryo_count": "2",
    }, follow_redirects=True)
    assert resp.status_code == 200
    p = Pregnancy.query.filter_by(female_id=ewe.id).first()
    assert p is not None
    assert p.embryo_count == 2


def test_sonar_new_rejects_absurd_gestation_age(logged_in_client):
    ewe = make_animal(animal_no="RP-3", gender="أنثى")
    resp = logged_in_client.post("/repro/sonar/new", data={
        "ewe_id": str(ewe.id), "exam_date": date.today().isoformat(), "gestation_age_days": "9999",
    }, follow_redirects=True)
    assert resp.status_code == 200
    from app.models import SonarResult
    assert SonarResult.query.filter_by(ewe_id=ewe.id).first() is None


def test_matings_list_query_count_does_not_scale_with_row_count(logged_in_client):
    def _make_matings(n, start):
        for i in range(start, start + n):
            female = make_animal(animal_no=f"ML-F-{i}", gender="أنثى")
            male = make_animal(animal_no=f"ML-M-{i}", gender="ذكر")
            db.session.add(Mating(female_id=female.id, male_id=male.id, date=date.today()))
        db.session.commit()

    _make_matings(3, 0)
    with count_queries() as small:
        logged_in_client.get("/repro/matings")

    _make_matings(15, 3)
    with count_queries() as big:
        logged_in_client.get("/repro/matings")

    growth = big["n"] - small["n"]
    assert growth <= 3, (
        f"عدد الاستعلامات نما {growth} مع إضافة 15 سجل تقريع — يدل على "
        f"خلل N+1 (صغير={small['n']}, كبير={big['n']})"
    )


def test_pregnancies_list_today_uses_farm_today(logged_in_client, monkeypatch):
    ewe = make_animal(animal_no="RP-TODAY", gender="أنثى")
    db.session.add(Pregnancy(female_id=ewe.id, date=date.today(), confirmed=True))
    db.session.commit()

    fake_farm_date = date(2030, 3, 3)
    monkeypatch.setattr("app.repro.routes.farm_today", lambda: fake_farm_date)
    resp = logged_in_client.get("/repro/pregnancies")
    assert resp.status_code == 200
    assert b"2030-03-03" in resp.data
