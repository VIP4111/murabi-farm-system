"""بند إضافي 297 — المرحلة ٢ من خطة "عقل المزرعة": أدوات قراءة ذكية
لـGemini (Function Calling). تغطي: التوضيح عند تعدد النتائج
(تحسينك الأول المعتمد)، فحص الصلاحيات قبل عرض الأداة أصلاً، والقراءة
المباشرة من الجداول الحقيقية بدون أي كتابة."""
from datetime import date
from unittest.mock import patch, MagicMock

from app.extensions import db
from app.assistant import agent_tools, llm_bridge, nlu_service
from app.models import Role, User, Disease, AnimalWeight
from factories import make_animal, make_barn


def _make_role_user(role_name, phone):
    role = Role.query.filter_by(name=role_name).first()
    user = User(name=f"مستخدم {role_name}", phone=phone, role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


# ---- search_animal_or_barn: التوضيح عند تعدد النتائج ----

def test_search_unique_animal_number_found(app):
    make_barn(barn_no="B-01", barn_name="حظيرة الحوامل")
    make_animal(animal_no="X-405")
    result = agent_tools.search_animal_or_barn("405")
    assert result["status"] == "found"
    assert result["type"] == "animal"


def test_search_ambiguous_multiple_matches_asks_for_clarification(app):
    make_animal(animal_no="1405")
    make_animal(animal_no="2405")
    result = agent_tools.search_animal_or_barn("405")
    assert result["status"] == "ambiguous"
    assert len(result["candidates"]) == 2


def test_search_not_found(app):
    result = agent_tools.search_animal_or_barn("لا-يوجد-9999")
    assert result["status"] == "not_found"


def test_search_ambiguous_across_animal_and_barn(app):
    make_barn(barn_no="B-405", barn_name="حظيرة اختبار")
    make_animal(animal_no="405")
    result = agent_tools.search_animal_or_barn("405")
    assert result["status"] == "ambiguous"


# ---- herd_summary / animal_history / finance_summary ----

def test_herd_summary_includes_pregnancy_counts(app):
    make_animal(animal_no="A-1")
    result = agent_tools.herd_summary()
    assert result["total_active"] == 1
    assert "pregnant_count" in result


def test_animal_history_exact_match_only(app):
    animal = make_animal(animal_no="A-405")
    db.session.add(Disease(animal_id=animal.id, disease_name="جرب", status="active", date=date.today()))
    db.session.add(AnimalWeight(animal_id=animal.id, weight=30, date=date.today()))
    db.session.commit()

    result = agent_tools.animal_history("A-405")
    assert result["status"] == "found"
    assert result["open_diseases"][0]["disease_name"] == "جرب"
    assert len(result["recent_weights"]) == 1


def test_animal_history_not_found_for_partial_number(app):
    make_animal(animal_no="A-405")
    result = agent_tools.animal_history("405")  # مطابقة تامة بس، مو جزئية
    assert result["status"] == "not_found"


def test_finance_summary_rejects_bad_date_format(app):
    result = agent_tools.finance_summary("2026/01/01", "2026-02-01")
    assert result["status"] == "error"


def test_finance_summary_valid_range_returns_totals(app):
    result = agent_tools.finance_summary("2026-01-01", "2026-12-31")
    assert result["status"] == "found"
    assert "net" in result


# ---- الصلاحيات: الأداة ما تظهر أصلاً بدون الصلاحية ----

def test_worker_without_finance_permission_does_not_get_finance_tool(app):
    worker = _make_role_user("worker", "0599999180")
    tools = agent_tools.build_tools_for_user(worker)
    assert agent_tools.finance_summary not in tools
    assert agent_tools.herd_summary not in tools  # العامل ما يملك animals.view أصلاً


def test_doctor_gets_herd_but_not_finance_tool(app):
    doctor = _make_role_user("doctor", "0599999181")
    tools = agent_tools.build_tools_for_user(doctor)
    assert agent_tools.herd_summary in tools  # animals.view متاحة للدكتور
    assert agent_tools.finance_summary not in tools


def test_owner_gets_all_tools(app, owner):
    tools = agent_tools.build_tools_for_user(owner)
    assert agent_tools.finance_summary in tools
    assert agent_tools.search_animal_or_barn in tools


# ---- llm_bridge.ask_with_tools ----

def test_ask_with_tools_returns_none_without_api_key(app, owner, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm_bridge.ask_with_tools("كم رأس عندي؟", owner) is None


def test_ask_with_tools_returns_gemini_text_when_configured(app, owner, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")
    fake_response = MagicMock(text="عندك 5 رؤوس نشطة.")
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    with patch("google.genai.Client", return_value=fake_client):
        reply = llm_bridge.ask_with_tools("كم رأس عندي؟", owner)
    assert reply == "عندك 5 رؤوس نشطة."


def test_ask_with_tools_swallows_exceptions_and_returns_none(app, owner, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")
    with patch("google.genai.Client", side_effect=RuntimeError("network down")):
        assert llm_bridge.ask_with_tools("كم رأس عندي؟", owner) is None


# ---- nlu_service.answer(): Gemini أولاً، ثم Claude، ثم fallback محلي ----

def test_answer_uses_gemini_tools_reply_when_available(app, owner, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")
    with patch("app.assistant.llm_bridge.ask_with_tools", return_value="جواب من Gemini بالأدوات"):
        result = nlu_service.answer(owner, "زطركش بلوق فنتاسيا 999 لا معنى له إطلاقاً")
    assert result["reply"] == "جواب من Gemini بالأدوات"
    assert result["answered_by"] == "llm_tools"
