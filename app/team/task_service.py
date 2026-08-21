"""
محرك المهام — نقطة الدخول الموحّدة لإنشاء وإدارة المهام، يدوية أو مقترحة
تلقائياً. أي جزء ثاني بالنظام يحتاج يولّد مهمة (محرك دورة الإنتاج، خطة
العزل...) يستدعي `create_suggested_task` أو `assign_task` من هنا، بدل ما
يكتب صف بجدول Tasks مباشرة.
"""
from datetime import date, datetime, timedelta, timezone
from flask_babel import lazy_gettext as _l
from app.extensions import db
from app.models import Task, AuditLog


def _now():
    return datetime.now(timezone.utc)


# أسباب تعذّر تنفيذ مهمة (بند إضافي 54) — قائمة مقفلة بدل نص حر، عشان
# تصير قابلة للتصفية والتقارير لاحقاً (مين يتكرر معه نقص الأدوات مثلاً).
# القيمة المخزّنة بـTask.failure_reason تبقى عربي دايماً (نفس مفتاح
# القائمة) — بند 74 أضاف FAILURE_REASON_LABELS بس للعرض المترجم
# بالواجهة، بدون ما يغيّر شكل البيانات المخزّنة.
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

FAILURE_REASON_LABELS = {
    "نقص الأدوات": _l("نقص الأدوات"),
    "نقص العلف": _l("نقص العلف"),
    "نقص الماء": _l("نقص الماء"),
    "الحيوان غير موجود": _l("الحيوان غير موجود"),
    "خطر يمنع التنفيذ": _l("خطر يمنع التنفيذ"),
    "تعليمات غير واضحة": _l("تعليمات غير واضحة"),
    "مهمة عاجلة أخرى": _l("مهمة عاجلة أخرى"),
    "سبب آخر": _l("سبب آخر"),
}


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

    # إشعار فوري مجاني عبر تيليجرام (بند إضافي 157) — يتجاهل بصمت لو
    # العامل ما سجّل Chat ID أو البوت غير مفعَّل (صفر كسر بالتوزيع نفسه).
    if task.assignee_id:
        from app.core import telegram_service
        telegram_service.notify_user(
            task.assignee, f"📋 مهمة جديدة: {task.title}" + (f"\nالموعد: {task.due_date}" if task.due_date else ""),
        )
    return task


