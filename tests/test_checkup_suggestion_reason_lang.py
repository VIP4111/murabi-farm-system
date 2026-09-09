"""بند إصلاح (فحص عميق — نفس خلل ملخص "الإدخال الذكي" بالضبط) — سبب
اقتراح "الذكاء الاصطناعي" لبنود الفحص (`suggest_checkup_items`) كان
يُطلَب من Gemini عربي دائماً بغض النظر عن لغة صاحب الحلال اللي يشوف
البادج بصفحة الحيوان."""
from unittest.mock import patch

from app.assistant import llm_bridge
from app.core import routes as core_routes


def test_checkup_suggestion_prompt_requests_reason_in_english_for_english_lang(app):
    prompt = llm_bridge.CHECKUP_SUGGESTION_SYSTEM_PROMPT.format(lang_name="English")
    assert "English" in prompt


def test_checkup_suggestion_prompt_requests_reason_in_arabic_by_default(app):
    prompt = llm_bridge.CHECKUP_SUGGESTION_SYSTEM_PROMPT.format(
        lang_name=llm_bridge._TARGET_LANG_NAMES["ar"])
    assert "العربية" in prompt


def test_suggest_checkup_items_sends_english_instruction_to_gemini(app, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    fake_response = type("R", (), {"text": '{"items": ["بند 1"], "reason": "test"}'})()
    fake_client = type("C", (), {"models": type("M", (), {
        "generate_content": staticmethod(lambda **kwargs: fake_response)})()})()
    calls = {}

    def fake_generate_content(**kwargs):
        calls["config"] = kwargs.get("config")
        return fake_response

    fake_client.models.generate_content = fake_generate_content
    with patch("google.genai.Client", return_value=fake_client):
        result = llm_bridge.suggest_checkup_items("سياق", ["بند 1"], "en")
    assert result == {"items": ["بند 1"], "reason": "test"}
    assert "English" in calls["config"].system_instruction
