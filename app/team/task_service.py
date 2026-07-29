"""
محرك المهام — نقطة الدخول الموحّدة لإنشاء وإدارة المهام، يدوية أو مقترحة
تلقائياً. أي جزء ثاني بالنظام يحتاج يولّد مهمة (محرك دورة الإنتاج، خطة
العزل...) يستدعي `create_suggested_task` أو `assign_task` من هنا، بدل ما
يكتب صف بجدول Tasks مباشرة.
"""
from datetime import date, datetime, timedelta, timezone
from app.extensions import db
from app.models import Task, AuditLog


def _now():
    return datetime.now(timezone.utc)


# أسباب تعذّر تنفيذ مهمة (بند إضافي 54) — قائمة مقفلة بدل نص حر، عشان
# تصير قابلة للتصفية والتقارير لاحقاً (مين يتكرر معه نقص الأدوات مثلاً).
FAILURE_REASONS = [
    "نقص الأدوات",
    "نقص العلف",
    "نقص الماء",
    "الحيوان غير موجود",
    "خطر يمنع التنفيذ",
    "تعليمات غير واضحة",
    "مهمة عاجلة أخرى",
    "سبب آخر",
]


class TaskPermissionError(Exception):
    pass


class TaskStateError(Exception):
    pass


def assign_task(*, actor, title, task_type="custom", assignee_id=None, barn_id=None,
                 animal_id=None, due_date=None, requires_photo=False, notes=None,
                 depends_on_task_id=None, target_role=None) -> Task:
    """تعيين مهمة مباشر من الدكتور/المالك — بدون مرحلة اقتراح."""
    if not actor.has_permission("tasks.assign_any"):
        raise TaskPermissionError("ما تملك صلاحية توزيع المهام.")
    if not assignee_id and barn_id:
        from app.models import Barn
        barn = Barn.query.get(barn_id)
        assignee_id = barn.responsible_worker_id if barn else None
    task = Task(
        title=title, task_type=task_type, status="pending",
        assignee_id=assignee_id, barn_id=barn_id, animal_id=animal_id,
        due_date=due_date, requires_photo=requires_photo, notes=notes,
        created_by_id=actor.id, depends_on_task_id=depends_on_task_id or None,
        target_role=target_role or None,
    )
    db.session.add(task)
    db.session.flush()
    db.session.add(AuditLog(actor_user_id=actor.id, action="task.assign",
                             entity_type="Task", entity_id=task.id))
    db.session.commit()
    return task


def create_suggested_task(*, title, task_type, barn_id=None, animal_id=None, due_date=None,
                           requires_photo=False, source_type=None, source_id=None, notes=None,
                           sort_order=0, target_role=None) -> Task:
    """مهمة تتولّد تلقائياً من النظام (محرك الدورة، خطة العزل...) — تحتاج
    مراجعة الدكتور قبل ما توصل للعامل."""
    assignee_id = None
    if barn_id:
        from app.models import Barn
        barn = Barn.query.get(barn_id)
        assignee_id = barn.responsible_worker_id if barn else None
    task = Task(
        title=title, task_type=task_type, status="suggested",
        assignee_id=assignee_id, barn_id=barn_id, animal_id=animal_id,
        due_date=due_date, requires_photo=requires_photo, notes=notes,
        source_type=source_type, source_id=source_id, sort_order=sort_order,
        target_role=target_role or None,
    )
    db.session.add(task)
    db.session.commit()
    return task


def approve_suggested_task(task: Task, *, actor) -> Task:
    if not actor.has_permission("tasks.review_daily"):
        raise TaskPermissionError("ما تملك صلاحية مراجعة المهام اليومية.")
    if task.status != "suggested":
        raise TaskStateError("هذي المهمة مو بحالة اقتراح.")
    task.status = "pending"
    task.reviewed_by_id = actor.id
    db.session.add(AuditLog(actor_user_id=actor.id, action="task.approve",
                             entity_type="Task", entity_id=task.id))
    db.session.commit()
    return task


def postpone_suggested_task(task: Task, *, actor, new_due_date) -> Task:
    if not actor.has_permission("tasks.review_daily"):
        raise TaskPermissionError("ما تملك صلاحية مراجعة المهام اليومية.")
    if task.status != "suggested":
        raise TaskStateError("هذي المهمة مو بحالة اقتراح.")
    task.due_date = new_due_date
    task.reviewed_by_id = actor.id
    db.session.add(AuditLog(actor_user_id=actor.id, action="task.postpone",
                             entity_type="Task", entity_id=task.id))
    db.session.commit()
    return task


