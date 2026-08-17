"""بند إضافي 209 — طلبك: صفحة الرأس تعرض "متطلبات ناقصة للانتقال"
(وزن ناقص، فحص صحي ناقص، فترة حجر باقية) بس ما فيه أي تنبيه استباقي
بشاشة "التنبيهات" العامة لو رأس واقف عند نفس المرحلة لفترة طويلة —
لازم تدخل صفحة كل رأس بنفسك لتلاحظ. أضفنا تنبيه تلقائي (`_stalled_workflow`)
لأي رأس نشط عنده نواقص ومر على آخر تحديث لحالته أكثر من عتبة قابلة
للتعديل (`workflow_stall_alert_days`، افتراضي 5 أيام)."""
from datetime import datetime, timedelta, timezone

from app.core import alerts_service, cycle_engine
from app.extensions import db
from app.models import FarmSettings
from factories import make_animal


def test_fresh_stalled_animal_not_alerted_yet(app):
    """رأس واقف من ثواني بس — تحت العتبة، ما يستاهل تنبيه لسا."""
    animal = make_animal(animal_no="STALL-01", price=500)
    cycle_engine.get_or_create_workflow(animal)
    cycle_engine.evaluate(animal)
    db.session.commit()

    fs = FarmSettings.get()
    alerts = alerts_service._stalled_workflow(fs)
    assert not any(a["animal_id"] == animal.id for a in alerts)


def test_animal_stalled_past_threshold_is_alerted(app):
    animal = make_animal(animal_no="STALL-02", price=500)
    wf = cycle_engine.get_or_create_workflow(animal)
    cycle_engine.evaluate(animal)
    db.session.commit()

    fs = FarmSettings.get()
    # نحاكي مرور الوقت — نرجّع updated_at لخلف عتبة التنبيه (بدل انتظار فعلي).
    wf.updated_at = datetime.now(timezone.utc) - timedelta(days=fs.workflow_stall_alert_days + 1)
    db.session.add(wf)
    db.session.commit()

    alerts = alerts_service._stalled_workflow(fs)
    matching = [a for a in alerts if a["animal_id"] == animal.id]
    assert matching
    assert "STALL-02" in matching[0]["label"]
    assert matching[0]["detail"]


def test_animal_without_missing_items_is_not_alerted(app):
    """رأس وصل مرحلته الكاملة (ما فيه missing_items) — ما يستاهل تنبيه
    توقّف حتى لو ما تغيّر شي من فترة طويلة (طبيعي، مو عالق)."""
    animal = make_animal(animal_no="STALL-03", price=500)
    wf = cycle_engine.get_or_create_workflow(animal)
    wf.missing_items = None
    wf.status = "active"
    wf.updated_at = datetime.now(timezone.utc) - timedelta(days=30)
    db.session.add(wf)
    db.session.commit()

    fs = FarmSettings.get()
    alerts = alerts_service._stalled_workflow(fs)
    assert not any(a["animal_id"] == animal.id for a in alerts)


def test_vaccination_counts_splits_overdue_and_upcoming(app):
    from datetime import date
    from app.models import Vaccination

    animal1 = make_animal(animal_no="VAC-01", price=500)
    animal2 = make_animal(animal_no="VAC-02", price=500)
    db.session.add_all([
        Vaccination(animal_id=animal1.id, vaccine_name="لقاح اختبار", date=date.today() - timedelta(days=30),
                    next_due_date=date.today() - timedelta(days=1)),
        Vaccination(animal_id=animal2.id, vaccine_name="لقاح اختبار", date=date.today() - timedelta(days=5),
                    next_due_date=date.today() + timedelta(days=30)),
    ])
    db.session.commit()

    overdue, upcoming = alerts_service.vaccination_counts()
    assert overdue == 1
    assert upcoming == 1
