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
