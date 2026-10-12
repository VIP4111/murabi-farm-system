"""
الإدخال الذكي بالنص/الصوت (بند إضافي 299 — المرحلة ٤، الأخيرة من خطة
"عقل المزرعة").

المسار الإلزامي بلا استثناء: نص/صوت حر ← `llm_bridge.parse_draft_action*`
يقترح إجراء ← `draft_guardrail_reason` يفحصه قطعياً ← لو مسموح يُحفظ
`pending` (بطاقة تأكيد) ← إنسان يضغط "اعتماد" ← عندها بس ينفَّذ
`_ALLOWED_ACTION_TYPES[type]["execute"]` الحقيقية. صفر كتابة بقاعدة
بيانات المزرعة الفعلية (Animal/AnimalWeight...) من أي نقطة قبل هذي
الخطوة الأخيرة.
"""
from datetime import date, datetime, timezone, timedelta
from flask_babel import gettext as _

from app.extensions import db, farm_today
from app.models import AssistantDraftAction, Animal, User
from app.assistant import llm_bridge
from app.core import animal_service

DRAFT_STALE_HOURS = 48


def _now():
    return datetime.now(timezone.utc)


def _execute_register_birth(payload: dict, *, actor, assignee_id=None):
    mother_no = payload.get("target_animal_no")
    mother = Animal.query.filter_by(animal_no=mother_no).first()
    if not mother:
        raise ValueError(_("ما فيه حيوان أم برقم \"%(no)s\".", no=mother_no))
    gender = payload.get("newborn_gender") or payload.get("gender")
    if gender not in ("ذكر", "أنثى"):
        raise ValueError(_("جنس المولود غير محدَّد أو غير صحيح — عدّل الملاحظة وسجّل الولادة يدوياً."))
    weight = payload.get("newborn_weight") or payload.get("weight")
    return animal_service.register_birth(
        mother=mother, gender=gender,
        weight=float(weight) if weight not in (None, "") else None,
    )


def _execute_record_weight(payload: dict, *, actor, assignee_id=None):
    animal_no = payload.get("target_animal_no")
    animal = Animal.query.filter_by(animal_no=animal_no).first()
    if not animal:
        raise ValueError(_("ما فيه حيوان برقم \"%(no)s\".", no=animal_no))
    weight = payload.get("weight")
    if weight in (None, ""):
        raise ValueError(_("الوزن غير محدَّد بالملاحظة — عدّلها وسجّل الوزن يدوياً."))
    record = animal_service.add_weight_record(
        animal=animal, record_date=farm_today(), weight=float(weight), recorded_by_id=actor.id,
    )
    # بند إضافي 310 — فجوة تدقيق حقيقية: الراوت اليدوي لتسجيل الوزن
    # (core/routes.py) يستدعي `cycle_engine.evaluate(animal)` دايماً
    # بعد كل وزن جديد (بوابات "جاهز للفطام/البيع" تعتمد على الوزن) —
    # هذا المسار كان يفوّتها، يعني وزن مسجَّل عبر الإدخال الذكي ما يحرّك
    # دورة الإنتاج تلقائياً زي نظيره اليدوي بالضبط.
    from app.core import cycle_engine
    cycle_engine.evaluate(animal)
    return record


