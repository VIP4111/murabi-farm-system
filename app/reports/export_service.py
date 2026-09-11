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


def build_lot_profile_pdf(lot, rows, stats, farm_settings) -> io.BytesIO:
    """بروفايل تجاري احترافي لدفعة بيع (بند إضافي 191.3) — مستند
    عرض للمشتري المحتمل: هوية المزرعة، إحصائيات الدفعة الاستثمارية،
    وجدول تفصيلي بكل رأس (رقم، عمر، وزن، سلالة، حالة صحية عامة).
    **صفر بيانات مالية داخلية حساسة** — لا تكلفة فعلية ولا هامش ربح،
    بس الوزن والعمر والصحة (ما يهم المشتري فعلياً)."""
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    right_margin = width - 15 * mm
    left_margin = 15 * mm
    y = height - 20 * mm

    c.setFont("Arabic", 18)
    c.drawRightString(right_margin, y, ar(lot.name))
    y -= 8 * mm
    c.setFont("Arabic", 10)
    farm_name = farm_settings.farm_name or "مراح بو علي"
    c.drawRightString(right_margin, y, ar(f"{farm_name} — {farm_settings.farm_phone or ''}"))
    y -= 10 * mm

    c.setFont("Arabic", 12)
    summary = (
        f"عدد الرؤوس: {stats['count']}   |   إجمالي الوزن: {stats['total_weight']} كجم"
        f"   |   متوسط الوزن: {stats['avg_weight']} كجم"
    )
    c.drawRightString(right_margin, y, ar(summary))
    y -= 10 * mm
    c.line(left_margin, y, right_margin, y)
    y -= 8 * mm

    columns = ["الرقم", "السلالة", "الجنس", "العمر", "الوزن (كجم)", "الحالة الصحية"]
    n_cols = len(columns)
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
    for r in rows:
        if y < 25 * mm:
            c.showPage()
            y = height - 20 * mm
            y = draw_header(y)
            c.setFont("Arabic", 8.5)
        animal = r["animal"]
        health_state = "سليم" if r.get("open_diseases", 0) == 0 else f"{r['open_diseases']} حالة مفتوحة"
        values = [
            animal.animal_no, animal.breed or "-", animal.gender or "-",
            r["age_label"] or "-", r["weight"] or "-", health_state,
        ]
        for i, val in enumerate(values):
            x = right_margin - i * col_width
            c.drawRightString(x, y, ar(val))
        y -= 6 * mm

    y -= 6 * mm
    c.setFont("Arabic", 9)
    c.drawRightString(right_margin, y, ar("بيانات استرشادية معدَّة آلياً — تواصل معنا مباشرة للتفاصيل والمعاينة."))

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


_ARABIC_MONTHS = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو",
    7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}


def resolve_payslip_employer(user, farm_settings):
    """يحدّد "صاحب العمل" اللي يُطبع بمسير راتب `user` — بند إصلاح
    (طلبك الصريح: "هل صاحب الحلال راح يكون مكفول جميع العمال او في
    امكانيه تسجيل كل عامل بيناته لحالها"). قبل هذا البند كان "صاحب
    العمل" يُطبع دائماً من بيانات صاحب الحلال الوحيدة (`farm_settings`)
    لكل عمال المزرعة بلا استثناء، حتى لو عامل معيّن مكفول فعلياً على
    شخص/منشأة ثانية — يخلي المستند مغلوطاً لو استُخدم رسمياً. صار يفضّل
    بيانات كفيل العامل نفسه (`User.sponsor_*`) لو معبّاة، ويرجع لصاحب
    الحلال تلقائياً لو فاضية (نفس السلوك القديم بالضبط لأي عامل ما له
    كفيل مستقل مسجَّل). دالة مستقلة (بدل منطق مباشر داخل بناء الـPDF)
    عشان تُختبر بسهولة بدون الحاجة نفكّك محتوى PDF."""
    name = user.sponsor_name or farm_settings.farm_name or "مراح بو علي"
    national_id = user.sponsor_national_id or farm_settings.owner_national_id
    phone = user.sponsor_phone or farm_settings.farm_phone
    return name, national_id, phone


