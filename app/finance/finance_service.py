"""
منطق الفواتير (بند إضافي 75، 2026-07-31) — تفرقة مقصودة حسب اتجاه
العملية: البيع تُصدر له فاتورة PDF من النظام نفسه (المزرعة هي البائع)،
والشراء/المصروف يُرفق له فاتورة المورّد الجاهزة (المزرعة هي المشتري،
ما تصدر فاتورة لنفسها). رقم الفاتورة يُبنى مرة وحدة عند أول إصدار
ويثبت بعدها — إعادة التنزيل ما تولّد رقم جديد.
"""
import os
import uuid
from datetime import datetime, timezone

from flask import current_app

from app.extensions import db
from app.models import Finance

ALLOWED_INVOICE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "pdf"}
MAX_INVOICE_BYTES = 8 * 1024 * 1024


def save_invoice_file(file_storage) -> str | None:
    """حفظ فاتورة مورّد مرفوعة (صورة أو PDF) — نفس فلسفة save_evidence_image
    بالضبط: تخزين محلي بسيط، ترجع None بصمت لأي إدخال غير صالح، لأن
    إرفاق الفاتورة اختياري أصلاً."""
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_INVOICE_EXTENSIONS:
        return None
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0 or size > MAX_INVOICE_BYTES:
        return None

    upload_dir = os.path.join(current_app.config["UPLOAD_DIR"], "invoices")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(upload_dir, filename))
    return f"/uploads/invoices/{filename}"


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
