"""بند إضافي 75 — فاتورة البيع (تُصدر من النظام) + إرفاق فاتورة الشراء
(ملف جاهز) + استرجاع بيع. يعيد استخدام نمط _force_stage_10 الموثّق
بـtest_task_automation.py لتجاوز بوابات مراحل الدورة العشر."""
import io
from datetime import date

import pytest

from app.core import cycle_engine
from app.finance.finance_service import issue_sale_invoice
from app.reports.export_service import build_invoice_pdf
from app.extensions import db
from app.models import Finance, FarmSettings
from factories import make_animal


def _force_stage_10(animal):
    def _fake_evaluate(a):
        wf = a.workflow
        wf.current_stage = 10
        wf.stage_name = "قرار المصير"
        wf.status = "complete"
        return {
            "route": wf.route, "allowed_stage": 10, "completed_through": 10,
            "first_blocked_stage": None, "cycle_status": "complete",
            "missing_items": None, "out_of_order_count": 0,
        }
    return _fake_evaluate


def _sellable_animal(animal_no, monkeypatch):
    animal = make_animal(animal_no=animal_no, price=500)
    cycle_engine.get_or_create_workflow(animal)
    monkeypatch.setattr(cycle_engine, "evaluate", _force_stage_10(animal))
    return animal


def test_sell_animal_stores_buyer_and_no_invoice_flag(app, monkeypatch):
    animal = _sellable_animal("INV-01", monkeypatch)
    fin = cycle_engine.sell_animal(animal, sale_price=700, actor_user_id=1,
                                    buyer_name="أحمد", buyer_phone="0501111111", no_invoice=True)
    assert fin.buyer_name == "أحمد"
    assert fin.buyer_phone == "0501111111"
    assert fin.no_invoice is True
    assert fin.invoice_number is None


def test_issue_sale_invoice_assigns_number_once_and_is_idempotent(app, monkeypatch):
    animal = _sellable_animal("INV-02", monkeypatch)
    fin = cycle_engine.sell_animal(animal, sale_price=700, actor_user_id=1, buyer_name="سالم")
    assert fin.invoice_number is None

    issue_sale_invoice(fin)
    first_number = fin.invoice_number
    first_issued_at = fin.invoice_issued_at
    assert first_number is not None
    assert first_number.startswith(f"INV-{date.today().year}-")

    issue_sale_invoice(fin)
    assert fin.invoice_number == first_number
    assert fin.invoice_issued_at == first_issued_at


def test_build_invoice_pdf_produces_nonempty_pdf_bytes(app, monkeypatch):
    animal = _sellable_animal("INV-03", monkeypatch)
    fin = cycle_engine.sell_animal(animal, sale_price=700, actor_user_id=1, buyer_name="خالد")
    issue_sale_invoice(fin)
    buf = build_invoice_pdf(fin, animal, FarmSettings.get())
    data = buf.read()
    assert data.startswith(b"%PDF")
    assert len(data) > 500


def test_animal_sale_invoice_route_returns_pdf_and_assigns_number(app, logged_in_client, monkeypatch):
    animal = _sellable_animal("INV-04", monkeypatch)
    logged_in_client.post(f"/animals/{animal.id}/sell", data={
        "sale_price": "800", "buyer_name": "منصور", "buyer_phone": "0502222222",
    })
    resp = logged_in_client.get(f"/animals/{animal.id}/sale-invoice")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    fin = Finance.query.filter_by(related_animal_id=animal.id, operation_type="sale").first()
    assert fin.invoice_number is not None


def test_animal_sale_invoice_route_rejects_no_invoice_sale(app, logged_in_client, monkeypatch):
    animal = _sellable_animal("INV-05", monkeypatch)
    logged_in_client.post(f"/animals/{animal.id}/sell", data={
        "sale_price": "800", "no_invoice": "1",
    })
    resp = logged_in_client.get(f"/animals/{animal.id}/sale-invoice", follow_redirects=True)
    assert resp.status_code == 200
    assert "بدون فاتورة".encode() in resp.data
    fin = Finance.query.filter_by(related_animal_id=animal.id, operation_type="sale").first()
    assert fin.invoice_number is None


def test_finance_cancel_on_sale_restores_animal_to_active(app, logged_in_client, monkeypatch):
    animal = _sellable_animal("INV-06", monkeypatch)
    logged_in_client.post(f"/animals/{animal.id}/sell", data={"sale_price": "800"})
    assert animal.status == "sold"
    fin = Finance.query.filter_by(related_animal_id=animal.id, operation_type="sale").first()

    logged_in_client.post(f"/finance/{fin.id}/cancel", data={"reason": "البيع ما تم"})
    db.session.refresh(animal)
    db.session.refresh(fin)
    assert animal.status == "active"
    assert fin.is_cancelled is True


def test_finance_new_saves_attached_invoice_file(app, logged_in_client):
    data = {
        "date": date.today().isoformat(), "operation_type": "purchase",
        "amount": "150", "invoice_file": (io.BytesIO(b"%PDF-1.4 fake"), "supplier_invoice.pdf"),
    }
    logged_in_client.post("/finance/new", data=data, content_type="multipart/form-data")
    row = Finance.query.filter_by(operation_type="purchase", amount=150).first()
    assert row is not None
    assert row.invoice_file_url is not None
    assert row.invoice_file_url.endswith(".pdf")


def test_animal_purchase_with_invoice_file_attaches_to_finance_row(app, logged_in_client):
    from factories import make_barn
    barn = make_barn(barn_no="INVB-01")
    data = {
        "animal_no": "PUR-INV-01", "source": "purchase", "gender": "أنثى",
        "barn_id": str(barn.id), "color": "أبيض", "price": "600",
        "purchase_date": date.today().isoformat(),
        "invoice_file": (io.BytesIO(b"\xff\xd8\xff fake jpg"), "invoice.jpg"),
    }
    logged_in_client.post("/animals/new", data=data, content_type="multipart/form-data")
    row = Finance.query.filter_by(operation_type="purchase", item="شراء PUR-INV-01").first()
    assert row is not None
    assert row.invoice_file_url is not None
    assert row.invoice_file_url.endswith(".jpg")


def test_farm_identity_save(app, logged_in_client):
    logged_in_client.post("/settings/farm-identity", data={
        "farm_name": "مزرعة الاختبار", "farm_phone": "0500000000", "farm_address": "الرياض",
    })
    fs = FarmSettings.get()
    assert fs.farm_name == "مزرعة الاختبار"
    assert fs.farm_phone == "0500000000"
    assert fs.farm_address == "الرياض"
