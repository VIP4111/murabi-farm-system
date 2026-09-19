"""
خدمة النعام (بند 23 بالمواصفة الرئيسية) — دورة (بيض → حضانة → فقس →
تسجيل فرخ). نفس مبدأ نقطة الدخول الموحّدة المعتمد بالمشروع: أي فرخ ناجح
لازم يمر من `record_hatch_success()` هنا، ما يُنشأ مباشرة بجدول Animal.
"""
from datetime import date, timedelta
from flask_babel import gettext as _
from app.extensions import db
from app.models import Animal, AuditLog
from app.models.animal import AnimalSource
from app.models.ostrich import Incubator, OstrichEgg


def register_egg(*, mother_id: int, lay_date: date, quality: str | None = None,
                  weight_grams: float | None = None, notes: str | None = None) -> OstrichEgg:
    egg = OstrichEgg(mother_id=mother_id, lay_date=lay_date, quality=quality,
                      weight_grams=weight_grams, notes=notes)
    db.session.add(egg)
    db.session.commit()
    return egg


class OstrichIncubatorFullError(ValueError):
    """بند إصلاح (فحص شامل سطر بسطر — ميزة النعام) — سعة الحاضنة ما
    كانت مفروضة إطلاقاً (موثَّق صراحة بنص الشاشة نفسها: "النظام ما
    يمنعك تدخل بيض أكثر منها") — صار يُفرض فعلياً الآن، نفس مبدأ
    OstrichEggAlreadyProcessedError."""


def place_in_incubator(egg: OstrichEgg, *, incubator_id: int, incubation_start_date: date) -> OstrichEgg:
    # بند إصلاح (فحص شامل سطر بسطر — ميزة النعام) — ما فيه حارس ضد
    # إعادة إدخال بيضة مسجَّلة نتيجتها أصلاً (فقست/فشلت) أو موجودة
    # بحاضنة ثانية فعلاً — نفس نمط الحارس الموجود بـrecord_hatch_*.
    if egg.hatch_result != "pending":
        raise OstrichEggAlreadyProcessedError(_("هذي البيضة مسجَّلة لها نتيجة فقس مسبقاً."))
    if egg.incubator_id and egg.incubator_id != incubator_id:
        raise ValueError(_("هذي البيضة موجودة بحاضنة ثانية أصلاً."))
    incubator = Incubator.query.get(incubator_id)
    if incubator and incubator.capacity:
        current_count = OstrichEgg.query.filter(
            OstrichEgg.incubator_id == incubator_id, OstrichEgg.id != egg.id,
            OstrichEgg.hatch_result == "pending",
        ).count()
        if current_count >= incubator.capacity:
            raise OstrichIncubatorFullError(
                _("الحاضنة %(code)s وصلت سعتها الكاملة (%(cap)s بيضة).", code=incubator.code, cap=incubator.capacity)
            )
    egg.incubator_id = incubator_id
    egg.incubation_start_date = incubation_start_date
    db.session.add(egg)
    db.session.commit()
    return egg


def expected_hatch_date(egg: OstrichEgg, incubation_days: int) -> date | None:
    if not egg.incubation_start_date:
        return None
    return egg.incubation_start_date + timedelta(days=incubation_days)


class OstrichEggAlreadyProcessedError(ValueError):
    """بند إصلاح (فحص عميق — قسم النعام) — ما كان فيه أي حارس ضد تسجيل
    نتيجة فقس بيضة مسجَّل لها نتيجة أصلاً — إعادة إرسال الفورم بالغلط
    (رجوع بالمتصفح، ضغطة مزدوجة) كانت تنشئ رأساً ثانياً مكرَّراً لنفس
    البيضة الفعلية (`record_hatch_success`)، أو تكتب فوق سبب الفشل
    الأصلي بصمت (`record_hatch_failure`) — بدون أي رسالة توضّح إنها
    مسجَّلة من قبل. نفس مبدأ الحارس الموجود أصلاً بمسار مشابه تماماً
    (`pregnancies_abort`: "هذا الحمل مسجَّل له نتيجة إجهاض مسبقاً")."""


def record_hatch_success(egg: OstrichEgg, *, actual_hatch_date: date, animal_no: str,
                          gender: str | None = None, weight: float | None = None,
                          actor_user_id: int | None = None) -> Animal:
    if egg.hatch_result != "pending":
        raise OstrichEggAlreadyProcessedError(_("هذي البيضة مسجَّلة لها نتيجة فقس مسبقاً."))
    from app.core.animal_service import create_animal

    chick = create_animal(
        animal_no=animal_no, source=AnimalSource.BIRTH, gender=gender or None,
        species="ostrich", mother_id=egg.mother_id, birth_date=actual_hatch_date,
        weight=weight, barn_id=egg.mother.barn_id if egg.mother else None,
    )
    egg.hatch_result = "hatched"
    egg.actual_hatch_date = actual_hatch_date
    egg.hatched_animal_id = chick.id
    db.session.add(egg)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="ostrich_egg.hatch",
                             entity_type="OstrichEgg", entity_id=egg.id, details=f"animal={chick.animal_no}"))
    db.session.commit()
    return chick


def record_hatch_failure(egg: OstrichEgg, *, fail_reason: str, actor_user_id: int | None = None) -> OstrichEgg:
    if egg.hatch_result != "pending":
        raise OstrichEggAlreadyProcessedError(_("هذي البيضة مسجَّلة لها نتيجة فقس مسبقاً."))
    egg.hatch_result = "failed"
    egg.fail_reason = fail_reason
    db.session.add(egg)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="ostrich_egg.fail",
                             entity_type="OstrichEgg", entity_id=egg.id, details=fail_reason))
    db.session.commit()
    return egg


def create_incubator(*, code: str, name: str | None = None, capacity: int | None = None,
                      notes: str | None = None) -> Incubator:
    incubator = Incubator(code=code, name=name, capacity=capacity, notes=notes)
    db.session.add(incubator)
    db.session.commit()
    return incubator