def _execute_assign_task(payload: dict, *, actor, assignee_id=None):
    """بند إضافي 316 — طلبك الصريح: "احتاج منه يترجم للغة العضو
    بالفريق"، وقبلها: "أخاف يحول أو يتخذ اتجاه غير مرغوب فيه لو ما
    اخترت بنفسي". لهذا `assignee_id` هنا **إلزامي** ويجي حصراً من
    اختيارك الصريح بواجهة الاعتماد (قائمة منسدلة بأسماء حقيقية) — النص
    الحر يوصف المهمة بس، أبداً ما يحدد المكلَّف. المهمة تُسجَّل بلغتك
    (عربي) دايماً بالـnotes، والعنوان (title) يُترجَم للغة الشخص
    المختار لو مختلفة — نفس منطق ترجمة ردود المساعد (بند 275)، بس
    للمهام هذي المرة."""
    if not assignee_id:
        raise ValueError(_("لازم تختار عضو الفريق المكلَّف قبل الاعتماد."))
    assignee = User.query.get(assignee_id)
    if not assignee:
        raise ValueError(_("عضو الفريق المختار غير موجود."))

    title = (payload.get("task_title") or "").strip()
    if not title:
        raise ValueError(_("نص المهمة غير محدَّد بالملاحظة — عدّلها ووزّع المهمة يدوياً."))

    animal_id = None
    animal_no = payload.get("target_animal_no")
    if animal_no:
        animal = Animal.query.filter_by(animal_no=animal_no).first()
        if not animal:
            raise ValueError(_("ما فيه حيوان برقم \"%(no)s\".", no=animal_no))
        animal_id = animal.id

    due_date = None
    due_date_raw = payload.get("due_date")
    if due_date_raw:
        try:
            due_date = date.fromisoformat(due_date_raw)
        except ValueError:
            due_date = None

    translated_title = llm_bridge.translate_text(title, assignee.language or "ar")
    final_title = translated_title or title
    notes = f"النص الأصلي (كما كتبه {actor.name}): {title}" if translated_title else None

    from app.team import task_service
    return task_service.assign_task(
        actor=actor, title=final_title, assignee_id=assignee.id,
        animal_id=animal_id, due_date=due_date, notes=notes,
    )


def _execute_record_expense(payload: dict, *, actor, assignee_id=None):
    """تسجيل فاتورة مورّد كمصروف — نفس شروط `finance.finance_new` (مبلغ
    غير سالب، تاريخ مو بالمستقبل). التنفيذ الوحيد: صف `Finance` من نوع
    expense؛ ما يلمس المخزون (شراء علف/دواء بالمخزون له شاشة الشراء
    المخصَّصة لأنها تزيد الرصيد فعلياً)."""
    from app.core import validation_service
    from app.models import Finance, AuditLog

    try:
        amount = float(payload.get("total_amount"))
    except (TypeError, ValueError):
        raise ValueError(_("مبلغ الفاتورة غير مقروء — سجّلها يدوياً من شاشة المالية."))
    validation_service.validate_price(amount, field_label=_("المبلغ"))
    if amount <= 0:
        raise ValueError(_("مبلغ الفاتورة لازم يكون أكبر من صفر."))

    entry_date = farm_today()
    raw_date = payload.get("invoice_date")
    if raw_date:
        try:
            entry_date = date.fromisoformat(raw_date)
        except ValueError:
            entry_date = farm_today()
    validation_service.validate_not_future_date(entry_date, field_label=_("تاريخ الفاتورة"))

    category = payload.get("category") or "بدون تصنيف"
    row = Finance(
        date=entry_date, operation_type="expense", category=category,
        item=(payload.get("supplier") or None), description=(payload.get("description") or None),
        amount=amount, invoice_file_url=payload.get("invoice_file_url") or None,
    )
    db.session.add(row)
    db.session.add(AuditLog(actor_user_id=actor.id, action="assistant.invoice_expense",
                             entity_type="Finance", details=f"{amount:g} — {payload.get('supplier') or '-'}"))
    db.session.commit()
    return row


def _animal_or_error(animal_no):
    animal_no = str(animal_no or "").strip()
    animal = Animal.query.filter_by(animal_no=animal_no).first()
    if not animal:
        raise ValueError(_("ما فيه حيوان برقم \"%(no)s\".", no=animal_no))
    return animal


def _active_animal_or_error(animal_no):
    animal = _animal_or_error(animal_no)
    if animal.status != "active":
        raise ValueError(_("الحيوان \"%(no)s\" مو نشط (مباع أو نافق).", no=animal.animal_no))
    return animal


def _barn_or_error(barn_name):
    from app.models import Barn
    name = str(barn_name or "").strip()
    if not name:
        raise ValueError(_("اسم الحظيرة غير محدَّد."))
    barns = Barn.query.filter(Barn.barn_name == name).all() or \
        Barn.query.filter(Barn.barn_name.contains(name)).all()
    if not barns:
        raise ValueError(_("ما لقيت حظيرة باسم \"%(name)s\".", name=name))
    if len(barns) > 1:
        raise ValueError(_("فيه أكثر من حظيرة باسم يشبه \"%(name)s\" — حدّد الاسم الكامل.", name=name))
    return barns[0]


