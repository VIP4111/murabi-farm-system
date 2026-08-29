"""بند إضافي 299 — المرحلة ٤ (الأخيرة) من خطة "عقل المزرعة": الإدخال
الذكي بالنص/الصوت مع مسودة إلزامية + اعتماد بشري صريح، والتزام صارم
بتحسينيك الثالث (توثيق `confirmed_by_id` + تنظيف 48 ساعة) والرابع
(حاجز صلب ضد جرعة دواء/حذف سجل)."""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from app.extensions import db
from app.assistant import draft_action_service, llm_bridge
from app.models import Role, User, AssistantDraftAction, AnimalWeight
from factories import make_animal


def _make_role_user(role_name, phone):
    role = Role.query.filter_by(name=role_name).first()
    user = User(name=f"مستخدم {role_name}", phone=phone, role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


# ---- الحاجز الصلب (تحسينك الرابع) ----

def test_guardrail_blocks_disallowed_action_type():
    reason = llm_bridge.draft_guardrail_reason("delete_animal", {})
    assert reason is not None


def test_guardrail_blocks_dosage_keyword_even_in_allowed_action_type():
    """أخطر اختبار هنا: حتى لو النوع بالقائمة المسموحة، أي ذكر لكلمة
    محظورة بالـpayload يُرفض قطعياً — الحاجز مستقل عن تصنيف Gemini."""
    reason = llm_bridge.draft_guardrail_reason("record_weight", {"note": "بعد إعطائه جرعة دواء"})
    assert reason is not None
    assert "جرعة" in reason


def test_guardrail_allows_clean_allowed_action():
    reason = llm_bridge.draft_guardrail_reason("record_weight", {"target_animal_no": "405", "weight": 30})
    assert reason is None


def test_allowed_action_types_match_between_llm_bridge_and_service():
    """فحص تطابق صريح — القائمتان لازم يكونان نفس الشي بالضبط، أي فرق
    يعني إجراء يقدر يتصنَّف لكن ما فيه تنفيذ حقيقي له أو العكس."""
    assert set(llm_bridge.ALLOWED_DRAFT_ACTION_TYPES) == set(draft_action_service.ALLOWED_ACTION_TYPES)


# ---- propose_from_text: مسار كامل ----

def test_propose_from_text_creates_pending_draft_for_allowed_action(app, owner, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    make_animal(animal_no="405", gender="أنثى")
    parsed = {"action_type": "register_birth",
              "payload": {"target_animal_no": "405", "newborn_gender": "أنثى"},
              "summary_ar": "تسجيل ولادة للشاة 405"}
    with patch("app.assistant.llm_bridge.parse_draft_action", return_value=parsed):
        draft = draft_action_service.propose_from_text("سجلت ولادة اليوم لشاة رقم 405", created_by=owner)
    assert draft.status == "pending"
    assert draft.parsed_action_type == "register_birth"


def test_propose_from_text_auto_rejects_when_model_returns_nothing(app, owner, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    draft = draft_action_service.propose_from_text("كلام غير مفهوم", created_by=owner)
    assert draft.status == "auto_rejected"


def test_propose_from_text_auto_rejects_dosage_related_draft_before_pending(app, owner, monkeypatch):
    """تحسينك الرابع من طرف لطرف: النموذج (مُحاكى) يقترح إجراء فيه ذكر
    جرعة — لازم يوصل auto_rejected مباشرة، أبداً pending."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    parsed = {"action_type": "record_weight",
              "payload": {"target_animal_no": "405", "weight": 30, "note": "بعد جرعة الدواء"},
              "summary_ar": "..."}
    with patch("app.assistant.llm_bridge.parse_draft_action", return_value=parsed):
        draft = draft_action_service.propose_from_text("...", created_by=owner)
    assert draft.status == "auto_rejected"
    assert "جرعة" in draft.rejection_reason


# ---- confirm_draft: التنفيذ الفعلي + توثيق confirmed_by_id ----

def test_confirm_draft_executes_real_write_and_records_confirmer(app, owner):
    animal = make_animal(animal_no="900", gender="أنثى")
    draft = AssistantDraftAction(
        raw_text="سجلت وزن اليوم للرأس 900: 35 كجم", input_source="text",
        parsed_action_type="record_weight",
        parsed_payload_json=AssistantDraftAction.encode_payload({"target_animal_no": "900", "weight": 35}),
        summary_ar="تسجيل وزن 35 كجم للرأس 900", status="pending", created_by_id=owner.id,
    )
    db.session.add(draft)
    db.session.commit()

    draft_action_service.confirm_draft(draft, actor=owner)

    db.session.refresh(draft)
    assert draft.status == "confirmed"
    assert draft.confirmed_by_id == owner.id
    assert draft.decided_at is not None
    assert AnimalWeight.query.filter_by(animal_id=animal.id, weight=35).first() is not None


def test_confirm_record_weight_triggers_cycle_engine_evaluation(app, owner):
    """بند إضافي 310 — فجوة حقيقية: الراوت اليدوي لتسجيل الوزن يستدعي
    cycle_engine.evaluate(animal) دايماً بعد كل وزن جديد (بوابات
    'جاهز للفطام/البيع' تعتمد عليه) — نفس المسار عبر الإدخال الذكي
    كان يفوّتها. لازم يتصرف نفس تصرف الشاشة اليدوية بالضبط."""
    animal = make_animal(animal_no="905")
    draft = AssistantDraftAction(
        raw_text="سجلت وزن اليوم للرأس 905: 20 كجم", parsed_action_type="record_weight",
        parsed_payload_json=AssistantDraftAction.encode_payload({"target_animal_no": "905", "weight": 20}),
        status="pending", created_by_id=owner.id,
    )
    db.session.add(draft)
    db.session.commit()

    with patch("app.core.cycle_engine.evaluate") as mock_evaluate:
        draft_action_service.confirm_draft(draft, actor=owner)

    mock_evaluate.assert_called_once()
    assert mock_evaluate.call_args[0][0].id == animal.id


def test_confirm_draft_rejects_double_confirmation(app, owner):
    draft = AssistantDraftAction(raw_text="x", parsed_action_type="record_weight",
                                  parsed_payload_json="{}", status="confirmed", created_by_id=owner.id)
    db.session.add(draft)
    db.session.commit()
    try:
        draft_action_service.confirm_draft(draft, actor=owner)
        assert False, "لازم يرفع استثناء"
    except ValueError:
        pass


def test_confirm_draft_with_missing_animal_leaves_draft_pending_with_clear_error(app, owner):
    draft = AssistantDraftAction(
        raw_text="x", parsed_action_type="record_weight",
        parsed_payload_json=AssistantDraftAction.encode_payload({"target_animal_no": "لا-يوجد", "weight": 10}),
        status="pending", created_by_id=owner.id,
    )
    db.session.add(draft)
    db.session.commit()
    try:
        draft_action_service.confirm_draft(draft, actor=owner)
        assert False, "لازم يرفع استثناء"
    except ValueError:
        pass
    db.session.refresh(draft)
    assert draft.status == "pending"  # ما تغيّرت — تقدر تصححها وتعيد المحاولة


def test_reject_draft_records_actor_without_writing_animal_data(app, owner):
    animal = make_animal(animal_no="901")
    draft = AssistantDraftAction(
        raw_text="x", parsed_action_type="record_weight",
        parsed_payload_json=AssistantDraftAction.encode_payload({"target_animal_no": "901", "weight": 40}),
        status="pending", created_by_id=owner.id,
    )
    db.session.add(draft)
    db.session.commit()

    draft_action_service.reject_draft(draft, actor=owner)
    db.session.refresh(draft)
    assert draft.status == "rejected"
    assert draft.confirmed_by_id == owner.id
    assert AnimalWeight.query.filter_by(animal_id=animal.id).count() == 0


# ---- expire_stale_drafts (تحسينك الثالث) ----

def test_expire_stale_drafts_flips_old_pending_only(app, owner):
    old = AssistantDraftAction(raw_text="قديمة", parsed_action_type="record_weight",
                                parsed_payload_json="{}", status="pending", created_by_id=owner.id,
                                created_at=datetime.now(timezone.utc) - timedelta(hours=50))
    fresh = AssistantDraftAction(raw_text="حديثة", parsed_action_type="record_weight",
                                  parsed_payload_json="{}", status="pending", created_by_id=owner.id,
                                  created_at=datetime.now(timezone.utc) - timedelta(hours=2))
    db.session.add_all([old, fresh])
    db.session.commit()

    count = draft_action_service.expire_stale_drafts()

    assert count == 1
    db.session.refresh(old)
    db.session.refresh(fresh)
    assert old.status == "expired"
    assert fresh.status == "pending"


# ---- الصلاحيات والراوت ----

def test_drafts_route_requires_permission(app, client):
    worker = _make_role_user("accountant", "0599999200")  # ما يملك الصلاحية أصلاً
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/assistant/drafts")
    assert resp.status_code == 403


def test_owner_can_propose_and_view_draft_via_route(app, client, owner, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.post("/assistant/drafts/new-text", data={"raw_text": "سجلت ولادة اليوم"}, follow_redirects=True)
    assert resp.status_code == 200
    assert AssistantDraftAction.query.filter_by(raw_text="سجلت ولادة اليوم").first() is not None


def test_owner_can_confirm_pending_draft_via_route(app, client, owner):
    make_animal(animal_no="902")
    draft = AssistantDraftAction(
        raw_text="x", parsed_action_type="record_weight",
        parsed_payload_json=AssistantDraftAction.encode_payload({"target_animal_no": "902", "weight": 22}),
        status="pending", created_by_id=owner.id,
    )
    db.session.add(draft)
    db.session.commit()

    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.post(f"/assistant/drafts/{draft.id}/confirm", follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(draft)
    assert draft.status == "confirmed"
    assert draft.confirmed_by_id == owner.id