def create_suggested_task(*, title, task_type, barn_id=None, animal_id=None, due_date=None,
                           requires_photo=False, source_type=None, source_id=None, notes=None,
                           sort_order=0, target_role=None, auto_approve=False) -> Task:
    """مهمة تتولّد تلقائياً من النظام (محرك الدورة، خطة العزل...) — تحتاج
    مراجعة الدكتور قبل ما توصل للعامل، إلا لو `auto_approve=True` (بند
    إضافي 107 — المهام اليومية الروتينية تحديداً: تنظيف/سقاية/فحص عام،
    ما فيها قرار طبي يستاهل انتظار مراجعة، وتعطيلها كان يعني العامل ما
    يشوف حتى المهام الأساسية لو الدكتور غاب يوم)."""
    assignee_id = None
    if barn_id:
        from app.models import Barn
        barn = Barn.query.get(barn_id)
        assignee_id = barn.responsible_worker_id if barn else None
    task = Task(
        title=title, task_type=task_type, status="pending" if auto_approve else "suggested",
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

    # خلطة العلف المقترحة لليوم (بند إضافي 134) — معاينة قبل الإنجاز
    # عشان العامل يعرف شنو ويش كمية يجيب فعلياً من المخزن قبل ما يضغط
    # "تم"، مو مفاجأة بعد الخصم. نفس الحساب اللي يشتغل فعلياً وقت
    # `complete_task` (`_distribute_barn_feed`) — بس هنا مجرد عرض بدون
    # أي خصم أو تسجيل حركة.
    if task.task_type == "feeding_schedule" and task.barn_id:
        from app.feed import feed_service as feed_svc
        ctx["feeding_blend"] = feed_svc.barn_daily_blend(barn_id=task.barn_id)

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

    if task.task_type == "protocol_step":
        _maybe_close_protocol_application(task)
    if task.task_type == "isolation_check":
        _maybe_close_isolation_plan(task)

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


def _claim_if_unassigned(task: Task, actor) -> None:
    """مهمة يومية مشتركة بلا عامل محدد (بند إضافي 107 — تولّد بدون
    `assignee_id`، تظهر لكل عمال نفس الدور عبر `target_role`) تُنسب
    تلقائياً لأول عامل يبدأها فعلياً — نفس منطق لوحة مهام مشتركة، أول
    وحد يمسكها يصير مسؤولها."""
    if task.assignee_id is None:
        task.assignee_id = actor.id


def start_task(task: Task, *, actor) -> Task:
    _claim_if_unassigned(task, actor)
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


def complete_task(task: Task, *, actor, note=None, evidence_image_url=None, voice_note_url=None,
                   barn_id=None) -> Task:
    _claim_if_unassigned(task, actor)
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
        _move_to_pregnant_barn(task, chosen_barn_id=barn_id)

    if task.task_type == "barn_physiology_move" and task.animal_id:
        _move_barn_physiology(task, chosen_barn_id=barn_id)

    if task.task_type == "feeding_schedule" and task.barn_id:
        _distribute_barn_feed(task)

    if task.task_type == "protocol_step":
        _maybe_close_protocol_application(task)

    if task.task_type == "isolation_check":
        _maybe_close_isolation_plan(task)

    db.session.commit()
    return task


def _maybe_close_isolation_plan(task: Task) -> None:
    """إغلاق تلقائي لخطة العزل بعد الولادة (بند إضافي 102) — قبل هذا،
    `start_isolation_plan` (بند 4) كانت تولّد سلسلة مهام "فحص عزل يومي"
    (`isolation_check`) بعدد أيام العزل المضبوط بالإعدادات، وتتوقف
    السلسلة بصمت بعد آخر يوم — ما فيه أي مهمة ختامية تؤكد إن العزل خلص
    فعلياً وصار آمن يخلط الأم والمولود بباقي القطيع.

    تُستدعى فقط لما آخر مهمة `isolation_check` بنفس `source_id`
    (المولود) توصل لحالة نهائية. مقيَّدة بـ`task_type == "isolation_check"`
    بس (يُتحقَّق منه بمكان الاستدعاء) عشان مهمة التأكيد نفسها ما تعيد
    تشغيل هذا المنطق."""
    if task.source_type != "IsolationPlan" or not task.source_id:
        return
    remaining_open = Task.query.filter(
        Task.source_type == "IsolationPlan", Task.source_id == task.source_id,
        Task.task_type == "isolation_check", Task.id != task.id,
        Task.status.in_(OPEN_TASK_STATUSES),
    ).count()
    if remaining_open:
        return
    from app.models import Animal
    newborn = Animal.query.get(task.source_id)
    if not newborn:
        return
    mother = newborn.mother
    title = f"✅ تأكيد انتهاء العزل — جاهز للاختلاط بالقطيع — {newborn.animal_no}"
    if mother:
        title += f" وأمه {mother.animal_no}"
    create_suggested_task(
        title=title,
        task_type="isolation_release_check",
        barn_id=task.barn_id, animal_id=newborn.id,
        due_date=date.today(),
        source_type="IsolationPlan", source_id=newborn.id,
        notes="كل أيام العزل اليومية المجدولة اكتملت (منجزة/فاشلة/ملغاة) — "
              "تأكد الأم والمولود بصحة جيدة قبل ما تنقلهم من حظيرة العزل.",
    )


def _maybe_close_protocol_application(task: Task) -> None:
    """إغلاق تلقائي لتطبيق بروتوكول العلاج (بند إضافي 101) — قبل هذا،
    `apply_protocol` كان يولّد مهمة مستقلة لكل خطوة (بند 52)، بدون أي
    كود يفحص هل كل الخطوات خلصت — البروتوكول ينتهي بصمت بلا أي تقييم
    لفعالية العلاج ولا حتى إغلاق فعلي لـ`ProtocolApplication` نفسه.
    تُستدعى فقط لما آخر خطوة `protocol_step` بنفس التطبيق توصل لحالة
    نهائية (منجزة/فاشلة/ملغاة — أي حالة برة `OPEN_TASK_STATUSES`)،
    فتنشئ مهمة مقترحة واحدة "تقييم فعالية العلاج" بعد يومين. مقيَّدة
    بـ`task_type == "protocol_step"` بس (يُتحقَّق منه بمكان الاستدعاء)
    عشان مهمة التقييم نفسها (لها نفس source_type/source_id) ما تعيد
    تشغيل هذا المنطق لما تُنجَز."""
    if task.source_type != "ProtocolApplication" or not task.source_id:
        return
    remaining_open = Task.query.filter(
        Task.source_type == "ProtocolApplication", Task.source_id == task.source_id,
        Task.id != task.id, Task.status.in_(OPEN_TASK_STATUSES),
    ).count()
    if remaining_open:
        return
    from app.models import ProtocolApplication
    application = ProtocolApplication.query.get(task.source_id)
    if not application:
        return
    animal = application.animal
    create_suggested_task(
        title=f'📋 تقييم فعالية العلاج — {application.protocol.name}'
              + (f' — {animal.animal_no}' if animal else ''),
        task_type="protocol_effectiveness_review",
        barn_id=animal.barn_id if animal else None,
        animal_id=application.animal_id,
        due_date=date.today() + timedelta(days=2),
        source_type="ProtocolApplication", source_id=application.id,
        notes=f'كل خطوات بروتوكول "{application.protocol.name}" اكتملت (منجزة/فاشلة/ملغاة) — '
              "راجع استجابة الرأس للعلاج ووثّق النتيجة.",
    )


def _move_to_pregnant_barn(task: Task, *, chosen_barn_id=None) -> None:
    """نقل فعلي لحظيرة الحوامل (بند إضافي، 2026-07-28، صار قابلاً لاختيار
    حظيرة بديلة + رفض واضح بند إضافي 217) — يُنفَّذ فقط عند إنجاز مهمة
    "نقل لحظيرة الحوامل" نفسها، بعد ما العزل والفحص خلصا فعلياً حسب
    تقدير الدكتور/المالك.

    **إصلاح بند 217**: قبل هذا البند، لو ما فيه حظيرة "حوامل" أصلاً،
    الدالة ترجع بصمت والمهمة تظل تتعلّم "منجزة" رغم إن الحيوان ما انتقل
    فعلياً — نجاح كاذب. الحين لو ما فيه حظيرة (ولا اختار العامل بديلة)،
    نرفع خطأ صريح قبل ما `complete_task` يعلّم المهمة منجزة، فتبقى
    مفتوحة لين تتوفر حظيرة فعلية."""
    from app.models import Barn

    if chosen_barn_id:
        barn = Barn.query.get(chosen_barn_id)
        if barn:
            task.animal.barn_id = barn.id
            db.session.add(task.animal)
            return

    barn = Barn.query.filter_by(barn_type="حوامل").order_by(Barn.id).first()
    if not barn:
        raise TaskStateError(
            'ما فيه حظيرة بنوع "حوامل" بالنظام — أنشئها من شاشة الحظائر '
            "أولاً، أو اختر حظيرة بديلة من فورم إنجاز المهمة."
        )
    task.animal.barn_id = barn.id
    db.session.add(task.animal)


def _move_barn_physiology(task: Task, *, chosen_barn_id=None) -> None:
    """نقل فعلي حسب الحالة الفسيولوجية (بند إضافي 133، صار قابلاً
    لاختيار حظيرة بديلة ببند إضافي 216) — نفس نمط `_move_to_pregnant_barn`
    بالضبط، بس عام لأي نوع حظيرة مشفَّر داخل `source_type`
    (`barn_physiology_service._source_type`) بدل نوع واحد مثبَّت. يُنفَّذ
    فقط عند إنجاز المهمة نفسها — بانتظار تقدير الدكتور/العامل، مو نقل
    صامت وقت التوليد.

    `chosen_barn_id` (بند 216): العامل ينقل الرأس فعلياً وممكن يحطه
    بحظيرة غير المقترحة (مثلاً المقترحة مليانة) — لو مرّر رقم حظيرة
    صريح وقت إنجاز المهمة، ينقله لها بدل الحظيرة المشتقة من
    `source_type` تلقائياً، طالما الحظيرة موجودة فعلاً.

    **إصلاح بند 219**: نفس ثغرة `_move_to_pregnant_barn` بالضبط كانت
    موجودة هنا (اكتشفها فحص شامل ثانٍ) — لو الحظيرة الهدف (أو
    `chosen_barn_id` نفسه) غير موجودة، الدالة كانت ترجع بصمت والمهمة
    تتعلّم "منجزة" رغم إن الرأس ما انتقل. الحين ترفع خطأ صريح قبل
    الـcommit، فتبقى المهمة مفتوحة."""
    from app.models import Barn

    if chosen_barn_id:
        barn = Barn.query.get(chosen_barn_id)
        if barn:
            task.animal.barn_id = barn.id
            db.session.add(task.animal)
            return
        raise TaskStateError("الحظيرة اللي اخترتها غير موجودة — تأكد من اختيارك.")

    if not task.source_type or ":" not in task.source_type:
        raise TaskStateError("تعذّر تحديد الحظيرة الهدف لهذي المهمة (بيانات مصدر ناقصة) — راجع الدعم الفني.")
    target_barn_type = task.source_type.split(":", 1)[1]
    barn = Barn.query.filter_by(barn_type=target_barn_type).order_by(Barn.id).first()
    if not barn:
        raise TaskStateError(
            f'ما فيه حظيرة بنوع "{target_barn_type}" بالنظام — أنشئها من شاشة الحظائر '
            "أولاً، أو اختر حظيرة بديلة من فورم إنجاز المهمة."
        )
    task.animal.barn_id = barn.id
    db.session.add(task.animal)


def _distribute_barn_feed(task: Task) -> None:
    """توزيع العلف الفعلي (بند إضافي 134) — يُنفَّذ فقط عند إنجاز مهمة
    "وجبة علف" (`feeding_schedule`، بند 131) نفسها، نفس نمط
    `_move_to_pregnant_barn` بالضبط: العامل يضغط "تم" بعد ما يوزّع
    العلف فعلياً بالحظيرة، وهذي اللحظة بالضبط هي اللي يحسب فيها النظام
    خلطة اليوم المجمَّعة لكل رؤوس الحظيرة (`feed_service.barn_daily_blend`
    — نفس موازِن العليقة `optimize_blend` الموجود أصلاً، بس مجمَّع
    لحظيرة كاملة بدل رأس واحد) ويخصمها فعلياً من المخزون. لو خلطة
    اليوم مو ممكنة (بدون أوزان مسجَّلة، أو بدون مكوّنات كافية) — المهمة
    تنجز عادي بدون خصم، وسبب عدم الخصم يُكتب بملاحظة الإنجاز عشان
    المالك يتنبّه بدون ما يفشل إنجاز المهمة الروتينية."""
    from app.feed import feed_service as feed_svc

    result = feed_svc.barn_daily_blend(barn_id=task.barn_id)
    if not result.get("feasible"):
        reason = result.get("reason", "خلطة اليوم غير ممكنة حالياً.")
        task.completion_note = f"{task.completion_note or ''}\n⚠️ ما تم خصم علف تلقائياً: {reason}".strip()
        return

    shortages = []
    distributed = []
    for item in result["blend"]:
        try:
            feed_svc.record_movement(
                feed=item["feed"], movement_type="out", quantity=item["quantity_kg"],
                barn_id=task.barn_id, note=f"توزيع علف تلقائي — مهمة #{task.id}",
                created_by_id=task.assignee_id,
            )
            distributed.append(f"{item['feed'].name} ({item['quantity_kg']} كجم)")
        except ValueError:
            shortages.append(item["feed"].name)

    summary = f"✅ خُصم من المخزون: {', '.join(distributed)}." if distributed else ""
    if shortages:
        summary += f" ⚠️ مخزون غير كافٍ لهذي المكوّنات (ما انخصمت): {', '.join(shortages)}."
    task.completion_note = f"{task.completion_note or ''}\n{summary}".strip()


def fail_task(task: Task, *, actor, reason, note=None, evidence_image_url=None, voice_note_url=None) -> Task:
    """تعذّر تنفيذ المهمة (بند إضافي 54) — بدل ما يظل العامل صامتاً أو
    يضغط "بدء" بلا أي أثر، يسجّل صراحة إنه ما قدر ينجزها وليش، بسبب من
    قائمة مقفلة (`FAILURE_REASONS`) عشان تصير قابلة للمتابعة والتحليل."""
    _claim_if_unassigned(task, actor)
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

    if task.task_type == "protocol_step":
        _maybe_close_protocol_application(task)
    if task.task_type == "isolation_check":
        _maybe_close_isolation_plan(task)

    db.session.commit()
    return task


def postpone_active_task(task: Task, *, actor, new_due_date=None) -> Task:
    """تأجيل مهمة فعلية (بند إضافي 109 — شاشة والدك) — مختلفة عن
    `postpone_suggested_task` (تعمل على `suggested` بس، من شاشة مراجعة
    الدكتور اليومية). هذي لمهمة `pending`/`in_progress` فعلية، بيوم
    واحد افتراضياً لو ما انبعث تاريخ صريح — نفس منطق زر "تأجيل" بضغطة
    وحدة (بند 72)."""
    if not actor.has_permission("tasks.assign_any"):
        raise TaskPermissionError("ما تملك صلاحية تأجيل المهام.")
    if task.status not in ("pending", "in_progress"):
        raise TaskStateError("هذي المهمة مو بحالة تسمح بالتأجيل.")
    task.due_date = new_due_date or ((task.due_date or date.today()) + timedelta(days=1))
    db.session.add(AuditLog(actor_user_id=actor.id, action="task.postpone_active",
                             entity_type="Task", entity_id=task.id))
    db.session.commit()
    return task


def cancel_active_task(task: Task, *, actor, reason=None) -> Task:
    """إلغاء مهمة فعلية يدوياً (بند إضافي 109) — نفس حالة `cancelled`
    المستخدمة تلقائياً ببند 98 (بيع/نفوق رأس)، بس هنا بقرار يدوي صريح
    من صاحب صلاحية توزيع المهام."""
    if not actor.has_permission("tasks.assign_any"):
        raise TaskPermissionError("ما تملك صلاحية إلغاء المهام.")
    if task.status not in ("pending", "in_progress"):
        raise TaskStateError("هذي المهمة مو بحالة تسمح بالإلغاء.")
    task.status = "cancelled"
    task.notes = (task.notes + " | " if task.notes else "") + (reason or "أُلغيت يدوياً")
    db.session.add(AuditLog(actor_user_id=actor.id, action="task.cancel_active",
                             entity_type="Task", entity_id=task.id))
    db.session.commit()
    return task


OPEN_TASK_STATUSES = ("suggested", "pending", "in_progress", "postponed")


def cancel_open_tasks_for_animal(animal, *, reason: str, actor_user_id: int | None = None) -> list[Task]:
    """إلغاء كل مهام رأس معيّن اللي لسا مفتوحة (بند إضافي 98) — قبل هذا
    البند، بيع/نفوق رأس كان يحدّث حالته بس، بدون ما يلمس أي مهمة مرتبطة
    فيه (تحصين، رش، خطوة بروتوكول علاج...). المهام تبقى معلّقة تشير
    لرأس مو موجود فعلياً، والعامل يفتحها يومياً بلا فايدة. يشمل مهام
    خطوات البروتوكول العلاجي كمان (`source_type='ProtocolApplication'`)
    لأنها كلها `Task` عادية بـ`animal_id` نفسه — صفر جدول ثاني يحتاج
    تعديل. مهام منجزة/فاشلة/ملغاة أصلاً ما تُلمَس — سجل تاريخي، مو
    عمل معلّق.

    كل مهمة تُلغى تسجّل سطر `AuditLog` مستقل (بند إضافي 231) — قبل هذا
    كان الإلغاء يظهر بس كملاحظة نصية داخل المهمة نفسها، بدون أي أثر
    بسجل التدقيق المركزي (البيع نفسه له سجل تدقيق، إلغاء مهامه التابعة
    ما كان له)."""
    tasks = Task.query.filter(Task.animal_id == animal.id, Task.status.in_(OPEN_TASK_STATUSES)).all()
    for t in tasks:
        t.status = "cancelled"
        t.notes = (t.notes + " | " if t.notes else "") + reason
        db.session.add(t)
        db.session.add(AuditLog(
            actor_user_id=actor_user_id, action="task.auto_cancel_on_animal_exit",
            entity_type="Task", entity_id=t.id, details=reason,
        ))
    return tasks
