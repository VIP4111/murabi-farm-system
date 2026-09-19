"""فحص شامل سطر بسطر — مركز الطبيب (health.dashboard).

ثلاث مشاكل حقيقية اكتُشفت:
1. رابط "تقويم التحصينات الكامل" كان يودّي لشاشة جدول مختلف كلياً
   (VaccinationSchedule) بدل سجلات Vaccination الفعلية المُلخَّصة فوق.
2. "التحصينات المستحقة" كانت تُبنى بمنطق مستقل عن alerts_service —
   رأس عنده سجل تحصين قديم بـnext_due_date غير محدَّث (تجاوزه سجل أحدث)
   كان يظهر بالخطأ، بينما alerts_service يتجاهله صح (يعتمد آخر سجل بس).
3. N+1 حقيقي: عرض اسم الحيوان بكل صف حالة مرضية/تحصين كان يسبب استعلام
   منفصل لكل صف.
"""
from datetime import date, timedelta

from contextlib import contextmanager
from sqlalchemy import event

from app.extensions import db
from app.core import alerts_service
from app.models import Animal, Vaccination
from app.models.animal import AnimalSource


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


def _make_animal(no):
    animal = Animal(animal_no=no, source=AnimalSource.PURCHASE, gender="أنثى",
                     species="sheep_goat", status="active", lifecycle_stage="source",
                     purchase_date=date.today())
    db.session.add(animal)
    db.session.commit()
    return animal


def test_dashboard_link_points_to_real_vaccination_records_list(logged_in_client):
    """"تقويم التحصينات الكامل" كان يودّي لـ vaccination_schedule_list
    (جدول تحصينات دفعية بالحظيرة، جدول مختلف كلياً) بدل vaccinations_list
    الفعلية اللي فيها نفس السجلات المُلخَّصة بهذي البطاقة تحديداً. رابط
    القائمة الجانبية لجدول التحصينات الدفعية يبقى موجوداً بصفحات ثانية،
    فما نتحقق من غيابه الكامل، بس من وجود الرابط الصحيح لهذي البطاقة."""
    resp = logged_in_client.get("/health/dashboard")
    assert resp.status_code == 200
    from flask import url_for
    with logged_in_client.application.test_request_context():
        correct_url = url_for("health.vaccinations_list")
    assert correct_url.encode() in resp.data


def test_dashboard_ignores_stale_next_due_date_from_superseded_vaccination(logged_in_client):
    """رأس عنده سجل تحصين قديم next_due_date قريب (خلال الأسبوع)، تلاه
    سجل أحدث فعلياً بموعد استحقاق تالٍ بعيد (مؤجَّل/أُعيدت جدولته) —
    لازم يُعتمد آخر سجل فقط (نفس معيار alerts_service)، فما يظهر
    بقائمة "المستحقة خلال 7 أيام" لأن موعده الحقيقي الحالي بعيد."""
    animal = _make_animal("HD-1")
    old = Vaccination(animal_id=animal.id, vaccine_name="قديم", date=date.today() - timedelta(days=10),
                       next_due_date=date.today() + timedelta(days=2))
    newer = Vaccination(animal_id=animal.id, vaccine_name="جديد", date=date.today() - timedelta(days=1),
                         next_due_date=date.today() + timedelta(days=30))
    db.session.add_all([old, newer])
    db.session.commit()

    resp = logged_in_client.get("/health/dashboard")
    assert resp.status_code == 200
    assert "HD-1".encode() not in resp.data, (
        "آخر سجل تحصين فعلي لهذا الرأس موعده بعد 30 يوم — ما يفترض يظهر "
        "بقائمة (المستحقة خلال 7 أيام) حتى لو فيه سجل أقدم قريب"
    )


def test_dashboard_query_count_does_not_scale_with_disease_count(logged_in_client):
    from app.models import Disease

    def _make_active_disease(no):
        animal = _make_animal(no)
        db.session.add(Disease(animal_id=animal.id, disease_name="مرض اختبار",
                                date=date.today(), status="active"))
        db.session.commit()

    for i in range(3):
        _make_active_disease(f"HDQ-SMALL-{i}")
    with count_queries() as small:
        logged_in_client.get("/health/dashboard")

    for i in range(15):
        _make_active_disease(f"HDQ-BIG-{i}")
    with count_queries() as big:
        logged_in_client.get("/health/dashboard")

    growth = big["n"] - small["n"]
    assert growth <= 3, (
        f"عدد الاستعلامات نما {growth} مع إضافة 15 حالة مرضية — يدل على "
        f"خلل N+1 (صغير={small['n']}, كبير={big['n']})"
    )
