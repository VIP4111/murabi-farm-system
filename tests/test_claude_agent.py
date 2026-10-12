"""وكيل Claude المتكامل: حلقة الأدوات بعميل مزيَّف (بدون أي نداء حقيقي).
الضمانات الخادمية: وزن/مهمة فوري، فاتورة/ولادة لا تنفَّذ إلا بتأكيد صريح
بنفس المحادثة، مسودتك أنت، ومهلة 30 دقيقة."""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.assistant import claude_agent, nlu_service
from app.extensions import db
from app.models import AnimalWeight, AssistantDraftAction, Finance, Task
from factories import make_animal


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _tool_use(name, tool_input, tid="tu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=tid)


def _resp(content, stop="end_turn"):
    return SimpleNamespace(content=content, stop_reason=stop)


class FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


@pytest.fixture(autouse=True)
def _legacy_policy(monkeypatch):
    """الاختبارات القديمة كُتبت لسياسة "الخفيف فوري/الحساس بتأكيد"؛ الافتراضي
    الحالي (استشارة لكل إجراء) له اختبارات مخصَّصة آخر الملف."""
    monkeypatch.setenv("AGENT_CONFIRM_TYPES", ",".join(claude_agent.SENSITIVE_TYPES))


@pytest.fixture()
def configured(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


def _use_client(monkeypatch, client):
    monkeypatch.setattr(claude_agent, "_client", lambda: client)


def test_not_configured_returns_none(app, owner, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert claude_agent.run(owner, "كم راس عندنا؟") is None


def test_plain_answer_and_tools_sent(app, owner, configured, monkeypatch):
    fake = FakeClient([_resp([_text("عندك 12 راس.")])])
    _use_client(monkeypatch, fake)
    assert claude_agent.run(owner, "كم راس عندنا؟") == "عندك 12 راس."
    names = [t["name"] for t in fake.calls[0]["tools"]]
    assert "web_search" in names and "record_weight" in names and "confirm_action" in names
    assert "web_research" not in names  # Claude عنده بحثه المدمج
    assert fake.calls[0]["model"] == claude_agent.DEFAULT_MODEL


def test_record_weight_executes_immediately(app, owner, configured, monkeypatch):
    make_animal("A-77")
    fake = FakeClient([
        _resp([_tool_use("record_weight", {"animal_no": "A-77", "weight": 41.5})], "tool_use"),
        _resp([_text("تم تسجيل 41.5 كجم.")]),
    ])
    _use_client(monkeypatch, fake)
    assert "تم" in claude_agent.run(owner, "سجل وزن A-77 41.5")
    assert AnimalWeight.query.one().weight == 41.5
    draft = AssistantDraftAction.query.one()
    assert draft.status == "confirmed" and draft.confirmed_by_id == owner.id


def test_expense_needs_confirmation_and_writes_nothing_first(app, owner, configured, monkeypatch):
    fake = FakeClient([
        _resp([_tool_use("record_expense", {"supplier": "مطحنة", "total_amount": 253, "category": "أعلاف"})],
              "tool_use"),
        _resp([_text("فاتورة مطحنة 253 ريال. أسجّلها؟")]),
    ])
    _use_client(monkeypatch, fake)
    claude_agent.run(owner, "سجل هذي الفاتورة")
    assert Finance.query.count() == 0
    draft = AssistantDraftAction.query.one()
    assert draft.status == "pending" and draft.input_source == "chat"


def test_confirm_requires_explicit_yes_in_current_message(app, owner, configured, monkeypatch):
    ctx = claude_agent._Ctx(owner, "كمّل")
    created = claude_agent._tool_record_expense(ctx, {"supplier": "س", "total_amount": 100, "category": "أعلاف"})
    out = claude_agent._tool_confirm_action(ctx, {"draft_id": created["draft_id"]})
    assert out["status"] == "refused" and Finance.query.count() == 0

    ctx_yes = claude_agent._Ctx(owner, "نعم")
    out = claude_agent._tool_confirm_action(ctx_yes, {"draft_id": created["draft_id"]})
    assert out["status"] == "done"
    assert Finance.query.one().amount == 100


def test_confirm_refuses_other_users_draft_and_expired(app, owner, worker, monkeypatch):
    ctx = claude_agent._Ctx(owner, "x")
    created = claude_agent._tool_record_expense(ctx, {"supplier": "س", "total_amount": 50, "category": "أعلاف"})
    other = claude_agent._tool_confirm_action(claude_agent._Ctx(worker, "نعم"), {"draft_id": created["draft_id"]})
    assert other["status"] == "error"

    draft = AssistantDraftAction.query.get(created["draft_id"])
    draft.created_at = draft.created_at - timedelta(minutes=claude_agent.CONFIRM_WINDOW_MINUTES + 5)
    db.session.commit()
    stale = claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "نعم"), {"draft_id": created["draft_id"]})
    assert stale["status"] == "error" and Finance.query.count() == 0


def test_confirm_cannot_be_used_to_skip_non_confirm_types(app, owner):
    make_animal("A-5")
    ctx = claude_agent._Ctx(owner, "نعم")
    draft = AssistantDraftAction(
        raw_text="x", parsed_action_type="record_weight",
        parsed_payload_json=AssistantDraftAction.encode_payload({"target_animal_no": "A-5", "weight": 30}),
        status="pending", created_by_id=owner.id)
    db.session.add(draft)
    db.session.commit()
    out = claude_agent._tool_confirm_action(ctx, {"draft_id": draft.id})
    assert out["status"] == "error" and AnimalWeight.query.count() == 0


def test_guardrail_blocks_absurd_amount(app, owner):
    out = claude_agent._tool_record_expense(claude_agent._Ctx(owner, "x"),
                                            {"supplier": "س", "total_amount": 9_000_000, "category": "أعلاف"})
    assert out["status"] == "rejected"
    assert AssistantDraftAction.query.count() == 0


def test_worker_without_permission_gets_forbidden_and_no_write_tool(app, worker, monkeypatch):
    out = claude_agent._tool_record_expense(claude_agent._Ctx(worker, "x"),
                                            {"supplier": "س", "total_amount": 10, "category": "أعلاف"})
    assert out["status"] == "forbidden" and Finance.query.count() == 0
    assert not claude_agent._write_tool_allowed(worker, "record_expense")


def test_assign_task_needs_known_unique_assignee(app, owner):
    ctx = claude_agent._Ctx(owner, "x")
    out = claude_agent._tool_assign_task(ctx, {"task_title": "فحص", "assignee_name": "غير موجود"})
    assert out["status"] == "error" and Task.query.count() == 0


def test_affirmative_detection():
    for yes in ("نعم", "نعم.", "ايوه سجلها", "أكد", "yes", "تمام"):
        assert claude_agent.is_affirmative(yes), yes
    for no in ("لا", "لا تسجلها", "ما ابي", "الغ", "no", "", "نعم بس غيّر المبلغ إلى ثلاثمية وخمسين ريال وغير المورد"):
        assert not claude_agent.is_affirmative(no), no


def test_api_failure_returns_none(app, owner, configured, monkeypatch):
    def boom():
        raise RuntimeError("down")
    monkeypatch.setattr(claude_agent, "_client", boom)
    assert claude_agent.run(owner, "كم راس؟") is None


def test_nlu_answer_uses_agent_then_falls_back(app, owner, configured, monkeypatch):
    monkeypatch.setattr(claude_agent, "run", lambda *a, **k: "رد الوكيل")
    out = nlu_service.answer(owner, "كم راس عندنا")
    assert out["reply"] == "رد الوكيل" and out["answered_by"] == "claude_agent"

    monkeypatch.setattr(claude_agent, "run", lambda *a, **k: None)
    out = nlu_service.answer(owner, "كم راس عندنا")
    assert out["answered_by"] != "claude_agent"


def test_voice_mode_adds_short_spoken_reply_instruction(app, owner, configured, monkeypatch):
    fake = FakeClient([_resp([_text("عندك اثنا عشر رأساً.")]), _resp([_text("ok")])])
    _use_client(monkeypatch, fake)
    claude_agent.run(owner, "كم راس؟", voice=True)
    claude_agent.run(owner, "كم راس؟")
    assert "وضع الصوت" in fake.calls[0]["system"]
    assert "وضع الصوت" not in fake.calls[1]["system"]


def test_send_route_passes_voice_flag_only_when_requested(app, logged_in_client, configured, monkeypatch):
    seen = []

    def fake_run(user, text, **kwargs):
        seen.append(kwargs.get("voice", False))
        return "تمام"
    monkeypatch.setattr(claude_agent, "run", fake_run)
    for payload in ({"message": "كم راس"}, {"message": "كم راس", "voice": True}):
        r = logged_in_client.post("/assistant/send", json=payload)
        assert r.status_code == 200 and r.get_json()["reply"] == "تمام"
    assert seen == [False, True]


def test_chat_page_has_voice_button_and_loop(app, logged_in_client):
    html = logged_in_client.get("/assistant/").get_data(as_text=True)
    assert 'id="voiceBtn"' in html and "SpeechRecognition" in html and "speechSynthesis" in html


# ---------------- الإجراءات الموسَّعة ----------------

def test_move_animal_executes_immediately_by_barn_name(app, owner):
    from factories import make_barn
    barn = make_barn("B-31", "حظيرة الشمال")
    animal = make_animal("A-31")
    out = claude_agent._tool_move_animal(claude_agent._Ctx(owner, "x"),
                                         {"animal_no": "A-31", "barn_name": "حظيرة الشمال"})
    assert out["status"] == "done"
    db.session.refresh(animal)
    assert animal.barn_id == barn.id


def test_move_animal_unknown_barn_reports_error_and_changes_nothing(app, owner):
    animal = make_animal("A-32")
    out = claude_agent._tool_move_animal(claude_agent._Ctx(owner, "x"),
                                         {"animal_no": "A-32", "barn_name": "غير موجودة"})
    assert out["status"] == "error"
    db.session.refresh(animal)
    assert animal.barn_id is None


def test_animal_note_and_farm_note_execute_immediately(app, owner):
    from app.models import AnimalNote, FarmNote
    make_animal("A-33")
    assert claude_agent._tool_add_animal_note(claude_agent._Ctx(owner, "x"),
                                              {"animal_no": "A-33", "note": "عرجان بسيط"})["status"] == "done"
    assert AnimalNote.query.one().note == "عرجان بسيط"
    assert claude_agent._tool_add_farm_note(claude_agent._Ctx(owner, "x"),
                                            {"body": "الحظيرة 2 تحتاج تنظيف", "title": "تنظيف"})["status"] == "done"
    assert FarmNote.query.one().body == "الحظيرة 2 تحتاج تنظيف"


def _force_stage_10(monkeypatch, animal):
    from app.core import cycle_engine
    cycle_engine.get_or_create_workflow(animal)

    def fake(a):
        wf = a.workflow
        wf.current_stage, wf.stage_name, wf.status = 10, "قرار المصير", "complete"
        return {"route": wf.route, "allowed_stage": 10, "completed_through": 10,
                "first_blocked_stage": None, "cycle_status": "complete",
                "missing_items": None, "out_of_order_count": 0}
    monkeypatch.setattr(cycle_engine, "evaluate", fake)


def test_sale_of_animal_not_at_exit_stage_is_blocked_by_cycle_gate(app, owner):
    animal = make_animal("A-39")
    first = claude_agent._tool_record_sale(claude_agent._Ctx(owner, "x"), {"animal_no": "A-39", "price": 900})
    done = claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "نعم"), {"draft_id": first["draft_id"]})
    assert done["status"] == "error" and "قرار المصير" in done["message"]
    db.session.refresh(animal)
    assert animal.status == "active" and Finance.query.count() == 0


