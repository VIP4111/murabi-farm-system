"""بند إضافي 269 — تكملة إثراء قاعدة معرفة المساعد الذكي (بند 268):
إضافات المالية الجديدة هالجلسة (بند 251-257) ما كانت موجودة بقاعدة
المعرفة. كمان صحّحنا بند قديم (howto_monthly_cost_report) كان يصف
تقرير التكلفة الشهرية غلط (وصفه كملخص دخل/مصروف عام، بينما هو فعلياً
تقرير تكلفة الرأس المقسومة على عدد رؤوس دقيق تاريخياً)."""
from app.assistant.knowledge_base import ENTRIES, search
from app.assistant.text_utils import normalize


def test_net_profit_percent_question_matches_entry():
    results = search(normalize("كيف اعرف نسبة ربحي الاجمالية"))
    assert results
    assert results[0].code == "howto_net_profit_percent"


def test_loss_diagnosis_question_matches_entry():
    results = search(normalize("ليش انا بخساره هل يبين لي السبب"))
    assert results
    assert results[0].code == "howto_loss_diagnosis"


def test_seasonal_price_chart_question_matches_entry():
    results = search(normalize("هل فيه شارت افضل وقت للبيع"))
    assert results
    assert results[0].code == "howto_seasonal_price_chart"


def test_break_even_market_value_question_matches_entry():
    results = search(normalize("من وين تجي القيمة التقديرية نقطة التعادل"))
    assert results
    assert results[0].code == "howto_break_even_market_value"


def test_monthly_cost_report_entry_corrected():
    entry = next(e for e in ENTRIES if e.code == "howto_monthly_cost_report")
    assert "تكلفة الرأس الشهرية" in entry.body
    assert "عدد رؤوسك" in entry.body


def test_monthly_cost_report_question_still_matches_after_fix():
    results = search(normalize("كم يكلفني كل رأس بالشهر"))
    assert results
    assert results[0].code == "howto_monthly_cost_report"


def test_all_finance_analytics_entries_present():
    codes = {e.code for e in ENTRIES}
    expected = {
        "howto_net_profit_percent", "howto_loss_diagnosis",
        "howto_seasonal_price_chart", "howto_break_even_market_value",
    }
    assert expected.issubset(codes)
