"""الإدخال الذكي بالفاتورة: صورة/PDF ← قراءة ← مسودة مصروف ← اعتماد بشري
← صف مالية. نفس مسار مسودات النص/الصوت (بنفس الحواجز)، بقيود إضافية:
المبلغ، الصلاحية المالية، ونوع/حجم الملف."""
import io
from types import SimpleNamespace

import pytest

from app.assistant import draft_action_service, llm_bridge
from app.extensions import db
from app.models import AssistantDraftAction, Finance, Role, User


def _parsed(amount=230.5, category="أعلاف", supplier="مطحنة الخير", description="شعير 10 أكياس"):
    return {
        "action_type": "record_expense",
        "payload": {"supplier": supplier, "invoice_date": "2026-09-01", "total_amount": amount,
                    "category": category, "description": description},
        "summary_ar": f"فاتورة {supplier} بمبلغ {amount}",
    }


def test_invoice_type_is_in_both_allowed_lists_and_not_in_text_parser(app):
    assert "record_expense" in llm_bridge.ALLOWED_DRAFT_ACTION_TYPES
    assert "record_expense" in draft_action_service.ALLOWED_ACTION_TYPES
    assert "record_expense" not in llm_bridge.TEXT_DRAFT_ACTION_TYPES


def test_propose_from_invoice_saves_pending_draft(app, owner, monkeypatch):
    monkeypatch.setattr(llm_bridge, "parse_invoice", lambda b, m, lang="ar": _parsed())
    draft = draft_action_service.propose_from_invoice(b"x", "image/jpeg", created_by=owner,
                                                      invoice_file_url="/uploads/invoices/a.jpg")
    assert draft.status == "pending"
    assert draft.parsed_action_type == "record_expense"
    assert draft.input_source == "invoice"
    assert draft.get_payload()["invoice_file_url"] == "/uploads/invoices/a.jpg"


def test_unreadable_invoice_is_auto_rejected_and_writes_nothing(app, owner, monkeypatch):
    monkeypatch.setattr(llm_bridge, "parse_invoice", lambda b, m, lang="ar": None)
    draft = draft_action_service.propose_from_invoice(b"x", "image/jpeg", created_by=owner)
    assert draft.status == "auto_rejected"
    assert Finance.query.count() == 0


@pytest.mark.parametrize("amount", [0, -5, 900000, "abc"])
def test_guardrail_rejects_bad_amounts(app, owner, monkeypatch, amount):
    monkeypatch.setattr(llm_bridge, "parse_invoice", lambda b, m, lang="ar": _parsed(amount=amount))
    draft = draft_action_service.propose_from_invoice(b"x", "image/jpeg", created_by=owner)
    assert draft.status == "auto_rejected"


def test_medicine_invoice_is_not_killed_by_dose_keyword_blocklist(app, owner, monkeypatch):
    parsed = _parsed(category="أدوية", supplier="صيدلية الأمل", description="دواء علاج ديدان - جرعة")
    monkeypatch.setattr(llm_bridge, "parse_invoice", lambda b, m, lang="ar": parsed)
    draft = draft_action_service.propose_from_invoice(b"x", "image/jpeg", created_by=owner)
    assert draft.status == "pending"


def test_confirm_creates_expense_row_only_after_approval(app, owner, monkeypatch):
    monkeypatch.setattr(llm_bridge, "parse_invoice", lambda b, m, lang="ar": _parsed())
    draft = draft_action_service.propose_from_invoice(b"x", "image/jpeg", created_by=owner,
                                                      invoice_file_url="/uploads/invoices/a.jpg")
    assert Finance.query.count() == 0  # لا كتابة قبل الاعتماد

    draft_action_service.confirm_draft(draft, actor=owner)
    row = Finance.query.one()
    assert row.operation_type == "expense"
    assert row.amount == 230.5
    assert row.item == "مطحنة الخير"
    assert row.category == "أعلاف"
    assert row.invoice_file_url == "/uploads/invoices/a.jpg"
    assert str(row.date) == "2026-09-01"


def test_confirm_rejects_future_invoice_date(app, owner, monkeypatch):
    parsed = _parsed()
    parsed["payload"]["invoice_date"] = "2099-01-01"
    monkeypatch.setattr(llm_bridge, "parse_invoice", lambda b, m, lang="ar": parsed)
    draft = draft_action_service.propose_from_invoice(b"x", "image/jpeg", created_by=owner)
    with pytest.raises(ValueError):
        draft_action_service.confirm_draft(draft, actor=owner)
    assert Finance.query.count() == 0


def test_confirm_requires_finance_permission(app, owner, monkeypatch):
    role = Role.query.filter_by(name="worker").first()
    worker = User(name="عامل", phone="0500007777", role_id=role.id, language="ar", is_active_account=True)
    worker.set_password("pass1234")
    db.session.add(worker)
    db.session.commit()
    monkeypatch.setattr(llm_bridge, "parse_invoice", lambda b, m, lang="ar": _parsed())
    draft = draft_action_service.propose_from_invoice(b"x", "image/jpeg", created_by=owner)
    with pytest.raises(PermissionError):
        draft_action_service.confirm_draft(draft, actor=worker)
    assert Finance.query.count() == 0


def test_extract_invoice_call_reads_tool_args(app):
    fc = SimpleNamespace(name=llm_bridge.INVOICE_TOOL_NAME,
                         args={"total_amount": 99.0, "category": "معدات", "supplier": "س", "summary_ar": "ملخص"})
    resp = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(function_call=fc)]))])
    out = llm_bridge._extract_invoice_call(resp)
    assert out["action_type"] == "record_expense"
    assert out["payload"]["total_amount"] == 99.0
    assert out["summary_ar"] == "ملخص"


def test_parse_invoice_returns_none_without_key(app, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm_bridge.parse_invoice(b"x", "image/jpeg") is None


def test_route_rejects_missing_and_unsupported_file(logged_in_client):
    r = logged_in_client.post("/assistant/drafts/new-invoice", data={}, follow_redirects=True)
    assert r.status_code == 200
    r = logged_in_client.post("/assistant/drafts/new-invoice",
                              data={"invoice": (io.BytesIO(b"hello"), "a.txt", "text/plain")},
                              content_type="multipart/form-data", follow_redirects=True)
    assert r.status_code == 200
    assert AssistantDraftAction.query.count() == 0


def test_route_creates_pending_draft(logged_in_client, monkeypatch):
    monkeypatch.setattr(llm_bridge, "parse_invoice", lambda b, m, lang="ar": _parsed())
    r = logged_in_client.post("/assistant/drafts/new-invoice",
                              data={"invoice": (io.BytesIO(b"\xff\xd8fakejpeg"), "inv.jpg", "image/jpeg")},
                              content_type="multipart/form-data", follow_redirects=True)
    assert r.status_code == 200
    draft = AssistantDraftAction.query.one()
    assert draft.status == "pending" and draft.parsed_action_type == "record_expense"
