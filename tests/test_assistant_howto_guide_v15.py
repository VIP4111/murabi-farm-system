"""بند إضافي 268 — قسم "الرواتب" بالكامل ما كان موجود بقاعدة معرفة
المساعد الذكي إطلاقاً (بناه النظام هالجلسة، بند 241-250)، رغم إن
النظام بنى قاعدة معرفة واسعة (93 بند) لأغلب الأقسام الثانية. أضفنا
15 بند جديد يغطي كل شاشات ومفاهيم الرواتب."""
from app.assistant.knowledge_base import ENTRIES, search
from app.assistant.text_utils import normalize


def test_salary_setup_question_matches_entry():
    results = search(normalize("كيف اسجّل راتب اساسي لعامل جديد"))
    assert results
    assert results[0].code == "howto_salary_setup"


def test_payroll_prepare_question_matches_entry():
    results = search(normalize("كيف اجهّز راتب هذا الشهر"))
    assert results
    assert results[0].code == "howto_payroll_prepare"


def test_payroll_confirm_question_matches_entry():
    results = search(normalize("شنو يصير عند تأكيد راتب نهائي"))
    assert results
    assert results[0].code == "howto_payroll_confirm"


def test_deductions_question_matches_entry():
    results = search(normalize("ابي اسوي اضافة خصم على راتب عامل"))
    assert results
    assert results[0].code == "howto_payroll_deductions"


def test_receipt_question_matches_entry():
    results = search(normalize("كيف ارفع وصل موقع للراتب"))
    assert results
    assert results[0].code == "howto_payroll_receipt"


def test_payroll_reports_question_matches_entry():
    results = search(normalize("ابي اشوف تاريخ رواتب عامل معيّن"))
    assert results
    assert results[0].code == "howto_payroll_reports"


def test_worker_travel_question_matches_entry():
    results = search(normalize("عندي عامل مسافر كيف اسجله"))
    assert results
    assert results[0].code == "howto_worker_travel"


def test_arrival_date_question_matches_entry():
    results = search(normalize("ما فايدة تاريخ الوصول للسعودية بالرواتب"))
    assert results
    assert results[0].code == "howto_saudi_arrival_date"


def test_top_performer_question_matches_entry():
    results = search(normalize("شنو معنى شارة اعلى نقطة اداء بالراتب"))
    assert results
    assert results[0].code == "howto_top_performer_bonus"


def test_month_end_reminder_question_matches_entry():
    results = search(normalize("نسيت راتب عامل هل فيه تذكير رواتب"))
    assert results
    assert results[0].code == "howto_payroll_month_end_reminder"


def test_travel_confirmed_warning_question_matches_entry():
    results = search(normalize("طلع لي تحذير راتب مؤكد لما عدّلت السفر"))
    assert results
    assert results[0].code == "howto_travel_edit_confirmed_month_warning"


def test_payment_method_question_matches_entry():
    results = search(normalize("ما الفرق بين طريقة الدفع الراتب نقدا وتحويل"))
    assert results
    assert results[0].code == "howto_payment_method_payroll"


def test_manage_salary_permission_question_matches_entry():
    results = search(normalize("ابي اعطي المحاسب صلاحية ادارة الرواتب بدون فريق كامل"))
    assert results
    assert results[0].code == "howto_team_manage_salary_permission"


def test_all_payroll_entries_present():
    codes = {e.code for e in ENTRIES}
    expected = {
        "howto_salary_setup", "howto_payroll_prepare", "howto_payroll_confirm",
        "howto_payroll_deductions", "howto_payroll_receipt", "howto_payroll_reports",
        "howto_worker_travel", "howto_saudi_arrival_date", "howto_top_performer_bonus",
        "howto_payroll_month_end_reminder", "howto_travel_edit_confirmed_month_warning",
        "howto_payment_method_payroll", "howto_team_manage_salary_permission",
    }
    assert expected.issubset(codes)


def test_finance_entry_no_longer_points_to_generic_form_for_payroll():
    entry = next(e for e in ENTRIES if e.code == "howto_finance_entry")
    assert "رواتب الشهر" in entry.body