def test_sale_needs_confirmation_then_sells_and_writes_finance(app, owner, monkeypatch):
    animal = make_animal("A-34")
    _force_stage_10(monkeypatch, animal)
    ctx = claude_agent._Ctx(owner, "بيع A-34 بـ 900")
    first = claude_agent._tool_record_sale(ctx, {"animal_no": "A-34", "price": 900})
    assert first["status"] == "needs_confirmation"
    db.session.refresh(animal)
    assert animal.status == "active" and Finance.query.count() == 0

    done = claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "نعم"), {"draft_id": first["draft_id"]})
    assert done["status"] == "done", done
    db.session.refresh(animal)
    assert animal.status == "sold"
    sale = Finance.query.filter_by(operation_type="sale").one()
    assert sale.amount == 900


def test_sale_guardrails_reject_missing_or_absurd_price(app, owner):
    make_animal("A-35")
    ctx = claude_agent._Ctx(owner, "x")
    assert claude_agent._tool_record_sale(ctx, {"animal_no": "A-35", "price": 0})["status"] == "rejected"
    assert claude_agent._tool_record_sale(ctx, {"animal_no": "A-35", "price": 9_999_999})["status"] == "rejected"
    assert claude_agent._tool_record_sale(ctx, {"animal_no": "", "price": 500})["status"] == "rejected"
    assert AssistantDraftAction.query.count() == 0