def _execute_create_animal(payload: dict, *, actor, assignee_id=None):
    """إضافة رأس جديد (شراء/هدية/رصيد افتتاحي) بنفس دالة الشاشة اليدوية
    `animal_service.create_animal` وبنفس شروطها (حظيرة ولون ورقم إلزامية).
    المواليد لها مسارها (`register_birth`) لأن إشعار الولادة وخطة العزل
    مرتبطان به."""
    from sqlalchemy.exc import IntegrityError
    from app.models import AuditLog, SpeciesType
    from app.models.animal import AnimalSource

    source_map = {"purchase": AnimalSource.PURCHASE, "gift": AnimalSource.GIFT,
                  "opening_balance": AnimalSource.OPENING_BALANCE}
    source_key = str(payload.get("source") or "").strip()
    if source_key == "birth":
        raise ValueError(_("المواليد تُسجَّل بأداة تسجيل الولادة مو بإضافة رأس جديد."))
    if source_key not in source_map:
        raise ValueError(_("مصدر الرأس لازم يكون: شراء أو هدية أو رصيد افتتاحي."))

    animal_no = str(payload.get("new_animal_no") or "").strip()
    if not animal_no:
        raise ValueError(_("رقم الحيوان مطلوب."))
    if Animal.query.filter_by(animal_no=animal_no).first():
        raise ValueError(_("رقم الحيوان \"%(no)s\" مستخدم من قبل", no=animal_no))
    gender = str(payload.get("gender") or "").strip()
    if gender not in ("ذكر", "أنثى"):
        raise ValueError(_("جنس الحيوان لازم يكون ذكر أو أنثى."))
    color = str(payload.get("color") or "").strip()
    if not color:
        raise ValueError(_("اللون مطلوب"))
    barn = _barn_or_error(payload.get("barn_name"))

    species = str(payload.get("species") or "sheep_goat").strip() or "sheep_goat"
    if species != "sheep_goat" and not SpeciesType.query.filter_by(code=species).first():
        raise ValueError(_("الفصيلة \"%(code)s\" غير معرَّفة بالنظام.", code=species))

    def _num(key):
        raw = payload.get(key)
        if raw in (None, ""):
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            raise ValueError(_("قيمة %(field)s غير واضحة.", field=key))

    mother = _animal_or_error(payload.get("mother_no")) if str(payload.get("mother_no") or "").strip() else None
    father = _animal_or_error(payload.get("father_no")) if str(payload.get("father_no") or "").strip() else None
    purpose = payload.get("purpose") or None
    if purpose and purpose not in ("تربية", "تسمين", "بيع"):
        raise ValueError(_("الغرض لازم يكون: تربية أو تسمين أو بيع."))

    try:
        animal = animal_service.create_animal(
            animal_no=animal_no, source=source_map[source_key], gender=gender, species=species,
            barn_id=barn.id, mother_id=mother.id if mother else None, father_id=father.id if father else None,
            birth_date=_parse_iso_date(payload.get("birth_date")),
            purchase_date=_parse_iso_date(payload.get("purchase_date")),
            weight=_num("weight"), price=_num("price"), purpose=purpose, color=color,
            name=(payload.get("name") or None), breed=(payload.get("breed") or None),
            is_pregnant_at_intake=bool(payload.get("is_pregnant")),
        )
    except IntegrityError:
        db.session.rollback()
        raise ValueError(_("رقم الحيوان \"%(no)s\" مستخدم من قبل", no=animal_no))
    db.session.add(AuditLog(actor_user_id=actor.id, action="animal.create", entity_type="Animal",
                            entity_id=animal.id, details=f"source={source_key}; via=assistant"))
    db.session.commit()
    return animal


def _execute_move_animal(payload: dict, *, actor, assignee_id=None):
    from app.models import Barn
    from app.core import bulk_service
    animal = _active_animal_or_error(payload.get("target_animal_no"))
    barn = _barn_or_error(payload.get("barn_name"))
    if animal.barn_id == barn.id:
        raise ValueError(_("الحيوان موجود أصلاً في هذي الحظيرة."))
    bulk_service.apply_bulk_barn_move(animal_ids=[animal.id], barn_id=barn.id, actor_user_id=actor.id)
    return animal


