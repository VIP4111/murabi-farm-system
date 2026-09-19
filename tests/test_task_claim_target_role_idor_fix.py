"""فحص شامل سطر بسطر — ميزة المهام: ثغرة IDOR حقيقية بمنطق "المسك
التلقائي" لمهمة مشتركة بلا عامل محدَّد.

قبل الإصلاح: `_claim_if_unassigned()` كانت تنسب أي مهمة غير معيَّنة
(assignee_id=None) لأول مستخدم يضغط "بدء/إنجاز/فشل" لها، بدون أي تحقق
من `target_role` — يعني عامل عادي يقدر يمسك وينفّذ مهمة موجَّهة صراحة
لدور "دكتور" (أو أي دور ثانٍ) لو عرف رقم المهمة، متجاوزاً تصنيف
الأدوار بالكامل رغم إن شاشة القائمة نفسها تُخفي هذي المهمة عنه أصلاً
(فلترة عرض بس، بدون حارس فعلي بالخدمة)."""
from app.extensions import db
from app.models import Role, User
from app.team import task_service
from app.team.task_service import TaskPermissionError


def _make_user(name, phone, role_name):
    role = Role.query.filter_by(name=role_name).first()
    user = User(name=name, phone=phone, role_id=role.id, language="ar", is_active_account=True)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_worker_cannot_claim_task_targeted_at_doctor_role(app, owner):
    worker = _make_user("عامل", "0599999500", "worker")
    task = task_service.assign_task(actor=owner, title="مهمة دكتور", target_role="doctor")
    assert task.assignee_id is None

    try:
        task_service.start_task(task, actor=worker)
        assert False, "عامل ما يفترض يقدر يمسك مهمة موجَّهة لدور (دكتور)"
    except TaskPermissionError:
        pass

    db.session.refresh(task)
    assert task.assignee_id is None, "المهمة ما يفترض تُنسب للعامل بعد محاولة مرفوضة"
    assert task.status == "pending"


def test_doctor_can_still_claim_task_targeted_at_doctor_role(app, owner):
    doctor = _make_user("دكتور", "0599999501", "doctor")
    task = task_service.assign_task(actor=owner, title="مهمة دكتور", target_role="doctor")

    started = task_service.start_task(task, actor=doctor)
    assert started.assignee_id == doctor.id
    assert started.status == "in_progress"


def test_task_without_target_role_still_claimable_by_anyone(app, owner):
    """مهمة بلا target_role (زي قبل الإصلاح تماماً) لازم تفضل تُنسب
    لأول من يضغط "بدء" — ما نغيّر هذا السلوك الأصلي."""
    worker = _make_user("عامل بدون تخصيص", "0599999502", "worker")
    task = task_service.assign_task(actor=owner, title="مهمة عامة")

    started = task_service.start_task(task, actor=worker)
    assert started.assignee_id == worker.id
    assert started.status == "in_progress"