def test_death_and_vaccination_need_confirmation(app, owner):
    from app.models import Vaccination
    animal = make_animal("A-36")
    ctx = claude_agent._Ctx(owner, "x")
    dead = claude_agent._tool_record_death(ctx, {"animal_no": "A-36", "reason": "مرض"})
    vacc = claude_agent._tool_record_vaccination(ctx, {"animal_no": "A-36", "vaccine_name": "جدري"})
    assert dead["status"] == vacc["status"] == "needs_confirmation"
    db.session.refresh(animal)
    assert animal.status == "active" and Vaccination.query.count() == 0

    yes = claude_agent._Ctx(owner, "نعم")
    assert claude_agent._tool_confirm_action(yes, {"draft_id": vacc["draft_id"]})["status"] == "done"
    assert Vaccination.query.one().vaccine_name == "جدري"
    assert claude_agent._tool_confirm_action(yes, {"draft_id": dead["draft_id"]})["status"] == "done"
    db.session.refresh(animal)
    assert animal.status == "dead"


def test_sold_or_dead_animal_cannot_be_moved_or_sold_again(app, owner):
    animal = make_animal("A-37", status="sold")
    ctx = claude_agent._Ctx(owner, "x")
    out = claude_agent._tool_record_sale(ctx, {"animal_no": "A-37", "price": 500})
    assert out["status"] == "needs_confirmation"  # المسودة تُحفظ، والتنفيذ يرفض
    done = claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "نعم"), {"draft_id": out["draft_id"]})
    assert done["status"] == "error" and Finance.query.count() == 0