def _execute_add_animal_note(payload: dict, *, actor, assignee_id=None):
    animal = _animal_or_error(payload.get("target_animal_no"))
    note = str(payload.get("note") or "").strip()
    if not note:
        raise ValueError(_("نص الملاحظة غير محدَّد."))
    return animal_service.add_note(animal=animal, note_date=farm_today(), note=note, created_by_id=actor.id)


def _execute_add_farm_note(payload: dict, *, actor, assignee_id=None):
    from app.assistant import farm_note_service
    body = str(payload.get("body") or "").strip()
    if not body:
        raise ValueError(_("نص الملاحظة غير محدَّد."))
    return farm_note_service.create_note(body=body, created_by=actor, title=(payload.get("title") or None))


def _execute_complete_task(payload: dict, *, actor, assignee_id=None):
    from app.models import Task
    from app.team import task_service
    task = _my_open_task_or_error(actor, payload.get("task_title"))
    return task_service.complete_task(task, actor=actor, note=(payload.get("note") or None))


def _my_open_task_or_error(actor, title):
    from app.models import Task
    title = str(title or "").strip()
    if not title:
        raise ValueError(_("عنوان المهمة غير محدَّد."))
    rows = Task.query.filter(Task.assignee_id == actor.id, Task.status.in_(("pending", "in_progress"))).all()
    exact = [t for t in rows if t.display_title() == title]
    matches = exact or [t for t in rows if title in t.display_title()]
    if not matches:
        raise ValueError(_("ما لقيت مهمة مفتوحة عندك بعنوان يشبه \"%(title)s\".", title=title))
    if len(matches) > 1:
        raise ValueError(_("أكثر من مهمة تشبه \"%(title)s\" — حدّد العنوان بدقة.", title=title))
    return matches[0]


def _execute_start_task(payload: dict, *, actor, assignee_id=None):
    from app.team import task_service
    task = _my_open_task_or_error(actor, payload.get("task_title"))
    return task_service.start_task(task, actor=actor)


def _execute_record_milk(payload: dict, *, actor, assignee_id=None):
    animal = _active_animal_or_error(payload.get("target_animal_no"))
    session = str(payload.get("session") or "").strip()
    if session not in ("صباح", "مساء"):
        raise ValueError(_("لازم تحدد الحلبة: صباح أو مساء."))
    try:
        liters = float(payload.get("liters"))
    except (TypeError, ValueError):
        raise ValueError(_("كمية الحليب غير واضحة."))
    return animal_service.add_milk_record(
        animal=animal, record_date=farm_today(), session=session, quantity_liters=liters,
        recorded_by_id=actor.id,
    )


def _execute_request_checkup(payload: dict, *, actor, assignee_id=None):
    from app.team import task_service
    if not assignee_id:
        raise ValueError(_("لازم تختار عضو الفريق المكلَّف قبل الاعتماد."))
    animal = _active_animal_or_error(payload.get("target_animal_no"))
    items = [str(i).strip() for i in (payload.get("items") or []) if str(i).strip()]
    if not items:
        raise ValueError(_("لازم تحدد بند فحص واحد على الأقل."))
    due = None
    if payload.get("due_date"):
        try:
            due = date.fromisoformat(payload["due_date"])
        except ValueError:
            due = None
    return task_service.assign_animal_checkup(actor=actor, animal=animal, items=items,
                                              assignee_id=assignee_id, due_date=due)


def _execute_set_purpose(payload: dict, *, actor, assignee_id=None):
    from app.core import bulk_service
    animal = _active_animal_or_error(payload.get("target_animal_no"))
    purpose = str(payload.get("purpose") or "").strip()
    if purpose not in ("تربية", "تسمين", "بيع"):
        raise ValueError(_("الغرض لازم يكون: تربية أو تسمين أو بيع."))
    bulk_service.apply_bulk_purpose(animal_ids=[animal.id], purpose=purpose, actor_user_id=actor.id)
    return animal


