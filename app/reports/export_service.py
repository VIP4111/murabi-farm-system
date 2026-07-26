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
    ws.append(columns)
    for row in rows:
        ws.append(row)
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