def build_payroll_receipt_pdf(payroll, farm_settings) -> io.BytesIO:
    """مسير راتب شهر واحد (بند إضافي 242) — نظام الرواتب العام (بخلاف
    وصل "موظف الشهر" الأبسط، بند 240): يفصّل الراتب الأساسي + المكافأة
    - كل سطر خصم بسببه - = الصافي المستحق، بطلبك الصريح."""
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    right_margin = width - 20 * mm
    left_margin = 20 * mm
    y = height - 25 * mm

    c.setFont("Arabic", 18)
    c.drawRightString(right_margin, y, ar("مسير راتب الشهر"))
    y -= 10 * mm
    c.setFont("Arabic", 10)
    c.drawRightString(right_margin, y, ar(f"التاريخ: {payroll.confirmed_at.date() if payroll.confirmed_at else ''}"))
    y -= 12 * mm

    c.line(left_margin, y, right_margin, y)
    y -= 10 * mm

    employer_name, employer_national_id, employer_phone = resolve_payslip_employer(payroll.user, farm_settings)

    c.setFont("Arabic", 12)
    c.drawRightString(right_margin, y, ar("صاحب العمل"))
    y -= 6 * mm
    c.setFont("Arabic", 10)
    c.drawRightString(right_margin, y, ar(employer_name))
    y -= 5.5 * mm
    if employer_national_id:
        c.drawRightString(right_margin, y, ar(f"رقم الهوية: {employer_national_id}"))
        y -= 5.5 * mm
    if employer_phone:
        c.drawRightString(right_margin, y, ar(f"رقم الجوال: {employer_phone}"))
        y -= 5.5 * mm

    y -= 8 * mm
    c.setFont("Arabic", 12)
    c.drawRightString(right_margin, y, ar("بيانات العامل"))
    y -= 6 * mm
    c.setFont("Arabic", 10)
    c.drawRightString(right_margin, y, ar(f"اسم العامل: {payroll.user.name}"))
    y -= 5.5 * mm
    if payroll.user.nationality:
        c.drawRightString(right_margin, y, ar(f"الجنسية: {payroll.user.nationality}"))
        y -= 5.5 * mm
    if payroll.user.passport_number:
        c.drawRightString(right_margin, y, ar(f"رقم الجواز: {payroll.user.passport_number}"))
        y -= 5.5 * mm
    if payroll.user.border_number:
        c.drawRightString(right_margin, y, ar(f"رقم الحدود: {payroll.user.border_number}"))
        y -= 5.5 * mm
    c.drawRightString(right_margin, y, ar(f"فترة الراتب: {_ARABIC_MONTHS.get(payroll.month, payroll.month)} {payroll.year}"))
    y -= 5.5 * mm
    if payroll.user.payment_method == "تحويل بنكي":
        # حوالة (بند إضافي 244) — بطلبك: "من المحوّل ومن مستلم الحوالة"
        # صريحين. المحوّل = صاحب العمل المذكور فوق (كفيل العامل لو
        # مسجَّل، وإلا صاحب الحلال — نفس `employer_name` أعلاه)، والمستلم
        # حقل مستقل قابل للاستبدال كل شهر (Payroll.recipient_name).
        recipient = payroll.recipient_name or payroll.user.name
        c.drawRightString(right_margin, y, ar(f"طريقة الدفع: تحويل بنكي — من {employer_name} إلى {recipient}"))
        y -= 5.5 * mm
    elif payroll.user.payment_method:
        c.drawRightString(right_margin, y, ar(f"طريقة الدفع: {payroll.user.payment_method}"))
        y -= 5.5 * mm

    y -= 10 * mm
    col_item = right_margin
    col_amount = left_margin + 30 * mm
    c.setFont("Arabic", 10)
    c.drawRightString(col_item, y, ar("البيان"))
    c.drawRightString(col_amount, y, ar("المبلغ"))
    y -= 3 * mm
    c.line(left_margin, y, right_margin, y)
    y -= 7 * mm

    c.setFont("Arabic", 10)
    c.drawRightString(col_item, y, ar("الراتب الأساسي"))
    c.drawRightString(col_amount, y, ar(f"{payroll.base_salary:,.2f}"))
    y -= 6 * mm
    if payroll.bonus_amount:
        c.drawRightString(col_item, y, ar("المكافأة"))
        c.drawRightString(col_amount, y, ar(f"{payroll.bonus_amount:,.2f}"))
        y -= 6 * mm
    for d in payroll.deductions:
        label = f"خصم — {d.reason}" if d.reason else "خصم"
        c.drawRightString(col_item, y, ar(label))
        c.drawRightString(col_amount, y, ar(f"-{d.amount:,.2f}"))
        y -= 6 * mm

    y -= 2 * mm
    c.line(left_margin, y, right_margin, y)
    y -= 10 * mm

    c.setFont("Arabic", 13)
    c.drawRightString(right_margin, y, ar(f"الصافي المستحق: {payroll.net_amount:,.2f}"))
    y -= 10 * mm
    c.setFont("Arabic", 9)
    c.drawRightString(right_margin, y, ar(f"معتمَد من: {payroll.confirmed_by.name if payroll.confirmed_by else '-'}"))

    y -= 30 * mm
    c.setFont("Arabic", 10)
    c.drawRightString(right_margin, y, ar("توقيع العامل: ......................"))
    y -= 12 * mm
    c.drawRightString(right_margin, y, ar("توقيع صاحب الحلال: ......................"))

    c.save()
    buf.seek(0)
    return buf


