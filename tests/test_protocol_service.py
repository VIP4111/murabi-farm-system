"""اختبارات قوالب بروتوكول العلاج (بند إضافي 52، جزء 1) — تطبيق بروتوكول
يولّد مهمة "علاج مخطَّط" واحدة لكل خطوة، مستحقة باليوم الصحيح، وربط
فترة السحب الأطول يصير تلقائياً عبر البنية الموجودة أصلاً (بند 50)
بدون أي كود إضافي — نتحقق من هذا الافتراض صراحة هنا."""
from datetime import date, timedelta

import pytest

from app.core import protocol_service
from app.extensions import db
from app.health import health_service
from app.models import Task, TreatmentProtocol, TreatmentProtocolStep
from factories import make_animal, make_pharmacy


def _make_protocol(name="بروتوكول اختبار", steps=None):
    protocol = TreatmentProtocol(name=name)
    db.session.add(protocol)
    db.session.flush()
    for day_offset, title, pharmacy, qty, kind in (steps or []):
        db.session.add(TreatmentProtocolStep(
            protocol_id=protocol.id, day_offset=day_offset, step_title=title,
            pharmacy_id=pharmacy.id, quantity=qty, treatment_kind=kind,
        ))
    db.session.commit()
    return protocol


def test_apply_protocol_creates_one_task_per_step_with_correct_due_dates(app):
    animal = make_animal(animal_no="PR-01")
    med_a = make_pharmacy(name="دواء أ", withdrawal_days=3)
    med_b = make_pharmacy(name="دواء ب", withdrawal_days=10)
    protocol = _make_protocol(steps=[
        (0, "جرعة أولى", med_a, 2, "vaccination"),
        (3, "جرعة ثانية", med_b, 1, "vaccination"),
    ])
    start = date.today()

    application = protocol_service.apply_protocol(
        protocol, animal_id=animal.id, start_date=start, actor_user_id=1,
    )

    tasks = protocol_service.protocol_application_tasks(application)
    assert len(tasks) == 2
    assert tasks[0].due_date == start
    assert tasks[0].planned_pharmacy_id == med_a.id
    assert tasks[0].planned_quantity == 2
    assert tasks[0].status == "suggested"
    assert tasks[1].due_date == start + timedelta(days=3)
    assert tasks[1].planned_pharmacy_id == med_b.id


def test_apply_protocol_tasks_are_suggested_not_auto_approved(app):
    """المساعد قرار مو طبيب (بند 13) — حتى المهام المولَّدة من بروتوكول
    جاهز تبقى status='suggested' بانتظار مراجعة الدكتور، نفس بقية النظام."""
    animal = make_animal(animal_no="PR-02")
    med = make_pharmacy(name="دواء", withdrawal_days=0)
    protocol = _make_protocol(steps=[(0, "خطوة", med, 1, "vaccination")])

    application = protocol_service.apply_protocol(
        protocol, animal_id=animal.id, start_date=date.today(), actor_user_id=1,
    )
    task = protocol_service.protocol_application_tasks(application)[0]
    assert task.status == "suggested"


def test_withdrawal_takes_longest_across_confirmed_protocol_steps(app):
    """لو خطوتان بنفس البروتوكول اتنفَّذتا فعلياً (تأكيد تنفيذ حقيقي عبر
    التسجيل الطبي، مو مجرد إنشاء المهمة)، فترة السحب المعروضة للرأس
    لازم تكون الأطول بينهما — نفس سلوك `animal_under_withdrawal` الموجود
    أصلاً (بند 50)، بدون أي تعديل عليه."""
    animal = make_animal(animal_no="PR-03")
    short_wd = make_pharmacy(name="دواء قصير السحب", withdrawal_days=2, available_qty=10)
    long_wd = make_pharmacy(name="دواء طويل السحب", withdrawal_days=21, available_qty=10)

    health_service.record_vaccination(
        actor_user_id=1, animal_id=animal.id, vaccine_name="جرعة 1",
        date_=date.today(), pharmacy_id=short_wd.id, quantity_used=1,
    )
    health_service.record_vaccination(
        actor_user_id=1, animal_id=animal.id, vaccine_name="جرعة 2",
        date_=date.today(), pharmacy_id=long_wd.id, quantity_used=1,
    )

    until = health_service.animal_under_withdrawal(animal.id)
    assert until == date.today() + timedelta(days=21)


def test_apply_protocol_with_no_steps_creates_no_tasks(app):
    animal = make_animal(animal_no="PR-04")
    protocol = _make_protocol(steps=[])
    application = protocol_service.apply_protocol(
        protocol, animal_id=animal.id, start_date=date.today(), actor_user_id=1,
    )
    assert protocol_service.protocol_application_tasks(application) == []


def test_protocol_application_tasks_scoped_to_single_application(app):
    """لو نفس البروتوكول اتطبّق مرتين على نفس الرأس (تكرار علاج)، كل
    تطبيق يبقى معزولاً بمهامه الخاصة — بنفس منطق (source_type, source_id)
    اللي يميّز الدفعات ببند 50."""
    animal = make_animal(animal_no="PR-05")
    med = make_pharmacy(name="دواء", withdrawal_days=0)
    protocol = _make_protocol(steps=[(0, "خطوة", med, 1, "vaccination")])

    app1 = protocol_service.apply_protocol(
        protocol, animal_id=animal.id, start_date=date.today(), actor_user_id=1,
    )
    app2 = protocol_service.apply_protocol(
        protocol, animal_id=animal.id, start_date=date.today() + timedelta(days=30), actor_user_id=1,
    )

    assert len(protocol_service.protocol_application_tasks(app1)) == 1
    assert len(protocol_service.protocol_application_tasks(app2)) == 1
    assert Task.query.filter_by(source_type="ProtocolApplication").count() == 2
