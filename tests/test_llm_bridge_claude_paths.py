"""مسارات Claude للمهام الأحادية في llm_bridge (ترجمة، فاتورة، مسودة
نصية، روشتة): Claude أولاً لو ANTHROPIC_API_KEY مضبوط، ثم Gemini."""
import json
from types import SimpleNamespace

import pytest

from app.assistant import llm_bridge


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _tool(name, data):
    return SimpleNamespace(type="tool_use", name=name, input=data, id="t1")


def _resp(*blocks):
    return SimpleNamespace(content=list(blocks), stop_reason="end_turn")


@pytest.fixture()
def claude_on(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def _capture(monkeypatch, response):
    seen = {}

    def fake(**kwargs):
        seen.update(kwargs)
        return response
    monkeypatch.setattr(llm_bridge, "_claude_message", fake)
    return seen


def test_translate_text_uses_claude_fast_model(app, claude_on, monkeypatch):
    seen = _capture(monkeypatch, _resp(_text("Inspect the water")))
    assert llm_bridge.translate_text("افحص الماء", "en") == "Inspect the water"
    assert seen["model"] == llm_bridge.CLAUDE_FAST_MODEL


def test_translate_to_arabic_uses_claude(app, claude_on, monkeypatch):
    _capture(monkeypatch, _resp(_text("تم فحص الأغنام")))
    assert llm_bridge.translate_to_arabic("Sheep checked") == "تم فحص الأغنام"


def test_translate_returns_none_when_claude_and_gemini_both_unavailable(app, claude_on, monkeypatch):
    _capture(monkeypatch, None)
    assert llm_bridge.translate_text("افحص", "en") is None


def test_arabic_target_still_short_circuits_without_any_call(app, claude_on, monkeypatch):
    def boom(**kwargs):
        raise AssertionError("no call expected")
    monkeypatch.setattr(llm_bridge, "_claude_message", boom)
    assert llm_bridge.translate_text("نص", "ar") is None


def test_parse_invoice_reads_image_via_claude_tool_call(app, claude_on, monkeypatch):
    seen = _capture(monkeypatch, _resp(_tool(llm_bridge.INVOICE_TOOL_NAME, {
        "supplier": "مطحنة الخير", "invoice_date": "2026-09-01", "total_amount": 253,
        "category": "أعلاف", "description": "شعير", "summary_ar": "فاتورة مطحنة الخير 253"})))
    out = llm_bridge.parse_invoice(b"\x89PNG", "image/png")
    assert out["action_type"] == "record_expense"
    assert out["payload"]["total_amount"] == 253 and out["payload"]["supplier"] == "مطحنة الخير"
    assert "summary_ar" not in out["payload"] and out["summary_ar"] == "فاتورة مطحنة الخير 253"
    assert seen["content"][0]["type"] == "image"
    assert seen["model"] == llm_bridge.CLAUDE_VISION_MODEL


def test_parse_invoice_pdf_uses_document_block(app, claude_on, monkeypatch):
    seen = _capture(monkeypatch, _resp(_tool(llm_bridge.INVOICE_TOOL_NAME, {
        "total_amount": 10, "category": "أعلاف", "summary_ar": "x"})))
    llm_bridge.parse_invoice(b"%PDF-1.4", "application/pdf")
    assert seen["content"][0]["type"] == "document"
    assert seen["content"][0]["source"]["media_type"] == "application/pdf"


def test_parse_invoice_none_when_claude_unreadable_and_no_gemini(app, claude_on, monkeypatch):
    _capture(monkeypatch, _resp(_text("ما قدرت أقرأها")))
    assert llm_bridge.parse_invoice(b"x", "image/jpeg") is None


def test_parse_draft_action_text_via_claude(app, claude_on, monkeypatch):
    _capture(monkeypatch, _resp(_tool(llm_bridge.DRAFT_ACTION_TOOL_NAME, {
        "action_type": "record_weight", "target_animal_no": "405",
        "payload_json": json.dumps({"weight": 41}), "summary_ar": "وزن 41 للرأس 405"})))
    out = llm_bridge.parse_draft_action("وزن الشاة 405 صار 41")
    assert out == {"action_type": "record_weight",
                   "payload": {"weight": 41, "target_animal_no": "405"},
                   "summary_ar": "وزن 41 للرأس 405"}


def test_parse_draft_action_plain_text_reply_means_no_action(app, claude_on, monkeypatch):
    _capture(monkeypatch, _resp(_text("هذا النوع غير مدعوم")))
    assert llm_bridge.parse_draft_action("بيع الشاة") is None


def test_prescription_image_via_claude_validates_class(app, claude_on, monkeypatch):
    payload = {"name": "إيفومك", "medicine_class": "NOT_A_CLASS", "withdrawal_days": "28",
               "expiry_date": "2027-01-15", "withdrawal_days_milk": None}
    _capture(monkeypatch, _resp(_text("```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```")))
    out = llm_bridge.parse_pharmacy_prescription_image(b"x", "image/jpeg")
    assert out["name"] == "إيفومك" and out["medicine_class"] is None
    assert out["withdrawal_days"] == 28 and out["expiry_date"] == "2027-01-15"


def test_claude_message_returns_none_without_key(app, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm_bridge._claude_message(system="s", content="c", model="m") is None
