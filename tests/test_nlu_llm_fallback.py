"""بند إضافي 84 — يتحقق إن answer() فعلياً توصل لـllm_bridge لما ما فيه
تطابق محلي (نية أو قاعدة معرفة)، وترجع للـfallback المحلي لو llm_bridge
رجّعت None (بدون مفتاح، أو أي خطأ) — أول اختبار لهذا المسار كامل."""
from app.assistant import nlu_service


def test_answer_falls_through_to_llm_bridge_when_nothing_matches_locally(monkeypatch, owner):
    monkeypatch.setattr(nlu_service.llm_bridge, "ask", lambda q, ctx: "رد من Claude التجريبي")
    result = nlu_service.answer(owner, "سؤال غريب جداً ما يطابق أي نية معروفة زطزط")
    assert result["answered_by"] == "llm"
    assert result["reply"] == "رد من Claude التجريبي"
    assert result["intent_code"] is None


def test_answer_uses_local_fallback_when_llm_bridge_returns_none(monkeypatch, owner):
    monkeypatch.setattr(nlu_service.llm_bridge, "ask", lambda q, ctx: None)
    result = nlu_service.answer(owner, "سؤال غريب جداً ما يطابق أي نية معروفة زطزط")
    assert result["answered_by"] == "local"
    assert result["reply"] == nlu_service.FALLBACK_MSG


def test_answer_prefers_local_intent_over_llm(monkeypatch, owner):
    """تأكيد ترتيب المحاولة الصحيح: نية محلية معروفة (زي عدد الحيوانات)
    ما توصل أبداً لـllm_bridge، حتى لو مفعَّلة."""
    called = {"count": 0}

    def fake_ask(q, ctx):
        called["count"] += 1
        return "ما كان لازم توصل هنا"

    monkeypatch.setattr(nlu_service.llm_bridge, "ask", fake_ask)
    result = nlu_service.answer(owner, "كم عدد الحيوانات؟")
    assert result["answered_by"] == "local"
    assert called["count"] == 0