def test_complete_task_finishes_only_own_open_task(app, owner, worker):
    from app.models import Task
    from app.team import task_service
    mine = task_service.assign_task(actor=owner, title="تنظيف المعالف", assignee_id=owner.id)
    other = task_service.assign_task(actor=owner, title="فحص الماء", assignee_id=worker.id)
    ctx = claude_agent._Ctx(owner, "x")
    assert claude_agent._tool_complete_task(ctx, {"task_title": "تنظيف المعالف"})["status"] == "done"
    assert Task.query.get(mine.id).status == "done"
    miss = claude_agent._tool_complete_task(ctx, {"task_title": "فحص الماء"})
    assert miss["status"] == "error" and Task.query.get(other.id).status != "done"


def test_worker_cannot_sell_or_move(app, worker):
    make_animal("A-38")
    ctx = claude_agent._Ctx(worker, "x")
    assert claude_agent._tool_record_sale(ctx, {"animal_no": "A-38", "price": 500})["status"] == "forbidden"
    assert claude_agent._tool_move_animal(ctx, {"animal_no": "A-38", "barn_name": "س"})["status"] == "forbidden"
    assert not claude_agent._write_tool_allowed(worker, "record_sale")


# ---------------- الدفعة الثالثة ----------------

def test_milk_record_immediate_and_validates_session_and_amount(app, owner):
    from app.models import MilkRecord
    make_animal("A-41")
    ctx = claude_agent._Ctx(owner, "x")
    ok = claude_agent._tool_record_milk(ctx, {"animal_no": "A-41", "session": "صباح", "liters": 2})
    assert ok["status"] == "done" and MilkRecord.query.one().quantity_liters == 2
    bad_session = claude_agent._tool_record_milk(ctx, {"animal_no": "A-41", "session": "ظهر", "liters": 2})
    bad_amount = claude_agent._tool_record_milk(ctx, {"animal_no": "A-41", "session": "مساء", "liters": 250})
    assert bad_session["status"] == bad_amount["status"] == "error"
    assert MilkRecord.query.count() == 1


def test_start_task_only_for_own_pending_task(app, owner, worker):
    from app.models import Task
    from app.team import task_service
    mine = task_service.assign_task(actor=owner, title="رش الحظيرة", assignee_id=owner.id)
    out = claude_agent._tool_start_task(claude_agent._Ctx(owner, "x"), {"task_title": "رش الحظيرة"})
    assert out["status"] == "done" and Task.query.get(mine.id).status == "in_progress"
    miss = claude_agent._tool_start_task(claude_agent._Ctx(owner, "x"), {"task_title": "غير موجودة"})
    assert miss["status"] == "error"


def test_request_checkup_needs_named_assignee_and_creates_tasks(app, owner, worker):
    from app.models import Task
    make_animal("A-42")
    ctx = claude_agent._Ctx(owner, "x")
    nobody = claude_agent._tool_request_checkup(ctx, {"animal_no": "A-42", "items": ["قياس الحرارة"],
                                                      "assignee_name": "شخص غير موجود"})
    assert nobody["status"] == "error" and Task.query.count() == 0
    ok = claude_agent._tool_request_checkup(ctx, {"animal_no": "A-42", "items": ["قياس الحرارة", "فحص العين"],
                                                  "assignee_name": worker.name})
    assert ok["status"] == "done"
    assert Task.query.filter_by(task_type="animal_checkup").count() == 2


