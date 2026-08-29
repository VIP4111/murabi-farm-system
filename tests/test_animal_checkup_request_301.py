"""بند إضافي 301 — طلبك: "مهام يومية لنعجة مختارة من نظام مهام مضاعفة
مثل افحص نعجة رقم خمس ورفع تقرير". كل بند فحص تختاره يصير مهمة مستقلة
مربوطة ببعض بنفس آلية الدفعة الموجودة أصلاً (source_type/source_id)،
بدون أي جدول جديد."""
from unittest.mock import patch

from app.extensions import db
from app.team import task_service
from app.models import Role, User, Task, AuditLog
from factories import make_animal, make_barn


def _make_doctor(phone="0599999210"):
    role = Role.query.filter_by(name="doctor").first()
    user = User(name="دكتور اختبار", phone=phone, role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_assign_animal_checkup_creates_one_task_per_item(app, owner):
    animal = make_animal(animal_no="405")
    tasks = task_service.assign_animal_checkup(
        actor=owner, animal=animal, items=["فحص الحرارة والنبض", "فحص الشهية والحالة العامة"],
    )
    assert len(tasks) == 2
    assert all(t.animal_id == animal.id for t in tasks)
    assert all(t.task_type == "animal_checkup" for t in tasks)


def test_checkup_tasks_share_same_batch_source(app, owner):
    animal = make_animal(animal_no="406")
    tasks = task_service.assign_animal_checkup(
        actor=owner, animal=animal, items=["بند أول", "بند ثاني", "بند ثالث"],
    )
    source_ids = {t.source_id for t in tasks}
    assert len(source_ids) == 1  # كلهم نفس الدفعة
    siblings = task_service.batch_siblings(tasks[0])
    assert len(siblings) == 3


def test_assign_to_specific_doctor(app, owner):
    doctor = _make_doctor()
    animal = make_animal(animal_no="407")
    tasks = task_service.assign_animal_checkup(
        actor=owner, animal=animal, items=["فحص الجلد والصوف (طفيليات خارجية)"], assignee_id=doctor.id,
    )
    assert tasks[0].assignee_id == doctor.id


def test_no_assignee_uses_target_role_doctor(app, owner):
    animal = make_animal(animal_no="408")
    tasks = task_service.assign_animal_checkup(
        actor=owner, animal=animal, items=["فحص العين والأنف"], target_role="doctor",
    )
    assert tasks[0].assignee_id is None
    assert tasks[0].target_role == "doctor"


def test_target_role_doctor_not_overridden_by_barn_responsible_worker(app, owner):
    """بند إضافي 308 — فجوة اكتُشفت بالتدقيق: `assign_animal_checkup`
    بعد إعادة استخدام `assign_task()` (لاستعادة سجل AuditLog وإشعار
    تيليجرام الفائتين) لازم تبقى تحترم "أي دكتور متاح" (target_role)
    ولا تسقط بالغلط لعامل الحظيرة المسؤول العادي (اللي غالباً مو دكتور)
    — نفس منطق `assign_task`'s barn fallback يشتغل بس لو `assignee_id`
    فاضي و`barn_id` معبّى، وهذا بالضبط سيناريو طلب فحص بدون تعيين شخص."""
    worker_role = Role.query.filter_by(name="worker").first()
    barn_worker = User(name="عامل الحظيرة", phone="0599999220", role_id=worker_role.id)
    barn_worker.set_password("pass1234")
    db.session.add(barn_worker)
    db.session.commit()

    barn = make_barn(barn_no="B-CHECKUP", responsible_worker_id=barn_worker.id)
    animal = make_animal(animal_no="415", barn_id=barn.id)

    tasks = task_service.assign_animal_checkup(
        actor=owner, animal=animal, items=["فحص العين والأنف"], target_role="doctor",
    )
    assert tasks[0].assignee_id != barn_worker.id
    assert tasks[0].assignee_id is None
    assert tasks[0].target_role == "doctor"


def test_checkup_tasks_are_audited_and_notify_assignee(app, owner):
    """بند إضافي 308 — النسخة الأصلية كانت تبني صفوف Task يدوياً بدل
    استدعاء assign_task()، وفوّتت بالغلط سجل AuditLog وإشعار تيليجرام
    الفوري اللي كل مهمة ثانية بالنظام تحصل عليها تلقائياً."""
    doctor = _make_doctor(phone="0599999221")
    doctor.telegram_chat_id = "555"
    db.session.commit()
    animal = make_animal(animal_no="416")

    with patch("app.core.telegram_service.notify_user") as mock_notify:
        tasks = task_service.assign_animal_checkup(
            actor=owner, animal=animal, items=["فحص الشهية والحالة العامة"], assignee_id=doctor.id,
        )

    audit_rows = AuditLog.query.filter_by(action="task.assign", entity_type="Task", entity_id=tasks[0].id).all()
    assert len(audit_rows) == 1
    assert audit_rows[0].actor_user_id == owner.id
    mock_notify.assert_called_once()
    assert mock_notify.call_args[0][0].id == doctor.id


def test_rejects_empty_item_list(app, owner):
    animal = make_animal(animal_no="409")
    try:
        task_service.assign_animal_checkup(actor=owner, animal=animal, items=["", "   "])
        assert False, "لازم يرفع استثناء"
    except task_service.TaskStateError:
        pass


def test_rejects_actor_without_assign_permission(app):
    worker_role = Role.query.filter_by(name="worker").first()
    worker = User(name="عامل اختبار", phone="0599999211", role_id=worker_role.id)
    worker.set_password("pass1234")
    db.session.add(worker)
    db.session.commit()

    animal = make_animal(animal_no="410")
    try:
        task_service.assign_animal_checkup(actor=worker, animal=animal, items=["فحص"])
        assert False, "لازم يرفع استثناء"
    except task_service.TaskPermissionError:
        pass


def test_doctor_completing_each_item_writes_separate_report_note(app, owner):
    """إنجاز كل بند بملاحظته المستقلة هو فعلياً "التقرير" اللي طلبه
    المالك — بدون أي نموذج تقرير منفصل."""
    doctor = _make_doctor(phone="0599999212")
    animal = make_animal(animal_no="411")
    tasks = task_service.assign_animal_checkup(
        actor=owner, animal=animal, items=["فحص الحرارة والنبض", "فحص الخف/الحافر"], assignee_id=doctor.id,
    )
    task_service.complete_task(tasks[0], actor=doctor, note="حرارة طبيعية 39.2")
    task_service.complete_task(tasks[1], actor=doctor, note="خف سليم بدون التهاب")

    db.session.refresh(tasks[0])
    db.session.refresh(tasks[1])
    assert tasks[0].completion_note == "حرارة طبيعية 39.2"
    assert tasks[1].completion_note == "خف سليم بدون التهاب"
    assert tasks[0].status == "done"
    assert tasks[1].status == "done"


# ---- الراوت ----

def test_checkup_request_route_requires_permission(app, client):
    worker_role = Role.query.filter_by(name="worker").first()
    worker = User(name="عامل اختبار", phone="0599999213", role_id=worker_role.id)
    worker.set_password("pass1234")
    db.session.add(worker)
    db.session.commit()
    animal = make_animal(animal_no="412")

    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.post(f"/animals/{animal.id}/checkup-request", data={"items": ["فحص"]})
    assert resp.status_code == 403


def test_owner_can_request_checkup_via_route(app, client, owner):
    animal = make_animal(animal_no="413")
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.post(
        f"/animals/{animal.id}/checkup-request",
        data={"items": ["فحص الحرارة والنبض", "فحص الخراجات أو الكتل الظاهرة"], "custom_item": "فحص إضافي حر"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    tasks = Task.query.filter_by(animal_id=animal.id, task_type="animal_checkup").all()
    assert len(tasks) == 3
