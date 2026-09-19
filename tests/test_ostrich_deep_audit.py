"""فحص شامل سطر بسطر — ميزة النعام.

مشاكل حقيقية اكتُشفت (نفس فئة خلل حارس double-hatch السابق):
1. place_in_incubator ما كان فيه حارس ضد إعادة إدخال بيضة مسجَّلة نتيجة
   فقس أصلاً، أو موجودة بحاضنة ثانية فعلاً.
2. سعة الحاضنة ما كانت مفروضة إطلاقاً (موثَّق صراحة بنص الشاشة نفسه).
3. رقم الأم عند تسجيل بيضة ما كان يُتحقَّق سيرفرياً (فلترة الواجهة بس).
4. N+1 على شاشة قائمة البيض.
"""
from contextlib import contextmanager
from datetime import date

import pytest
from sqlalchemy import event

from app.core import ostrich_service as svc
from app.extensions import db
from app.models import Animal
from app.models.animal import AnimalSource
from app.models.ostrich import Incubator, OstrichEgg


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


def _mother(no="OST-DA-M"):
    m = Animal(animal_no=no, source=AnimalSource.PURCHASE, gender="أنثى",
               species="ostrich", status="active")
    db.session.add(m)
    db.session.commit()
    return m


def _egg(mother, no_suffix=""):
    egg = OstrichEgg(mother_id=mother.id, lay_date=date.today())
    db.session.add(egg)
    db.session.commit()
    return egg


def test_place_in_incubator_rejects_already_hatched_egg(app):
    mother = _mother("OST-DA-M1")
    egg = _egg(mother)
    incubator = Incubator(code="INC-1")
    db.session.add(incubator)
    db.session.commit()
    svc.record_hatch_success(egg, actual_hatch_date=date.today(), animal_no="OST-DA-C1")

    with pytest.raises(ValueError):
        svc.place_in_incubator(egg, incubator_id=incubator.id, incubation_start_date=date.today())


def test_place_in_incubator_enforces_capacity(app):
    mother = _mother("OST-DA-M2")
    incubator = Incubator(code="INC-2", capacity=1)
    db.session.add(incubator)
    db.session.commit()

    egg1 = _egg(mother)
    svc.place_in_incubator(egg1, incubator_id=incubator.id, incubation_start_date=date.today())

    egg2 = _egg(mother)
    with pytest.raises(svc.OstrichIncubatorFullError):
        svc.place_in_incubator(egg2, incubator_id=incubator.id, incubation_start_date=date.today())


def test_place_in_incubator_still_allows_updating_same_egg(app):
    """إعادة إرسال نفس الفورم لنفس البيضة بنفس الحاضنة (مثلاً تعديل
    تاريخ البدء) ما يفترض يُرفض كـ"حاضنة ثانية"."""
    mother = _mother("OST-DA-M3")
    incubator = Incubator(code="INC-3", capacity=1)
    db.session.add(incubator)
    db.session.commit()
    egg = _egg(mother)
    svc.place_in_incubator(egg, incubator_id=incubator.id, incubation_start_date=date.today())
    # نفس البيضة، نفس الحاضنة، تاريخ مختلف — يفترض يشتغل عادي
    from datetime import timedelta
    svc.place_in_incubator(egg, incubator_id=incubator.id, incubation_start_date=date.today() - timedelta(days=1))
    assert egg.incubator_id == incubator.id


def test_eggs_new_rejects_mother_not_active_female_ostrich(logged_in_client):
    male = Animal(animal_no="OST-DA-MALE", source=AnimalSource.PURCHASE, gender="ذكر",
                  species="ostrich", status="active")
    db.session.add(male)
    db.session.commit()

    resp = logged_in_client.post("/ostrich/eggs/new", data={
        "mother_id": str(male.id), "lay_date": date.today().isoformat(),
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert OstrichEgg.query.filter_by(mother_id=male.id).first() is None


def test_incubators_new_rejects_zero_capacity(logged_in_client):
    resp = logged_in_client.post("/ostrich/incubators/new", data={
        "code": "INC-BAD", "capacity": "0",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Incubator.query.filter_by(code="INC-BAD").first() is None


def test_eggs_list_query_count_does_not_scale_with_egg_count(logged_in_client):
    def _make_eggs(n, start, prefix):
        for i in range(start, start + n):
            m = _mother(f"{prefix}-{i}")
            db.session.add(OstrichEgg(mother_id=m.id, lay_date=date.today()))
        db.session.commit()

    _make_eggs(3, 0, "QCS")
    with count_queries() as small:
        logged_in_client.get("/ostrich/eggs")

    _make_eggs(15, 0, "QCB")
    with count_queries() as big:
        logged_in_client.get("/ostrich/eggs")

    growth = big["n"] - small["n"]
    assert growth <= 3, (
        f"عدد الاستعلامات نما {growth} مع إضافة 15 بيضة — يدل على خلل "
        f"N+1 (صغير={small['n']}, كبير={big['n']})"
    )
