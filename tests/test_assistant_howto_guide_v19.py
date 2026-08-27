"""بند إضافي 272 — تكملة التدقيق العميق: لقينا شاشتين ماليتين حقيقيتين
بدون أي بند معرفة إطلاقاً — "نقطة التعادل" (شرح عام لسعر التعادل/
الهامش، بخلاف بند مصدر القيمة التقديرية اللي أضفناه قبل) و"مؤشر
الاستبعاد المالي" (culling index، بند 190 قديم بس ما وصل لقاعدة
المعرفة من الأساس)."""
from app.assistant.knowledge_base import ENTRIES, search
from app.assistant.text_utils import normalize


def test_break_even_screen_question_matches_entry():
    results = search(normalize("شنو يعني سعر التعادل"))
    assert results
    assert results[0].code == "howto_break_even_screen"


def test_culling_index_question_matches_entry():
    results = search(normalize("مؤشر الاستبعاد المالي وكم تكلفة الاحتفاظ برأس غير دافعة"))
    assert results
    assert results[0].code == "howto_culling_index"


def test_culling_index_entry_discloses_no_auto_action():
    entry = next(e for e in ENTRIES if e.code == "howto_culling_index")
    assert "ما يبيع ولا يعزل أي رأس تلقائياً" in entry.body


def test_all_new_entries_present():
    codes = {e.code for e in ENTRIES}
    expected = {"howto_break_even_screen", "howto_culling_index"}
    assert expected.issubset(codes)