def _wrap_ar_lines(c, text: str, font: str, size: float, max_width: float) -> list[str]:
    """يلف نص عربي طويل على عدة أسطر تناسب عرض معيّن (بند إصلاح —
    build_pdf/build_payroll_receipt_pdf ما يحتاجوا هذا لأن كل قيمة
    فيهم سطر واحد قصير أصلاً؛ بنود العقد فقرات طويلة تحتاج التفاف
    حقيقي حسب عرض الصفحة). يلف بالكلمة الكاملة (مو بالحرف) عشان ما
    تنقطع كلمة عربية بمنتصفها."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if c.stringWidth(ar(candidate), font, size) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def build_employment_contract_pdf(user, template, farm_settings) -> io.BytesIO:
    """اتفاقية عمل رسمية (بند إصلاح — طلبك: "طباعة اتفاقية عمل"، ثم
    "كل مسمى وظيفي له بنود تختلف... ابيك تبنيها وتعطيني صلاحيه في
    تعديل على البنود فيما بعد") — الطرف الأول يُحدَّد بنفس منطق
    `resolve_payslip_employer` (كفيل العامل نفسه لو مسجَّل، وإلا صاحب
    الحلال تلقائياً)، والبنود تُقرأ حرفياً من `template.clauses_text`
    القابل للتعديل الكامل من شاشة الإعدادات. **ملاحظة قانونية**: هذي
    مسودة عامة تحتاج مراجعة محامٍ/مستشار موارد بشرية قبل الاستخدام
    الفعلي — نفس التحذير المعروض بشاشة الطباعة."""
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    right_margin = width - 20 * mm
    left_margin = 20 * mm
    usable_width = right_margin - left_margin
    y = height - 25 * mm

    employer_name, employer_national_id, employer_phone = resolve_payslip_employer(user, farm_settings)

    c.setFont("Arabic", 18)
    c.drawRightString(right_margin, y, ar("اتفاقية عمل"))
    y -= 10 * mm
    c.setFont("Arabic", 10)
    c.drawRightString(right_margin, y, ar(f"المسمى الوظيفي: {template.job_title}"))
    y -= 12 * mm

    c.line(left_margin, y, right_margin, y)
    y -= 10 * mm

    c.setFont("Arabic", 12)
    c.drawRightString(right_margin, y, ar("الطرف الأول (صاحب العمل)"))
    y -= 6 * mm
    c.setFont("Arabic", 10)
    c.drawRightString(right_margin, y, ar(employer_name))
    y -= 5.5 * mm
    if employer_national_id:
        c.drawRightString(right_margin, y, ar(f"رقم الهوية: {employer_national_id}"))
        y -= 5.5 * mm
    if employer_phone:
        c.drawRightString(right_margin, y, ar(f"رقم الجوال: {employer_phone}"))
        y -= 5.5 * mm

    y -= 6 * mm
    c.setFont("Arabic", 12)
    c.drawRightString(right_margin, y, ar("الطرف الثاني (العامل)"))
    y -= 6 * mm
    c.setFont("Arabic", 10)
    c.drawRightString(right_margin, y, ar(f"الاسم: {user.name}"))
    y -= 5.5 * mm
    if user.nationality:
        c.drawRightString(right_margin, y, ar(f"الجنسية: {user.nationality}"))
        y -= 5.5 * mm
    if user.passport_number:
        c.drawRightString(right_margin, y, ar(f"رقم الجواز: {user.passport_number}"))
        y -= 5.5 * mm
    if user.border_number:
        c.drawRightString(right_margin, y, ar(f"رقم الحدود: {user.border_number}"))
        y -= 5.5 * mm

    y -= 10 * mm
    c.line(left_margin, y, right_margin, y)
    y -= 10 * mm

    c.setFont("Arabic", 12)
    c.drawRightString(right_margin, y, ar("بنود الاتفاقية"))
    y -= 8 * mm

    clauses = [ln.strip() for ln in template.clauses_text.splitlines() if ln.strip()]
    c.setFont("Arabic", 9.5)
    for i, clause in enumerate(clauses, start=1):
        clause_text = f"{i}. {clause}"
        lines = _wrap_ar_lines(c, clause_text, "Arabic", 9.5, usable_width)
        for line in lines:
            if y < 30 * mm:
                c.showPage()
                c.setFont("Arabic", 9.5)
                y = height - 20 * mm
            c.drawRightString(right_margin, y, ar(line))
            y -= 5.5 * mm
        y -= 2 * mm

    if y < 55 * mm:
        c.showPage()
        y = height - 25 * mm

    y -= 20 * mm
    c.setFont("Arabic", 10)
    col_left_sig = left_margin + 40 * mm
    col_right_sig = right_margin
    c.drawRightString(col_right_sig, y, ar("توقيع الطرف الثاني (العامل): ......................"))
    c.drawRightString(col_left_sig, y, ar("توقيع الطرف الأول: ......................"))

    c.setFont("Arabic", 7.5)
    c.drawCentredString(width / 2, 12 * mm, ar(
        "مستند مُولَّد من نظام مراح بو علي — مسودة عامة تحتاج مراجعة محامٍ/مستشار موارد بشرية قبل الاستخدام الرسمي."
    ))

    c.save()
    buf.seek(0)
    return buf


def build_settlement_pdf(user, context, farm_settings) -> io.BytesIO:
    """إقرار وتعهد بالمخالصة النهائية (بند إصلاح — طلبك: "مخالصه في
    حال اختيار السفر بشكل نهائي"، ثم وضّحت: "ابيه يكون تعهد بان
    العامل يتعهد بستلام كافة رواتبه وحقوقه وتنظيف بياناته من النظام").
    نص الإقرار ثابت (مو حسب مسمى وظيفي — طبيعة الإقرار المالي واحدة
    لكل العمال)، والمبالغ تُدخَل يدوياً وقت الطباعة (`context`) بدل
    حساب تلقائي لمكافأة نهاية الخدمة — بطلبك الصريح."""
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    right_margin = width - 20 * mm
    left_margin = 20 * mm
    usable_width = right_margin - left_margin
    y = height - 25 * mm

    employer_name, employer_national_id, employer_phone = resolve_payslip_employer(user, farm_settings)

    c.setFont("Arabic", 17)
    c.drawRightString(right_margin, y, ar("إقرار وتعهد بالمخالصة النهائية"))
    y -= 10 * mm
    c.setFont("Arabic", 10)
    c.drawRightString(right_margin, y, ar(f"اسم العامل: {user.name}"))
    y -= 5.5 * mm
    if context.get("last_work_day"):
        c.drawRightString(right_margin, y, ar(f"آخر يوم عمل فعلي: {context['last_work_day']}"))
        y -= 5.5 * mm
    if context.get("reason"):
        c.drawRightString(right_margin, y, ar(f"سبب إنهاء الخدمة: {context['reason']}"))
        y -= 5.5 * mm
    y -= 6 * mm
    c.line(left_margin, y, right_margin, y)
    y -= 10 * mm

    total = (
        context.get("final_salary", 0) + context.get("end_of_service", 0)
        + context.get("leave_balance", 0) - context.get("deductions", 0)
    )
    rows = [
        ("راتب الشهر الأخير", context.get("final_salary", 0)),
        ("مكافأة نهاية الخدمة", context.get("end_of_service", 0)),
        ("بدل إجازة سنوية غير مستخدمة", context.get("leave_balance", 0)),
        ("خصومات", -context.get("deductions", 0)),
    ]
    col_item = right_margin
    col_amount = left_margin + 30 * mm
    c.setFont("Arabic", 10)
    c.drawRightString(col_item, y, ar("البند"))
    c.drawRightString(col_amount, y, ar("المبلغ (ريال)"))
    y -= 3 * mm
    c.line(left_margin, y, right_margin, y)
    y -= 7 * mm
    for label, amount in rows:
        c.drawRightString(col_item, y, ar(label))
        c.drawRightString(col_amount, y, ar(f"{amount:,.2f}"))
        y -= 6 * mm
    y -= 2 * mm
    c.line(left_margin, y, right_margin, y)
    y -= 8 * mm
    c.setFont("Arabic", 12)
    c.drawRightString(right_margin, y, ar(f"إجمالي المستلَم: {total:,.2f} ريال"))
    y -= 14 * mm

    pledge = (
        f"أقرّ أنا الموقّع أدناه ({user.name}) بأنني استلمت من الكفيل/صاحب العمل ({employer_name}) "
        f"كامل مستحقاتي المالية المذكورة أعلاه (الراتب ومكافأة نهاية الخدمة وأي بدلات مستحقة) عن كامل "
        f"مدة عملي، وأنه لا يوجد لي أي مطالبة مالية أو حقوقية أخرى تجاه صاحب العمل بأي صفة كانت، سواء "
        f"بشكل حالي أو مستقبلي، وذلك اعتباراً من تاريخ توقيعي على هذا الإقرار."
    )
    pledge_2 = (
        "كما أوافق وأتعهد بموافقتي الصريحة على قيام إدارة نظام \"مراح بو علي\" بحذف/تنظيف كافة بياناتي "
        "الشخصية المسجَّلة بالنظام (بيانات الهوية، السجلات المالية المرتبطة بي، أي مستند مرفوع باسمي) "
        "بعد إتمام هذا الإقرار ومغادرتي النهائية، ولا يحق لي أي اعتراض على ذلك لاحقاً."
    )
    c.setFont("Arabic", 9.5)
    for para in (pledge, pledge_2):
        for line in _wrap_ar_lines(c, para, "Arabic", 9.5, usable_width):
            if y < 40 * mm:
                c.showPage()
                c.setFont("Arabic", 9.5)
                y = height - 25 * mm
            c.drawRightString(right_margin, y, ar(line))
            y -= 5.5 * mm
        y -= 4 * mm

    y -= 20 * mm
    if y < 30 * mm:
        c.showPage()
        y = height - 40 * mm
    c.setFont("Arabic", 10)
    col_left_sig = left_margin + 40 * mm
    c.drawRightString(right_margin, y, ar("توقيع العامل: ......................"))
    c.drawRightString(col_left_sig, y, ar(f"توقيع واعتماد صاحب العمل ({employer_name}): ......................"))

    c.setFont("Arabic", 7.5)
    c.drawCentredString(width / 2, 12 * mm, ar(
        "مستند مُولَّد من نظام مراح بو علي — مسودة عامة تحتاج مراجعة محامٍ/مستشار موارد بشرية قبل الاستخدام الرسمي."
    ))

    c.save()
    buf.seek(0)
    return buf