def test_set_purpose_needs_confirmation_and_validates_value(app, owner):
    animal = make_animal("A-43")
    ctx = claude_agent._Ctx(owner, "x")
    first = claude_agent._tool_set_purpose(ctx, {"animal_no": "A-43", "purpose": "تسمين"})
    assert first["status"] == "needs_confirmation"
    db.session.refresh(animal)
    assert animal.purpose is None
    assert claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "نعم"),
                                             {"draft_id": first["draft_id"]})["status"] == "done"
    db.session.refresh(animal)
    assert animal.purpose == "تسمين"
    bad = claude_agent._tool_set_purpose(ctx, {"animal_no": "A-43", "purpose": "ذبح"})
    done = claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "نعم"), {"draft_id": bad["draft_id"]})
    assert done["status"] == "error"


def test_send_to_market_is_gated_and_return_is_immediate(app, owner, monkeypatch):
    animal = make_animal("A-44")
    first = claude_agent._tool_send_to_market(claude_agent._Ctx(owner, "x"), {"animal_no": "A-44"})
    blocked = claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "نعم"), {"draft_id": first["draft_id"]})
    assert blocked["status"] == "error" and "قرار المصير" in blocked["message"]

    _force_stage_10(monkeypatch, animal)
    second = claude_agent._tool_send_to_market(claude_agent._Ctx(owner, "x"), {"animal_no": "A-44", "note": "سوق الخميس"})
    assert claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "نعم"),
                                             {"draft_id": second["draft_id"]})["status"] == "done"
    db.session.refresh(animal)
    assert animal.market_trip_started_at is not None
    back = claude_agent._tool_return_from_market(claude_agent._Ctx(owner, "x"), {"animal_no": "A-44"})
    assert back["status"] == "done"
    db.session.refresh(animal)
    assert animal.market_trip_started_at is None


def test_record_disease_needs_confirmation_and_creates_record(app, owner):
    from app.models import Disease
    make_animal("A-45")
    ctx = claude_agent._Ctx(owner, "x")
    first = claude_agent._tool_record_disease(ctx, {"animal_no": "A-45", "disease_name": "عرجان", "severity": "light"})
    assert first["status"] == "needs_confirmation" and Disease.query.count() == 0
    assert claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "نعم"),
                                             {"draft_id": first["draft_id"]})["status"] == "done"
    d = Disease.query.one()
    assert d.disease_name == "عرجان" and d.severity == "light"


# ---------------- التلقيح والحمل ----------------

def _yes(owner, tool, args):
    ctx = claude_agent._Ctx(owner, "x")
    first = getattr(claude_agent, tool)(ctx, args)
    assert first["status"] == "needs_confirmation", first
    return first, claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "نعم"), {"draft_id": first["draft_id"]})


def test_mating_needs_confirmation_then_creates_row_and_cycle_event(app, owner):
    from app.models import Mating
    female = make_animal("F-51", gender="أنثى")
    male = make_animal("M-51", gender="ذكر")
    first, done = _yes(owner, "_tool_record_mating", {"female_no": "F-51", "male_no": "M-51"})
    assert done["status"] == "done"
    row = Mating.query.one()
    assert row.female_id == female.id and row.male_id == male.id


def test_mating_blocked_for_close_relatives_and_wrong_sex(app, owner):
    from app.models import Mating
    male = make_animal("M-52", gender="ذكر")
    female = make_animal("F-52", gender="أنثى")
    female.father_id = male.id
    db.session.commit()
    _, rel = _yes(owner, "_tool_record_mating", {"female_no": "F-52", "male_no": "M-52"})
    assert rel["status"] == "error" and "قرابة" in rel["message"]

    make_animal("F-53", gender="أنثى")
    _, wrong = _yes(owner, "_tool_record_mating", {"female_no": "M-52", "male_no": "F-53"})
    assert wrong["status"] == "error"
    assert Mating.query.count() == 0


def test_mating_requires_a_male_or_external_description(app, owner):
    make_animal("F-54", gender="أنثى")
    _, out = _yes(owner, "_tool_record_mating", {"female_no": "F-54"})
    assert out["status"] == "error"
    _, ok = _yes(owner, "_tool_record_mating", {"female_no": "F-54", "male_note": "فحل جار"})
    assert ok["status"] == "done"


def test_pregnancy_links_latest_mating_and_blocks_duplicate_open_pregnancy(app, owner):
    from app.models import Pregnancy
    make_animal("F-55", gender="أنثى")
    make_animal("M-55", gender="ذكر")
    _yes(owner, "_tool_record_mating", {"female_no": "F-55", "male_no": "M-55"})
    _, done = _yes(owner, "_tool_record_pregnancy", {"female_no": "F-55", "confirmed": False, "embryo_count": 2})
    assert done["status"] == "done"
    p = Pregnancy.query.one()
    assert p.mating_id is not None and p.confirmed is False and p.embryo_count == 2
    _, dup = _yes(owner, "_tool_record_pregnancy", {"female_no": "F-55"})
    assert dup["status"] == "error" and Pregnancy.query.count() == 1


