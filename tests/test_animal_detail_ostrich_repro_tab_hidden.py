"""فحص شامل سطر بسطر — صفحة تفاصيل الحيوان (بند بعد فحص قائمة الحيوانات).

خلل واجهة حقيقي: تبويب "التكاثر" (تقريع/تشخيص حمل/سونار — بيولوجيا
مجترات بحتة) كان يظهر بلا شرط حتى لصفحة تفاصيل النعام، رغم إن النعام
مستثنى صراحة من محرك التكاثر هذا (بند 23) وله نظام بيض/تفقيس منفصل
تماماً (`app/ostrich/`). التبويب ما يسبب خطأ (الجداول تطلع فاضية)، لكنه
مضلِّل — يوحي بوجود بيانات تكاثر غير موجودة أصلاً لهذي الفصيلة."""
from datetime import date

from app.extensions import db
from app.models import Animal
from app.models.animal import AnimalSource


def _make_ostrich(no="OS-1"):
    animal = Animal(animal_no=no, source=AnimalSource.PURCHASE, gender="أنثى",
                     species="ostrich", status="active", lifecycle_stage="source",
                     purchase_date=date.today())
    db.session.add(animal)
    db.session.commit()
    return animal


def _make_sheep(no="SH-1"):
    animal = Animal(animal_no=no, source=AnimalSource.PURCHASE, gender="أنثى",
                     species="sheep_goat", status="active", lifecycle_stage="source",
                     purchase_date=date.today())
    db.session.add(animal)
    db.session.commit()
    return animal


def test_ostrich_detail_page_hides_reproduction_tab(logged_in_client, owner):
    ostrich = _make_ostrich()
    resp = logged_in_client.get(f"/animals/{ostrich.id}")
    assert resp.status_code == 200
    assert "data-tab=\"repro\"".encode() not in resp.data, (
        "صفحة تفاصيل النعام لازم ما تعرض تبويب التكاثر (تقريع/حمل/سونار) "
        "— هذي الفصيلة مستثناة صراحة من محرك التكاثر"
    )


def test_sheep_detail_page_still_shows_reproduction_tab(logged_in_client, owner):
    sheep = _make_sheep()
    resp = logged_in_client.get(f"/animals/{sheep.id}")
    assert resp.status_code == 200
    assert "data-tab=\"repro\"".encode() in resp.data, (
        "صفحة تفاصيل رأس من الحلال (غير نعام) لازم يبقى يشوف تبويب "
        "التكاثر زي ما هو"
    )
