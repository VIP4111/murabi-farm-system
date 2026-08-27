"""بند إضافي 270 — تكملة إثراء قاعدة معرفة المساعد الذكي: المعدات
والصيانة (ربطها المالي، بند 263) والفريق (تقرير الأداء وتقييم جودة
المهام، ما كان لهم بند معرفة إطلاقاً)."""
from app.assistant.knowledge_base import ENTRIES, search
from app.assistant.text_utils import normalize


def test_asset_maintenance_question_matches_entry():
    results = search(normalize("كيف اسجل صيانة اصل وتكلفتها"))
    assert results
    assert results[0].code == "howto_asset_maintenance"


def test_utility_readings_question_matches_entry():
    results = search(normalize("كيف اسجل فاتورة كهرباء"))
    assert results
    assert results[0].code == "howto_utility_readings"


def test_team_performance_question_matches_entry():
    results = search(normalize("كيف اشوف اداء العمال"))
    assert results
    assert results[0].code == "howto_team_performance_report"


def test_task_quality_rate_question_matches_entry():
    results = search(normalize("ابي اسوي تقييم جودة مهمة انجزها عامل"))
    assert results
    assert results[0].code == "howto_task_quality_rate"


def test_all_new_entries_present():
    codes = {e.code for e in ENTRIES}
    expected = {
        "howto_asset_maintenance", "howto_utility_readings",
        "howto_team_performance_report", "howto_task_quality_rate",
    }
    assert expected.issubset(codes)


def test_asset_maintenance_mentions_finance_link():
    entry = next(e for e in ENTRIES if e.code == "howto_asset_maintenance")
    assert "مصروف" in entry.body


def test_utility_readings_mentions_finance_link():
    entry = next(e for e in ENTRIES if e.code == "howto_utility_readings")
    assert "مصروف" in entry.body
