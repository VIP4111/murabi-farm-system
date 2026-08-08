"""بند إضافي 154 — طلبك: تقرير مشتريات مستقل بقسم التقارير (نفس بنية
تقرير المبيعات: قائمة عمليات + إجماليات + تصنيف + تصدير)، يشمل رابط
الفاتورة/الملف المرفق داخل نفس التقرير."""
from datetime import date

from app.extensions import db
from app.models import Finance
from app.reports.report_service import purchases_report, REPORTS


def _add_finance(operation_type, amount, category=None, invoice_file_url=None, is_cancelled=False):
    row = Finance(
        date=date.today(), operation_type=operation_type, amount=amount,
        category=category, invoice_file_url=invoice_file_url, is_cancelled=is_cancelled,
    )
    db.session.add(row)
    db.session.commit()
    return row


def test_purchases_report_lists_purchase_and_expense_rows(app):
    _add_finance("purchase", 500, category="حيوانات")
    _add_finance("expense", 100, category="أدوية")
    _add_finance("sale", 9999)  # ما يفترض يظهر

    data = purchases_report(date.today(), date.today())
    assert len(data["table"]["rows"]) == 2


def test_purchases_report_excludes_cancelled_rows(app):
    _add_finance("purchase", 300, is_cancelled=True)
    data = purchases_report(date.today(), date.today())
    assert data["table"]["rows"] == []


def test_purchases_report_includes_invoice_link_column(app):
    _add_finance("purchase", 500, invoice_file_url="https://res.cloudinary.com/x/invoice.pdf")
    data = purchases_report(date.today(), date.today())
    assert data["table"]["columns"][-1] == "الفاتورة المرفقة"
    assert data["table"]["rows"][0][-1] == "https://res.cloudinary.com/x/invoice.pdf"


def test_purchases_report_row_without_invoice_shows_dash(app):
    _add_finance("expense", 50)
    data = purchases_report(date.today(), date.today())
    assert data["table"]["rows"][0][-1] == "-"


def test_purchases_report_category_breakdown(app):
    _add_finance("purchase", 200, category="حيوانات")
    _add_finance("expense", 100, category="حيوانات")
    _add_finance("expense", 50, category="أدوية")

    data = purchases_report(date.today(), date.today())
    breakdown = dict(data["category_breakdown"])
    assert breakdown["حيوانات"] == 300
    assert breakdown["أدوية"] == 50


def test_purchases_registered_in_reports_dict():
    assert "purchases" in REPORTS
    assert REPORTS["purchases"][0] == "تقرير المشتريات"


def test_purchases_report_page_renders(logged_in_client):
    resp = logged_in_client.get("/reports/purchases")
    assert resp.status_code == 200
    assert "تقرير المشتريات" in resp.get_data(as_text=True)


def test_purchases_report_excel_export_works(logged_in_client):
    resp = logged_in_client.get("/reports/purchases/export/xlsx")
    assert resp.status_code == 200