def _execute_send_to_market(payload: dict, *, actor, assignee_id=None):
    from app.core import cycle_engine
    animal = _active_animal_or_error(payload.get("target_animal_no"))
    try:
        cycle_engine.send_to_market(animal, actor_user_id=actor.id, note=(payload.get("note") or None))
    except cycle_engine.CycleExitBlocked as e:
        raise ValueError(str(e))
    return animal


def _execute_return_from_market(payload: dict, *, actor, assignee_id=None):
    from app.core import cycle_engine
    animal = _active_animal_or_error(payload.get("target_animal_no"))
    cycle_engine.return_from_market(animal, actor_user_id=actor.id, note=(payload.get("note") or None))
    return animal


def _parse_iso_date(raw):
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return None


def _execute_record_mating(payload: dict, *, actor, assignee_id=None):
    from app.core import repro_service
    female = _animal_or_error(payload.get("target_animal_no"))
    male = None
    if str(payload.get("male_no") or "").strip():
        male = _animal_or_error(payload.get("male_no"))
    return repro_service.record_mating_checked(
        female=female, male=male, male_note=payload.get("male_note"),
        mating_date=_parse_iso_date(payload.get("mating_date")), notes=payload.get("notes"),
        actor_user_id=actor.id,
    )


def _execute_record_pregnancy(payload: dict, *, actor, assignee_id=None):
    from app.core import repro_service
    female = _animal_or_error(payload.get("target_animal_no"))
    embryo = payload.get("embryo_count")
    try:
        embryo = int(embryo) if embryo not in (None, "") else None
    except (TypeError, ValueError):
        raise ValueError(_("عدد الأجنة غير واضح."))
    return repro_service.record_pregnancy_checked(
        female=female, confirmed=bool(payload.get("confirmed")), embryo_count=embryo,
        sonar_date=_parse_iso_date(payload.get("sonar_date")),
        pregnancy_date=_parse_iso_date(payload.get("pregnancy_date")), notes=payload.get("notes"),
        actor_user_id=actor.id,
    )


def _execute_confirm_pregnancy(payload: dict, *, actor, assignee_id=None):
    from app.core import repro_service
    female = _animal_or_error(payload.get("target_animal_no"))
    pregnancy = repro_service.latest_open_pregnancy(female)
    if not pregnancy:
        raise ValueError(_("ما فيه حمل مسجَّل للأنثى \"%(no)s\" يحتاج تأكيد.", no=female.animal_no))
    return repro_service.confirm_pregnancy(pregnancy, actor_user_id=actor.id)


def _execute_record_abortion(payload: dict, *, actor, assignee_id=None):
    from app.core import repro_service
    from app.core.isolation_service import record_abortion
    female = _animal_or_error(payload.get("target_animal_no"))
    pregnancy = repro_service.latest_open_pregnancy(female)
    if not pregnancy:
        raise ValueError(_("ما فيه حمل مسجَّل مفتوح للأنثى \"%(no)s\".", no=female.animal_no))
    return record_abortion(
        pregnancy=pregnancy, outcome_date=farm_today(), notes=(payload.get("notes") or None),
        actor_user_id=actor.id,
    )


def _execute_record_disease(payload: dict, *, actor, assignee_id=None):
    from app.health import health_service
    animal = _active_animal_or_error(payload.get("target_animal_no"))
    name = str(payload.get("disease_name") or "").strip()
    if not name:
        raise ValueError(_("اسم المرض غير محدَّد."))
    severity = payload.get("severity") or "medium"
    if severity not in ("light", "medium", "severe"):
        severity = "medium"
    return health_service.record_disease(
        actor_user_id=actor.id, animal_id=animal.id, disease_name=name,
        date_=farm_today(), severity=severity,
    )


def _execute_record_vaccination(payload: dict, *, actor, assignee_id=None):
    from app.health import health_service
    animal = _active_animal_or_error(payload.get("target_animal_no"))
    vaccine = str(payload.get("vaccine_name") or "").strip()
    if not vaccine:
        raise ValueError(_("اسم اللقاح غير محدَّد."))
    next_due = None
    if payload.get("next_due_date"):
        try:
            next_due = date.fromisoformat(payload["next_due_date"])
        except ValueError:
            next_due = None
    return health_service.record_vaccination(
        actor_user_id=actor.id, animal_id=animal.id, vaccine_name=vaccine,
        date_=farm_today(), next_due_date=next_due,
    )