def test_pregnancy_embryo_count_is_bounded(app, owner):
    from app.models import Pregnancy
    make_animal("F-56", gender="أنثى")
    _, out = _yes(owner, "_tool_record_pregnancy", {"female_no": "F-56", "embryo_count": 12})
    assert out["status"] == "error" and Pregnancy.query.count() == 0


def test_confirm_pregnancy_flips_flag_once(app, owner):
    from app.models import Pregnancy
    make_animal("F-57", gender="أنثى")
    _yes(owner, "_tool_record_pregnancy", {"female_no": "F-57", "confirmed": False})
    assert Pregnancy.query.one().confirmed is False
    _, done = _yes(owner, "_tool_confirm_pregnancy", {"female_no": "F-57"})
    assert done["status"] == "done" and Pregnancy.query.one().confirmed is True
    _, again = _yes(owner, "_tool_confirm_pregnancy", {"female_no": "F-57"})
    assert again["status"] == "error"


def test_repro_tools_hidden_and_forbidden_without_repro_manage(app, worker):
    make_animal("F-58", gender="أنثى")
    assert not claude_agent._write_tool_allowed(worker, "record_mating")
    out = claude_agent._tool_record_pregnancy(claude_agent._Ctx(worker, "x"), {"female_no": "F-58"})
    assert out["status"] == "forbidden"


# ---------------- إجهاض + أدوات قراءة جديدة ----------------

def test_abortion_needs_confirmation_and_runs_isolation_protocol(app, owner):
    from app.models import Pregnancy
    from factories import make_barn
    isolation = make_barn("ISO-1", "حظيرة العزل", barn_type="عزل")
    female = make_animal("F-61", gender="أنثى")
    _yes(owner, "_tool_record_pregnancy", {"female_no": "F-61", "confirmed": True})
    first, done = _yes(owner, "_tool_record_abortion", {"female_no": "F-61", "notes": "تعثرت"})
    assert done["status"] == "done"
    p = Pregnancy.query.one()
    assert p.outcome == "abortion"
    db.session.refresh(female)
    assert female.barn_id == isolation.id


def test_abortion_without_open_pregnancy_is_rejected(app, owner):
    make_animal("F-62", gender="أنثى")
    _, out = _yes(owner, "_tool_record_abortion", {"female_no": "F-62"})
    assert out["status"] == "error"


def test_barn_summary_counts_and_ambiguity(app, owner):
    from app.assistant import agent_tools
    from factories import make_barn
    barn = make_barn("B-71", "حظيرة الأمهات")
    make_barn("B-72", "حظيرة الأمهات الجديدة")
    a1 = make_animal("A-71", gender="أنثى")
    a2 = make_animal("A-72", gender="ذكر")
    a1.barn_id = a2.barn_id = barn.id
    db.session.commit()
    assert agent_tools.barn_summary("حظيرة الأمهات") == {
        "status": "found", "barn_no": "B-71", "barn_name": "حظيرة الأمهات",
        "active_count": 2, "males": 1, "females": 1, "capacity": None}
    assert agent_tools.barn_summary("الأمهات")["status"] == "ambiguous"
    assert agent_tools.barn_summary("غير موجودة")["status"] == "not_found"


def test_milk_summary_totals_today_and_is_exposed_as_read_tool(app, owner):
    from app.assistant import agent_tools
    make_animal("A-73")
    ctx = claude_agent._Ctx(owner, "x")
    claude_agent._tool_record_milk(ctx, {"animal_no": "A-73", "session": "صباح", "liters": 2})
    claude_agent._tool_record_milk(ctx, {"animal_no": "A-73", "session": "مساء", "liters": 1.5})
    out = agent_tools.milk_summary(1)
    assert out["total_liters"] == 3.5 and out["records"] == 2
    defs, registry = claude_agent._read_tool_defs(owner)
    names = [d["name"] for d in defs]
    assert "barn_summary" in names and "milk_summary" in names
    milk_def = next(d for d in defs if d["name"] == "milk_summary")
    assert milk_def["input_schema"]["properties"]["days"]["type"] == "integer"


# ---------------- الافتراضي: يستشيرك قبل أي تنفيذ ----------------

