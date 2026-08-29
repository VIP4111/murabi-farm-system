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

from app.extensions import db
from app.models import AssistantDraftAction, Animal
from app.assistant import llm_bridge
from app.core import animal_service

DRAFT_STALE_HOURS = 48


def _now():
    return datetime.now(timezone.utc)


def _execute_register_birth(payload: dict, *, actor):
    mother_no = payload.get("target_animal_no")
    mother = Animal.query.filter_by(animal_no=mother_no).first()
    if not mother:
        raise ValueError(f"ما فيه حيوان أم برقم \"{mother_no}\".")
    gender = payload.get("newborn_gender") or payload.get("gender")
    if gender not in ("ذكر", "أنثى"):
        raise ValueError("جنس المولود غير محدَّد أو غير صحيح — عدّل الملاحظة وسجّل الولادة يدوياً.")
    weight = payload.get("newborn_weight") or payload.get("weight")
    return animal_service.register_birth(
        mother=mother, gender=gender,
        weight=float(weight) if weight not in (None, "") else None,
    )


def _execute_record_weight(payload: dict, *, actor):
    animal_no = payload.get("target_animal_no")
    animal = Animal.query.filter_by(animal_no=animal_no).first()
    if not animal:
        raise ValueError(f"ما فيه حيوان برقم \"{animal_no}\".")
    weight = payload.get("weight")
    if weight in (None, ""):
        raise ValueError("الوزن غير محدَّد بالملاحظة — عدّلها وسجّل الوزن يدوياً.")
    record = animal_service.add_weight_record(
        animal=animal, record_date=date.today(), weight=float(weight), recorded_by_id=actor.id,
    )
    # بند إضافي 310 — فجوة تدقيق حقيقية: الراوت اليدوي لتسجيل الوزن
    # (core/routes.py) يستدعي `cycle_engine.evaluate(animal)` دايماً
    # بعد كل وزن جديد (بوابات "جاهز للفطام/البيع" تعتمد على الوزن) —
    # هذا المسار كان يفوّتها، يعني وزن مسجَّل عبر الإدخال الذكي ما يحرّك
    # دورة الإنتاج تلقائياً زي نظيره اليدوي بالضبط.
    from app.core import cycle_engine
    cycle_engine.evaluate(animal)
    return record


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
}


def propose_from_text(raw_text: str, *, created_by) -> AssistantDraftAction:
    parsed = llm_bridge.parse_draft_action(raw_text)
    return _save_proposal(raw_text, parsed, created_by=created_by, input_source="text")


def propose_from_audio(audio_bytes: bytes, mime_type: str, *, created_by) -> AssistantDraftAction:
    parsed = llm_bridge.parse_draft_action_from_audio(audio_bytes, mime_type)
    return _save_proposal("(مقطع صوتي)", parsed, created_by=created_by, input_source="voice")


def _save_proposal(raw_text: str, parsed: dict | None, *, created_by, input_source: str) -> AssistantDraftAction:
    if not parsed:
        # النموذج ما تعرّف على إجراء مدعوم (أو Gemini غير مفعَّل/فشل) —
        # نسجّلها بالتوثيق بس، بدون أي محاولة تنفيذ.
        draft = AssistantDraftAction(
            raw_text=raw_text, input_source=input_source, status="auto_rejected",
            rejection_reason="ما قدر النموذج يحوّل هذا النص/الصوت لإجراء مدعوم تلقائياً.",
            created_by_id=created_by.id if created_by else None,
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
        rejection_reason=reason,
    )
    db.session.add(draft)
    db.session.commit()
    return draft


def confirm_draft(draft: AssistantDraftAction, *, actor):
    """ينفّذ الإجراء الحقيقي فقط الآن — وحيد نقطة بالنظام كله تكتب
    بقاعدة بيانات المزرعة بناءً على مسودة مساعد ذكي. يرجّع الاستثناء
    كما هو للمتصل (الراوت) بدل ابتلاعه — تعديل بيانات فعلي، الفشل يجب
    يكون واضحاً ومرئياً، مو صامتاً."""
    if draft.status != "pending":
        raise ValueError("هذي المسودة مو بانتظار الاعتماد.")
    action_def = ALLOWED_ACTION_TYPES[draft.parsed_action_type]
    required_permission = action_def["required_permission"]
    if not actor.has_permission(required_permission):
        raise PermissionError(f"تحتاج صلاحية \"{required_permission}\" لاعتماد هذا النوع من المسودات.")
    result = action_def["execute"](draft.get_payload(), actor=actor)
    draft.status = "confirmed"
    draft.confirmed_by_id = actor.id
    draft.decided_at = _now()
    db.session.commit()
    return result


def reject_draft(draft: AssistantDraftAction, *, actor):
    if draft.status != "pending":
        raise ValueError("هذي المسودة مو بانتظار الاعتماد.")
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