def _execute_record_sale(payload: dict, *, actor, assignee_id=None):
    from app.core import cycle_engine, validation_service
    animal = _active_animal_or_error(payload.get("target_animal_no"))
    try:
        price = float(payload.get("price"))
    except (TypeError, ValueError):
        raise ValueError(_("سعر البيع غير واضح."))
    validation_service.validate_price(price, field_label=_("سعر البيع"))
    sale_date = farm_today()
    if payload.get("sale_date"):
        try:
            sale_date = date.fromisoformat(payload["sale_date"])
        except ValueError:
            sale_date = farm_today()
    validation_service.validate_not_future_date(sale_date, field_label=_("تاريخ البيع"))
    try:
        cycle_engine.sell_animal(animal, sale_price=price, actor_user_id=actor.id, sale_date=sale_date,
                                 notes=(payload.get("buyer_note") or None))
    except cycle_engine.CycleExitBlocked as e:
        raise ValueError(str(e))
    return animal


def _execute_record_death(payload: dict, *, actor, assignee_id=None):
    from app.core import cycle_engine
    animal = _active_animal_or_error(payload.get("target_animal_no"))
    cycle_engine.mark_animal_dead(animal, actor_user_id=actor.id, reason=(payload.get("reason") or None),
                                  death_date=farm_today())
    return animal


# **مصدر الحقيقة الوحيد لما يُنفَّذ فعلياً** — لازم يطابق
# `llm_bridge.ALLOWED_DRAFT_ACTION_TYPES` تماماً (اختبار مخصَّص يتحقق
# من هذا التطابق). أي إجراء مو هنا يستحيل تنفيذه حتى لو تجاوز الحاجز
# البرمجي بطريقة ما — دفاع بطبقتين مستقلتين.
#
# `required_permission` (بند إضافي 307 — فجوة أمان حقيقية اكتشفناها
# بالتدقيق): الراوت `/assistant/drafts/<id>/confirm` يفحص بس
# `assistant.draft_actions.confirm` — صلاحية "تقدر تستخدم شاشة الإدخال
# الذكي"، مو "تقدر تعدّل حيوانات فعلياً". بدون هذا الفحص، عامل عنده
# `assistant.draft_actions.confirm` بس بدون `animals.manage` (منح
# افتراضي فعلي لدور "worker" ببند 299) كان يقدر يسجّل ولادة/وزن حقيقي
# عبر مسار المسودات — تجاوز كامل لنفس فحص `animals.manage` اللي يحمي
# كل مسار كتابة حيوان ثاني بالنظام (`/animals/new`،
# `/animals/<id>/weights/new`). هذا الفحص يطبّق نفس القاعدة هنا بالضبط.
ALLOWED_ACTION_TYPES = {
    "register_birth": {"label": "تسجيل ولادة", "execute": _execute_register_birth,
                        "required_permission": "animals.manage"},
    "record_weight": {"label": "تسجيل وزن", "execute": _execute_record_weight,
                       "required_permission": "animals.manage"},
    "assign_task": {"label": "توزيع مهمة", "execute": _execute_assign_task,
                     "required_permission": "tasks.assign_any"},
    "record_expense": {"label": "تسجيل فاتورة كمصروف", "execute": _execute_record_expense,
                        "required_permission": "finance.full.manage"},
    # أنواع وكيل Claude (محادثة فورية) — نفس صلاحيات الشاشات اليدوية بالضبط.
    "move_animal": {"label": "نقل حيوان لحظيرة", "execute": _execute_move_animal,
                     "required_permission": "animals.manage"},
    "add_animal_note": {"label": "ملاحظة على حيوان", "execute": _execute_add_animal_note,
                         "required_permission": "animals.manage"},
    "add_farm_note": {"label": "ملاحظة بدفتر المزرعة", "execute": _execute_add_farm_note,
                       "required_permission": "farm_notes.manage"},
    "complete_task": {"label": "إنهاء مهمة", "execute": _execute_complete_task,
                       "required_permission": "tasks.view_own"},
    "record_vaccination": {"label": "تسجيل تحصين", "execute": _execute_record_vaccination,
                            "required_permission": "health.manage"},
    "record_sale": {"label": "تسجيل بيع رأس", "execute": _execute_record_sale,
                     "required_permission": "animals.manage"},
    "record_death": {"label": "تسجيل نفوق", "execute": _execute_record_death,
                      "required_permission": "animals.manage"},
    "record_milk": {"label": "تسجيل حليب", "execute": _execute_record_milk,
                     "required_permission": "animals.manage"},
    "start_task": {"label": "بدء مهمة", "execute": _execute_start_task,
                    "required_permission": "tasks.view_own"},
    "request_checkup": {"label": "طلب فحص من عضو فريق", "execute": _execute_request_checkup,
                         "required_permission": "tasks.assign_any"},
    "set_purpose": {"label": "تحديد غرض رأس", "execute": _execute_set_purpose,
                     "required_permission": "animals.manage"},
    "send_to_market": {"label": "إطلاع رأس للسوق", "execute": _execute_send_to_market,
                        "required_permission": "animals.manage"},
    "return_from_market": {"label": "إرجاع رأس من السوق", "execute": _execute_return_from_market,
                            "required_permission": "animals.manage"},
    "record_disease": {"label": "تسجيل مرض", "execute": _execute_record_disease,
                        "required_permission": "health.manage"},
    "record_mating": {"label": "تسجيل تقريع/تلقيح", "execute": _execute_record_mating,
                       "required_permission": "repro.manage"},
    "record_pregnancy": {"label": "تسجيل تشخيص حمل", "execute": _execute_record_pregnancy,
                          "required_permission": "repro.manage"},
    "confirm_pregnancy": {"label": "تأكيد حمل", "execute": _execute_confirm_pregnancy,
                           "required_permission": "repro.manage"},
    "record_abortion": {"label": "تسجيل إجهاض", "execute": _execute_record_abortion,
                         "required_permission": "repro.manage"},
    "create_animal": {"label": "إضافة رأس جديد", "execute": _execute_create_animal,
                       "required_permission": "animals.manage"},
}


