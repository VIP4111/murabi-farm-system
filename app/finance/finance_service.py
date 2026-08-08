"""
منطق الفواتير (بند إضافي 75، 2026-07-31) — تفرقة مقصودة حسب اتجاه
العملية: البيع تُصدر له فاتورة PDF من النظام نفسه (المزرعة هي البائع)،
والشراء/المصروف يُرفق له فاتورة المورّد الجاهزة (المزرعة هي المشتري،
ما تصدر فاتورة لنفسها). رقم الفاتورة يُبنى مرة وحدة عند أول إصدار
ويثبت بعدها — إعادة التنزيل ما تولّد رقم جديد.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.models import Finance
from app.core.cloud_storage_service import save_upload

ALLOWED_INVOICE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "pdf"}
MAX_INVOICE_BYTES = 8 * 1024 * 1024


def save_invoice_file(file_storage) -> str | None:
    """حفظ فاتورة مورّد مرفوعة (صورة أو PDF) — سحابياً (Cloudinary، بند
    إضافي 151) لو مضبوط، وإلا محلياً كما كان. إرفاق الفاتورة اختياري أصلاً."""
    return save_upload(file_storage, subfolder="invoices",
                        allowed_extensions=ALLOWED_INVOICE_EXTENSIONS, max_bytes=MAX_INVOICE_BYTES)


def _generate_invoice_number() -> str:
    year = datetime.now(timezone.utc).year
    count = Finance.query.filter(Finance.invoice_number.isnot(None)).count()
    return f"INV-{year}-{count + 1:04d}"


def issue_sale_invoice(finance_row: Finance) -> Finance:
    """يبني رقم فاتورة ثابت أول مرة بس — استدعاء ثاني (إعادة تنزيل) ما
    يغيّر الرقم ولا التاريخ."""
    if not finance_row.invoice_number:
        finance_row.invoice_number = _generate_invoice_number()
        finance_row.invoice_issued_at = datetime.now(timezone.utc)
        db.session.add(finance_row)
        db.session.commit()
    return finance_row