def test_default_policy_consults_even_for_routine_actions(app, owner, monkeypatch):
    monkeypatch.delenv("AGENT_CONFIRM_TYPES", raising=False)
    make_animal("A-81")
    ctx = claude_agent._Ctx(owner, "سجل وزن A-81 40")
    first = claude_agent._tool_record_weight(ctx, {"animal_no": "A-81", "weight": 40})
    assert first["status"] == "needs_confirmation"
    assert AnimalWeight.query.count() == 0

    refused = claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "كمّل"), {"draft_id": first["draft_id"]})
    assert refused["status"] == "refused" and AnimalWeight.query.count() == 0

    done = claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "نعم"), {"draft_id": first["draft_id"]})
    assert done["status"] == "done" and AnimalWeight.query.one().weight == 40


def test_default_policy_assign_task_keeps_assignee_through_confirmation(app, owner, worker, monkeypatch):
    monkeypatch.delenv("AGENT_CONFIRM_TYPES", raising=False)
    ctx = claude_agent._Ctx(owner, "وزّع مهمة")
    first = claude_agent._tool_assign_task(ctx, {"task_title": "فحص الماء", "assignee_name": worker.name})
    assert first["status"] == "needs_confirmation" and Task.query.count() == 0
    done = claude_agent._tool_confirm_action(claude_agent._Ctx(owner, "نعم"), {"draft_id": first["draft_id"]})
    assert done["status"] == "done"
    assert Task.query.one().assignee_id == worker.id


def test_default_policy_prompt_and_tools_tell_model_to_consult(app, owner, configured, monkeypatch):
    monkeypatch.delenv("AGENT_CONFIRM_TYPES", raising=False)
    fake = FakeClient([_resp([_text("أسجّلها؟")])])
    _use_client(monkeypatch, fake)
    claude_agent.run(owner, "سجل وزن")
    assert "confirm_action" in [t["name"] for t in fake.calls[0]["tools"]]
    assert "needs_confirmation" in fake.calls[0]["system"] and "تستشيره" in fake.calls[0]["system"]


def test_none_switch_makes_everything_immediate_and_hides_confirm_tool(app, owner, configured, monkeypatch):
    monkeypatch.setenv("AGENT_CONFIRM_TYPES", "none")
    make_animal("A-82")
    out = claude_agent._tool_record_weight(claude_agent._Ctx(owner, "x"), {"animal_no": "A-82", "weight": 33})
    assert out["status"] == "done" and AnimalWeight.query.one().weight == 33
    fake = FakeClient([_resp([_text("تم")])])
    _use_client(monkeypatch, fake)
    claude_agent.run(owner, "x")
    assert "confirm_action" not in [t["name"] for t in fake.calls[0]["tools"]]


# ---------------- إضافة رأس بالصوت ----------------

def _create(owner, **overrides):
    args = {"animal_no": "N-501", "gender": "أنثى", "source": "purchase", "barn_name": "حظيرة الأمهات",
            "color": "بني"}
    args.update(overrides)
    return _yes(owner, "_tool_create_animal", args)


def test_create_animal_purchase_with_price_records_purchase_expense(app, owner):
    from app.models import Animal, AuditLog
    from factories import make_barn
    barn = make_barn("B-91", "حظيرة الأمهات")
    first, done = _create(owner, weight=34, price=900, breed="نجدي")
    assert done["status"] == "done"
    animal = Animal.query.filter_by(animal_no="N-501").one()
    assert animal.barn_id == barn.id and animal.gender == "أنثى" and animal.color == "بني"
    assert animal.price == 900 and animal.weight == 34 and animal.breed == "نجدي"
    purchase = Finance.query.filter_by(operation_type="purchase").one()
    assert purchase.amount == 900 and purchase.related_animal_id == animal.id
    assert AuditLog.query.filter_by(action="animal.create", entity_id=animal.id).count() == 1


def test_create_animal_requires_known_barn_color_and_gender(app, owner):
    from app.models import Animal
    from factories import make_barn
    make_barn("B-92", "حظيرة الأمهات")
    for overrides in ({"barn_name": "حظيرة وهمية"}, {"color": ""}, {"gender": "غير معروف"}):
        _, out = _create(owner, **overrides)
        assert out["status"] == "error", overrides
    assert Animal.query.filter_by(animal_no="N-501").count() == 0


def test_create_animal_blocks_duplicate_number_and_birth_source(app, owner):
    from factories import make_barn
    make_barn("B-93", "حظيرة الأمهات")
    make_animal("N-501")
    _, dup = _create(owner)
    assert dup["status"] == "error" and "مستخدم" in dup["message"]
    _, birth = _create(owner, animal_no="N-502", source="birth")
    assert birth["status"] == "error"