def soft_delete_suggested_task(task: Task, *, actor, reason=None) -> Task:
    """حذف من الدكتور — مو نهائي، يتحوّل لصندوق مراجعة صاحب الحلال."""
    if not actor.has_permission("tasks.review_daily"):
        raise TaskPermissionError("ما تملك صلاحية مراجعة المهام اليومية.")
    if task.status != "suggested":
        raise TaskStateError("هذي المهمة مو بحالة اقتراح.")
    task.status = "deleted_pending_review"
    task.reviewed_by_id = actor.id
    task.notes = ((task.notes + " | ") if task.notes else "") + (reason or "")
    db.session.add(AuditLog(actor_user_id=actor.id, action="task.soft_delete",
                             entity_type="Task", entity_id=task.id, details=reason))
    db.session.commit()
    return task


def owner_restore_task(task: Task, *, actor) -> Task:
    if not actor.has_permission("tasks.delete_final"):
        raise TaskPermissionError("الاسترجاع حصري لصاحب الحلال.")
    if task.status != "deleted_pending_review":
        raise TaskStateError("هذي المهمة مو بصندوق المراجعة.")
    task.status = "suggested"
    db.session.add(AuditLog(actor_user_id=actor.id, action="task.owner_restore",
                             entity_type="Task", entity_id=task.id))
    db.session.commit()
    return task


def owner_delete_task_final(task: Task, *, actor) -> None:
    if not actor.has_permission("tasks.delete_final"):
        raise TaskPermissionError("الحذف النهائي حصري لصاحب الحلال.")
    if task.status != "deleted_pending_review":
        raise TaskStateError("الحذف النهائي بس للمهام اللي بصندوق المراجعة.")
    db.session.add(AuditLog(actor_user_id=actor.id, action="task.delete_final",
                             entity_type="Task", entity_id=task.id))
    db.session.delete(task)
    db.session.commit()


def batch_siblings(task: Task) -> list[Task]:
    """كل المهام اللي تشترك بنفس (source_type, source_id) — بقرارك
    الصريح (بند إضافي 50)، هذا اللي يمثّل "الدفعة" بالواجهة بدون نموذج
    بيانات جديد. لو المهمة مالها مصدر مشترك، ترجع لحالها فقط."""
    if not task.source_type or not task.source_id:
        return [task]
    return (Task.query.filter_by(source_type=task.source_type, source_id=task.source_id)
            .order_by(Task.id).all())


def task_rich_context(task: Task) -> dict:
    """التفصيل الشامل للمهمة (بند إضافي 50): سبب المهمة، الدفعة/الحظيرة/
    عدد الرؤوس، الدواء والجرعة الإجمالية، حالة المخزون الحالي والمتوقع
    بعد التنفيذ، والمهمة التالية بسلسلة الأتمتة."""
    from app.models import FarmSettings

    siblings = batch_siblings(task)
    ctx = {
        "reason": task.notes,
        "barn": task.barn,
        "head_count": len(siblings),
        "siblings": siblings,
        "next_action": None,
    }
    if task.planned_pharmacy_id and task.planned_pharmacy:
        pharmacy = task.planned_pharmacy
        total_quantity = sum(s.planned_quantity or 0 for s in siblings)
        stock_now = pharmacy.available_qty or 0
        ctx.update({
            "pharmacy": pharmacy,
            "quantity_per_head": task.planned_quantity,
            "total_quantity": total_quantity,
            "stock_now": stock_now,
            "stock_after": stock_now - total_quantity,
            "stock_insufficient": (stock_now - total_quantity) < 0,
            "next_action": (
                f"بعد تأكيد التنفيذ: تُجدوَل مهمة إعادة وزن تلقائية بعد "
                f"{FarmSettings.get().reweigh_followup_days} يوماً للتأكد من استجابة العلاج."
            ),
        })
    return ctx


def complete_task_via_treatment(task: Task, *, actor) -> Task:
    """إنجاز مباشر لمهمة "علاج مخطَّط" عند تأكيد التنفيذ الفعلي بشاشة
    التسجيل الطبي (بند إضافي 50) — بدون قيد "المهمة معيّنة لك" الصارم
    اللي بـ`complete_task()` العادية: الفعل الحقيقي هنا (سجل طبي حقيقي
    بصلاحية health.manage، والدكتور غالباً مو نفس العامل المكلَّف بالمهمة)
    هو الحاسم، لا تطابق المكلَّف."""
    task.status = "done"
    task.completed_at = _now()
    task.completion_note = "أُنجزت تلقائياً عند تأكيد تنفيذ العلاج المخطَّط."
    db.session.add(AuditLog(actor_user_id=actor.id, action="task.complete_via_treatment",
                             entity_type="Task", entity_id=task.id))
    db.session.commit()
    return task


def schedule_reweigh_followup(task: Task, *, actor) -> Task | None:
    """مهلة إعادة الوزن بعد العلاج (بند إضافي 50) — تُنشأ فقط لحظة
    "تأكيد التنفيذ" الفعلية (تحويل مهمة العلاج لحالة منجزة)، فتبدأ تُحسب
    من هناك بالضبط، لا من لحظة اقتراح المهمة أو خطة العلاج."""
    from app.models import FarmSettings

    if not task.animal_id:
        return None
    days = FarmSettings.get().reweigh_followup_days
    return create_suggested_task(
        title=f'⚖️ إعادة وزن متابعة بعد علاج "{task.title}"',
        task_type="reweigh_followup",
        animal_id=task.animal_id, barn_id=task.barn_id,
        due_date=date.today() + timedelta(days=days),
        source_type="TreatmentFollowUp", source_id=task.id,
        notes=f"متابعة استجابة العلاج المنفَّذ بالمهمة #{task.id} — يتأكد الوزن تحسّن بعد التنفيذ.",
    )


