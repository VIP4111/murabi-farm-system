"""رمز QR بأسلوب هيئة الزكاة والضريبة والجمارك السعودية — المرحلة
الأولى فقط (بند إضافي 184).

**تحذير قانوني صريح، اقرأه قبل أي استخدام فعلي**: هذا **ترميز QR
مبسّط بصيغة TLV** يحتوي الحقول الخمسة المطلوبة بالمرحلة الأولى
(اسم البائع، الرقم الضريبي، الطابع الزمني، إجمالي الفاتورة، إجمالي
الضريبة) — نفس أسلوب الفوترة الإلكترونية المبسّطة (Simplified Tax
Invoice) بالمرحلة الأولى من نظام "فاتورة".

**ما هذا مو**: هذا **ليس** ربطاً فعلياً بمنصة "فاتورة" التابعة
للهيئة (Phase 2 — يحتاج شهادة CSID معتمدة، توقيع رقمي مشفَّر، وربط
API حي بالهيئة). ولا يضمن أهلية بيع الحلال أصلاً لضريبة القيمة
المضافة من عدمها (يعتمد على تصنيف نشاطك الضريبي — راجع محاسبك). صاحب
الحلال مسؤول عن التحقق من التزامه الفعلي مع الهيئة قبل اعتماد أي
فاتورة صادرة هنا كمستند ضريبي رسمي."""
import base64
import io
from datetime import datetime

import qrcode


def _tlv(tag: int, value: str) -> bytes:
    value_bytes = value.encode("utf-8")
    return bytes([tag, len(value_bytes)]) + value_bytes


def build_qr_base64(*, seller_name: str, vat_number: str, timestamp: datetime,
                     invoice_total: float, vat_total: float) -> str:
    """يبني السلسلة المرمَّزة بصيغة Base64 (TLV) — نفس الصيغة اللي
    يقرأها تطبيق التحقق الرسمي من الهيئة لو مسحها المستخدم."""
    payload = (
        _tlv(1, seller_name)
        + _tlv(2, vat_number)
        + _tlv(3, timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"))
        + _tlv(4, f"{invoice_total:.2f}")
        + _tlv(5, f"{vat_total:.2f}")
    )
    return base64.b64encode(payload).decode("ascii")


def build_qr_image(qr_base64: str) -> io.BytesIO:
    img = qrcode.make(qr_base64)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def invoice_qr_image(*, farm_settings, invoice_total: float, vat_rate: float = 0.0,
                      timestamp: datetime | None = None) -> io.BytesIO | None:
    """يرجّع صورة QR جاهزة للفاتورة، أو None لو صاحب الحلال ما سجّل
    رقم ضريبي أصلاً (يعني مو مسجَّل بضريبة القيمة المضافة — لا داعي
    لأي رمز). `vat_rate` صفر افتراضياً عمداً — النظام ما يفترض 15%
    تلقائياً لأن تصنيف بيع الحلال الضريبي قرار محاسبي، مو تقنياً."""
    if not farm_settings.vat_number:
        return None
    vat_total = round(invoice_total * vat_rate, 2)
    qr_b64 = build_qr_base64(
        seller_name=farm_settings.farm_name or "-",
        vat_number=farm_settings.vat_number,
        timestamp=timestamp or datetime.utcnow(),
        invoice_total=invoice_total, vat_total=vat_total,
    )
    return build_qr_image(qr_b64)