def test_create_animal_price_guardrail_and_permission(app, owner, worker):
    from factories import make_barn
    make_barn("B-94", "حظيرة الأمهات")
    out = claude_agent._tool_create_animal(
        claude_agent._Ctx(owner, "x"),
        {"animal_no": "N-503", "gender": "ذكر", "source": "purchase", "barn_name": "حظيرة الأمهات",
         "color": "أبيض", "price": 9_999_999})
    assert out["status"] == "rejected"
    denied = claude_agent._tool_create_animal(
        claude_agent._Ctx(worker, "x"),
        {"animal_no": "N-504", "gender": "ذكر", "source": "gift", "barn_name": "حظيرة الأمهات", "color": "أبيض"})
    assert denied["status"] == "forbidden"
    assert not claude_agent._write_tool_allowed(worker, "create_animal")


def test_create_animal_gift_has_no_finance_effect(app, owner):
    from app.models import Animal
    from factories import make_barn
    make_barn("B-95", "حظيرة الأمهات")
    _, done = _create(owner, animal_no="N-505", source="gift", gender="ذكر")
    assert done["status"] == "done"
    assert Animal.query.filter_by(animal_no="N-505").count() == 1
    assert Finance.query.count() == 0


# ---------------- تعديل رأس + شراء مخزون ----------------

def test_edit_animal_replaces_temp_number_and_logs_audit(app, owner):
    from app.models import Animal, AuditLog
    make_animal("TEMP-405-1")
    _, done = _yes(owner, "_tool_edit_animal", {"animal_no": "TEMP-405-1", "new_animal_no": "530", "color": "أسود"})
    assert done["status"] == "done"
    animal = Animal.query.filter_by(animal_no="530").one()
    assert animal.color == "أسود"
    assert Animal.query.filter_by(animal_no="TEMP-405-1").count() == 0
    log = AuditLog.query.filter_by(action="animal.edit", entity_id=animal.id).one()
    assert "TEMP-405-1 -> 530" in log.details


def test_edit_animal_rejects_duplicate_number_and_empty_change(app, owner):
    make_animal("E-1")
    make_animal("E-2")
    _, dup = _yes(owner, "_tool_edit_animal", {"animal_no": "E-1", "new_animal_no": "E-2"})
    assert dup["status"] == "error"
    _, nothing = _yes(owner, "_tool_edit_animal", {"animal_no": "E-1"})
    assert nothing["status"] == "error"


def test_feed_purchase_increases_stock_and_records_finance(app, owner):
    from factories import make_feed
    feed = make_feed("شعير", available_qty=100)
    _, done = _yes(owner, "_tool_record_stock_purchase",
                   {"kind": "feed", "item_name": "شعير", "quantity": 20, "unit_price": 3.5})
    assert done["status"] == "done"
    db.session.refresh(feed)
    assert feed.available_qty == 120
    fin = Finance.query.filter_by(operation_type="purchase").one()
    assert fin.amount == 70 and fin.category == "أعلاف" and fin.item == "شعير"


def test_stock_purchase_requires_price_for_feed_and_known_item(app, owner):
    from factories import make_feed
    make_feed("برسيم")
    _, no_price = _yes(owner, "_tool_record_stock_purchase", {"kind": "feed", "item_name": "برسيم", "quantity": 5})
    assert no_price["status"] == "error"
    _, missing = _yes(owner, "_tool_record_stock_purchase",
                      {"kind": "feed", "item_name": "ما له وجود", "quantity": 5, "unit_price": 2})
    assert missing["status"] == "error"
    assert Finance.query.count() == 0


def test_pharmacy_purchase_without_price_is_stock_only(app, owner):
    from factories import make_pharmacy
    item = make_pharmacy("فيتامين", available_qty=2)
    _, done = _yes(owner, "_tool_record_stock_purchase", {"kind": "pharmacy", "item_name": "فيتامين", "quantity": 4})
    assert done["status"] == "done"
    db.session.refresh(item)
    assert item.available_qty == 6 and Finance.query.count() == 0


def test_stock_purchase_guardrails_and_permissions(app, owner, worker):
    from factories import make_feed
    make_feed("ذرة")
    ctx = claude_agent._Ctx(owner, "x")
    assert claude_agent._tool_record_stock_purchase(
        ctx, {"kind": "feed", "item_name": "ذرة", "quantity": 100000, "unit_price": 100})["status"] == "rejected"
    assert claude_agent._tool_record_stock_purchase(
        ctx, {"kind": "feed", "item_name": "ذرة", "quantity": 0, "unit_price": 1})["status"] == "rejected"
    denied = claude_agent._tool_record_stock_purchase(
        claude_agent._Ctx(worker, "x"), {"kind": "feed", "item_name": "ذرة", "quantity": 5, "unit_price": 2})
    assert denied["status"] == "forbidden"
