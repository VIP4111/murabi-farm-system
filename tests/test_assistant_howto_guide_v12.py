"""بند إضافي 204 — بعد إضافة "رحلة السوق" (طلّعها للسوق/رجعت بدون بيع)
لصفحة دورة الإنتاج، أضفنا بند معرفة يشرحها ويشرح "استرجاع البيع"
الموجود أصلاً (بند 75) لحالة تسجيل بيع فعلي محتاج تراجع."""
from app.assistant.knowledge_base import ENTRIES, search
from app.assistant.text_utils import normalize


def test_market_trip_question_matches_entry():
    results = search(normalize("طلعتها للسوق وما بعت"))
    assert results
    assert results[0].code == "howto_market_trip"


def test_cancel_sale_question_matches_entry():
    results = search(normalize("الغاء البيع"))
    assert results
    assert results[0].code == "howto_market_trip"


def test_market_trip_entry_mentions_both_paths():
    entry = next(e for e in ENTRIES if e.code == "howto_market_trip")
    assert "رجع للمزرعة بدون بيع" in entry.body
    assert "استرجاع البيع" in entry.body
