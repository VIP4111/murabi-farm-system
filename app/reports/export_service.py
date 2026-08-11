"""
تصدير التقارير PDF/Excel (بند 22). خط عربي مُرفَق بالمشروع
(app/static/fonts/NotoNaskhArabic-Regular.ttf) عشان التصدير يشتغل بأي
بيئة نشر بدون الاعتماد على خطوط النظام.
"""
import io
import os
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

_FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "fonts", "NotoNaskhArabic-Regular.ttf")
_font_registered = False


def _ensure_font():
    global _font_registered
    if not _font_registered:
        pdfmetrics.registerFont(TTFont("Arabic", _FONT_PATH))
        _font_registered = True


def ar(text) -> str:
    if text is None:
        return ""
    return get_display(arabic_reshaper.reshape(str(text)))


def build_excel(title: str, columns: list[str], rows: list[list]) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = (title or "تقرير")[:31]
    ws.sheet_view.rightToLeft = True
    # تحويل صريح لـstr() هنا (بند إضافي 165) — عناوين الأعمدة صارت
    # نصوص مترجمة (Flask-Babel LazyString)، وopenpyxl ما يقدر يكتبها
    # مباشرة بالخلية (يرفض أي نوع غير str/رقم/تاريخ صراحة).
    columns = [str(c) for c in columns]
    ws.append(columns)
    for row in rows:
        ws.append([str(cell) if cell is not None else "" for cell in row])
    for i, col in enumerate(columns, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(14, len(str(col)) + 6)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def build_pdf(title: str, columns: list[str], rows: list[list], subtitle: str | None = None) -> io.BytesIO:
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    right_margin = width - 15 * mm
    left_margin = 15 * mm
    y = height - 20 * mm

    c.setFont("Arabic", 16)
    c.drawRightString(right_margin, y, ar(title))
    y -= 8 * mm
    if subtitle:
        c.setFont("Arabic", 10)
        c.drawRightString(right_margin, y, ar(subtitle))
        y -= 8 * mm

    n_cols = max(len(columns), 1)
    col_width = (right_margin - left_margin) / n_cols

    def draw_header(yy):
        c.setFont("Arabic", 9)
        for i, col in enumerate(columns):
            x = right_margin - i * col_width
            c.drawRightString(x, yy, ar(col))
        c.line(left_margin, yy - 2 * mm, right_margin, yy - 2 * mm)
        return yy - 7 * mm

    y = draw_header(y)
    c.setFont("Arabic", 8.5)
    for row in rows:
        if y < 20 * mm:
            c.showPage()
            y = height - 20 * mm
            y = draw_header(y)
            c.setFont("Arabic", 8.5)
        for i, val in enumerate(row):
            x = right_margin - i * col_width
            c.drawRightString(x, y, ar(val))
        y -= 6 * mm

    if not rows:
        c.drawRightString(right_margin, y, ar("لا يوجد بيانات لهذه الفترة."))

    c.save()
    buf.seek(0)
    return buf


def build_invoice_pdf(finance_row, animal, farm_settings) -> io.BytesIO:
    """فاتورة بيع رسمية (بند إضافي 75) — المزرعة بائع، تصدر لمشترٍ. تخطيط
    مستند مفرد (رأس/طرفين/بند واحد/إجمالي) مو جدول تقرير، بس بنفس خط
    وأدوات build_pdf أعلاه (الخط العربي المسجَّل مرة وحدة، ودالة ar())."""
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    right_margin = width - 20 * mm
    left_margin = 20 * mm
    y = height - 25 * mm

    c.setFont("Arabic", 18)
    c.drawRightString(right_margin, y, ar("فاتورة بيع"))
    y -= 8 * mm
    c.setFont("Arabic", 11)
    c.drawRightString(right_margin, y, ar(f"رقم الفاتورة: {finance_row.invoice_number}"))
    y -= 6 * mm
    c.drawRightString(right_margin, y, ar(f"التاريخ: {finance_row.date}"))
    y -= 12 * mm

    c.line(left_margin, y, right_margin, y)
    y -= 10 * mm

    c.setFont("Arabic", 12)
    c.drawRightString(right_margin, y, ar("البائع"))
    y -= 6 * mm
    c.setFont("Arabic", 10)
    for line in (farm_settings.farm_name, farm_settings.farm_phone, farm_settings.farm_address):
        if line:
            c.drawRightString(right_margin, y, ar(line))
            y -= 5.5 * mm
    if not (farm_settings.farm_name or farm_settings.farm_phone or farm_settings.farm_address):
        c.drawRightString(right_margin, y, ar("مراح بو علي"))
        y -= 5.5 * mm

    y -= 6 * mm
    c.setFont("Arabic", 12)
    c.drawRightString(right_margin, y, ar("المشتري"))
    y -= 6 * mm
    c.setFont("Arabic", 10)
    if finance_row.buyer_name:
        c.drawRightString(right_margin, y, ar(finance_row.buyer_name))
        y -= 5.5 * mm
    if finance_row.buyer_phone:
        c.drawRightString(right_margin, y, ar(finance_row.buyer_phone))
        y -= 5.5 * mm
    if not (finance_row.buyer_name or finance_row.buyer_phone):
        c.drawRightString(right_margin, y, ar("غير مسجَّل"))
        y -= 5.5 * mm

    y -= 12 * mm
    col_item = right_margin
    col_amount = left_margin + 30 * mm
    c.setFont("Arabic", 10)
    c.drawRightString(col_item, y, ar("البيان"))
    c.drawRightString(col_amount, y, ar("المبلغ"))
    y -= 3 * mm
    c.line(left_margin, y, right_margin, y)
    y -= 8 * mm

    item_label = f"بيع رأس رقم {animal.animal_no}" if animal else (finance_row.item or "بيع")
    c.setFont("Arabic", 10)
    c.drawRightString(col_item, y, ar(item_label))
    c.drawRightString(col_amount, y, ar(f"{finance_row.amount:,.2f}"))
    y -= 6 * mm
    c.line(left_margin, y, right_margin, y)
    y -= 10 * mm

    c.setFont("Arabic", 13)
    c.drawRightString(right_margin, y, ar(f"الإجمالي: {finance_row.amount:,.2f}"))

    if finance_row.description:
        y -= 12 * mm
        c.setFont("Arabic", 9)
        c.drawRightString(right_margin, y, ar(f"ملاحظات: {finance_row.description}"))

    # رمز QR بأسلوب "فاتورة" المرحلة الأولى (بند إضافي 184) — بس لو
    # صاحب الحلال سجّل رقماً ضريبياً فعلياً بالإعدادات؛ فاضي = بدون رمز
    # إطلاقاً (نفس فلسفة كل ميزة اختيارية بالمشروع: صفر إعداد = صفر أثر).
    from app.core.zatca_service import invoice_qr_image
    from datetime import datetime as _dt
    qr_buf = invoice_qr_image(
        farm_settings=farm_settings, invoice_total=finance_row.amount,
        timestamp=_dt.combine(finance_row.date, _dt.min.time()),
    )
    if qr_buf:
        from reportlab.lib.utils import ImageReader
        qr_size = 28 * mm
        c.drawImage(ImageReader(qr_buf), left_margin, 15 * mm, width=qr_size, height=qr_size)
        c.setFont("Arabic", 7)
        c.drawString(left_margin, 12 * mm, ar("QR مبسّط (المرحلة الأولى) — ليس فاتورة ضريبية معتمدة رسمياً"))

    c.save()
    buf.seek(0)
    return buf