def propose_from_text(raw_text: str, *, created_by) -> AssistantDraftAction:
    # بند إصلاح (فحص عميق — طلبك: "افحص شاشة المساعد الذكي كمان") —
    # كان الملخص القصير بالبطاقة يُطلَب عربي دائماً بغض النظر عن لغة
    # مُنشئ المسودة (نفس من يراجع بطاقة الاعتماد غالباً). صار يُطلَب
    # بلغته الفعلية.
    from app.assistant.translations import lang_for
    lang = lang_for(created_by) if created_by else "ar"
    parsed = llm_bridge.parse_draft_action(raw_text, lang)
    return _save_proposal(raw_text, parsed, created_by=created_by, input_source="text")


def propose_from_audio(audio_bytes: bytes, mime_type: str, *, created_by, audio_url: str | None = None) -> AssistantDraftAction:
    """`audio_url` (بند إضافي 312) — رابط دائم اختياري للمقطع نفسه
    (نفس آلية `report_service.save_voice_note` الموجودة أصلاً)، عشان
    مسودة الصوت توثَّق بنفس مستوى مسودة الصورة (بند 305) — تقدر ترجع
    تسمع وش قلت بالضبط، مو بس النص المستخرَج منه."""
    from app.assistant.translations import lang_for
    lang = lang_for(created_by) if created_by else "ar"
    parsed = llm_bridge.parse_draft_action_from_audio(audio_bytes, mime_type, lang)
    return _save_proposal("(مقطع صوتي)", parsed, created_by=created_by, input_source="voice", audio_url=audio_url)


def propose_from_invoice(file_bytes: bytes, mime_type: str, *, created_by,
                         invoice_file_url: str | None = None) -> AssistantDraftAction:
    """فاتورة (صورة/PDF) ← مسودة مصروف تنتظر اعتمادك. `invoice_file_url`
    رابط دائم للفاتورة نفسها (نفس `finance_service.save_invoice_file`)
    يُحفظ مع السجل المالي عند الاعتماد كدليل."""
    from app.assistant.translations import lang_for
    lang = lang_for(created_by) if created_by else "ar"
    parsed = llm_bridge.parse_invoice(file_bytes, mime_type, lang)
    if parsed and invoice_file_url:
        parsed["payload"]["invoice_file_url"] = invoice_file_url
    return _save_proposal("(فاتورة مرفوعة)", parsed, created_by=created_by, input_source="invoice")