def _check_not_locked(task: Task) -> None:
    """تسلسل المهام (بند 21) — مهمة عندها 'مهمة سابقة' ما تُبدأ ولا تُنجز
    لين السابقة تصير status=done."""
    if task.depends_on_task_id and task.depends_on and task.depends_on.status != "done":
        raise TaskStateError(f"لازم تكمل المهمة السابقة أولاً: \"{task.depends_on.title}\"")


def _duration_minutes_since_start(task: Task, end_time) -> int | None:
    """مدة التنفيذ الفعلية بالدقائق من `started_at` — None لو المهمة
    اتنجزت/تعذّرت بدون ما تمر بمرحلة "بدء" (نادر، بس ممكن)."""
    if not task.started_at:
        return None
    started = task.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return max(0, round((end_time - started).total_seconds() / 60))


def start_task(task: Task, *, actor) -> Task:
    if task.assignee_id != actor.id:
        raise TaskPermissionError("هذي المهمة مو معيّنة لك.")
    if task.status != "pending":
        raise TaskStateError("المهمة مو جاهزة للبدء.")
    _check_not_locked(task)
    task.status = "in_progress"
    task.started_at = _now()
    task.accepted_by_id = actor.id
    task.server_time_source = "server"
    db.session.commit()
    return task


def complete_task(task: Task, *, actor, note=None, evidence_image_url=None, voice_note_url=None) -> Task:
    if task.assignee_id != actor.id:
        raise TaskPermissionError("هذي المهمة مو معيّنة لك.")
    if task.status not in ("pending", "in_progress"):
        raise TaskStateError("المهمة مو جاهزة للإنجاز.")
    _check_not_locked(task)
    if task.requires_photo and not evidence_image_url:
        raise TaskStateError("هذي المهمة تتطلب إرفاق صورة.")
    now = _now()
    task.status = "done"
    task.completed_at = now
    task.completion_note = note
    task.completion_evidence_image_url = evidence_image_url
    task.voice_note_url = voice_note_url
    task.duration_minutes = _duration_minutes_since_start(task, now)
    task.server_time_source = "server"
    db.session.add(AuditLog(actor_user_id=actor.id, action="task.complete",
                             entity_type="Task", entity_id=task.id))

    if task.task_type == "move_to_pregnant_barn" and task.animal_id:
        _move_to_pregnant_barn(task)

    db.session.commit()
    return task


def _move_to_pregnant_barn(task: Task) -> None:
    """نقل فعلي لحظيرة الحوامل (بند إضافي، 2026-07-28) — يُنفَّذ فقط
    عند إنجاز مهمة "نقل لحظيرة الحوامل" نفسها (نفس نمط
    `complete_task_via_treatment`: إجراء خاص يشغّله إنجاز نوع مهمة
    معيّن)، بعد ما العزل والفحص خلصا فعلياً حسب تقدير الدكتور/المالك."""
    from app.models import Barn

    barn = Barn.query.filter_by(barn_type="حوامل").order_by(Barn.id).first()
    if not barn:
        return
    task.animal.barn_id = barn.id
    db.session.add(task.animal)


def fail_task(task: Task, *, actor, reason, note=None, evidence_image_url=None, voice_note_url=None) -> Task:
    """تعذّر تنفيذ المهمة (بند إضافي 54) — بدل ما يظل العامل صامتاً أو
    يضغط "بدء" بلا أي أثر، يسجّل صراحة إنه ما قدر ينجزها وليش، بسبب من
    قائمة مقفلة (`FAILURE_REASONS`) عشان تصير قابلة للمتابعة والتحليل."""
    if task.assignee_id != actor.id:
        raise TaskPermissionError("هذي المهمة مو معيّنة لك.")
    if task.status not in ("pending", "in_progress"):
        raise TaskStateError("المهمة مو بحالة تسمح بتسجيل التعذّر.")
    _check_not_locked(task)
    if reason not in FAILURE_REASONS:
        raise TaskStateError("سبب التعذّر غير معروف.")
    now = _now()
    task.status = "failed"
    task.failed_at = now
    task.failure_reason = reason
    task.completion_note = note
    task.completion_evidence_image_url = evidence_image_url
    task.voice_note_url = voice_note_url
    task.duration_minutes = _duration_minutes_since_start(task, now)
    task.server_time_source = "server"
    db.session.add(AuditLog(actor_user_id=actor.id, action="task.fail",
                             entity_type="Task", entity_id=task.id, details=reason))
    db.session.commit()
    return task