def _save_proposal(raw_text: str, parsed: dict | None, *, created_by, input_source: str,
                    audio_url: str | None = None) -> AssistantDraftAction:
    if not parsed:
        # النموذج ما تعرّف على إجراء مدعوم (أو Gemini غير مفعَّل/فشل) —
        # نسجّلها بالتوثيق بس، بدون أي محاولة تنفيذ.
        draft = AssistantDraftAction(
            raw_text=raw_text, input_source=input_source, status="auto_rejected",
            rejection_reason="ما قدر النموذج يحوّل هذا النص/الصوت لإجراء مدعوم تلقائياً.",
            created_by_id=created_by.id if created_by else None, audio_url=audio_url,
        )
        db.session.add(draft)
        db.session.commit()
        return draft

    action_type = parsed["action_type"]
    payload = parsed["payload"]
    reason = llm_bridge.draft_guardrail_reason(action_type, payload)

    draft = AssistantDraftAction(
        raw_text=raw_text, input_source=input_source,
        parsed_action_type=action_type,
        parsed_payload_json=AssistantDraftAction.encode_payload(payload),
        summary_ar=parsed.get("summary_ar"),
        created_by_id=created_by.id if created_by else None,
        status="auto_rejected" if reason else "pending",
        rejection_reason=reason, audio_url=audio_url,
    )
    db.session.add(draft)
    db.session.commit()
    return draft


def confirm_draft(draft: AssistantDraftAction, *, actor, assignee_id=None):
    """ينفّذ الإجراء الحقيقي فقط الآن — وحيد نقطة بالنظام كله تكتب
    بقاعدة بيانات المزرعة بناءً على مسودة مساعد ذكي. يرجّع الاستثناء
    كما هو للمتصل (الراوت) بدل ابتلاعه — تعديل بيانات فعلي، الفشل يجب
    يكون واضحاً ومرئياً، مو صامتاً. `assignee_id` (بند إضافي 316) —
    اختيارك الصريح بواجهة الاعتماد لعضو الفريق المكلَّف؛ يُستخدم بس
    لمسودات `assign_task`، الأنواع الثانية تتجاهله."""
    if draft.status != "pending":
        raise ValueError(_("هذي المسودة مو بانتظار الاعتماد."))
    action_def = ALLOWED_ACTION_TYPES[draft.parsed_action_type]
    required_permission = action_def["required_permission"]
    if not actor.has_permission(required_permission):
        raise PermissionError(_('تحتاج صلاحية "%(perm)s" لاعتماد هذا النوع من المسودات.', perm=required_permission))
    result = action_def["execute"](draft.get_payload(), actor=actor, assignee_id=assignee_id)
    draft.status = "confirmed"
    draft.confirmed_by_id = actor.id
    draft.decided_at = _now()
    db.session.commit()
    return result


def reject_draft(draft: AssistantDraftAction, *, actor):
    if draft.status != "pending":
        raise ValueError(_("هذي المسودة مو بانتظار الاعتماد."))
    draft.status = "rejected"
    draft.confirmed_by_id = actor.id
    draft.decided_at = _now()
    db.session.commit()


def expire_stale_drafts(*, now: datetime | None = None) -> int:
    """تحسينك الثالث المعتمد — تنظيف دوري للمسودات المعلَّقة اللي
    تجاوز عمرها 48 ساعة بدون قرار، بدل ما تتراكم للأبد. يُستدعى من
    مهمة مجدولة حقيقية (`app/core/scheduler.py`)، نفس آلية بند إضافي 78."""
    now = now or _now()
    cutoff = now - timedelta(hours=DRAFT_STALE_HOURS)
    stale = AssistantDraftAction.query.filter(
        AssistantDraftAction.status == "pending", AssistantDraftAction.created_at <= cutoff,
    ).all()
    for draft in stale:
        draft.status = "expired"
        draft.decided_at = now
    db.session.commit()
    return len(stale)
