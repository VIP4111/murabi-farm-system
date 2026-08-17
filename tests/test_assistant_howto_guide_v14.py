"""بند إضافي 208 — بند معرفة جديد يشرح ميزة الجرد/الهالك المضافة."""
from app.assistant.knowledge_base import ENTRIES, search
from app.assistant.text_utils import normalize


def test_inventory_count_question_matches_entry():
    results = search(normalize("كيف اسوي جرد؟"))
    assert results
    assert results[0].code == "howto_inventory_count"


def test_waste_calculation_question_matches_entry():
    results = search(normalize("حساب الهالك"))
    assert results
    assert results[0].code == "howto_inventory_count"


def test_inventory_count_entry_mentions_indirect_expense_distribution():
    entry = next(e for e in ENTRIES if e.code == "howto_inventory_count")
    assert "مصروف مالي غير مباشر" in entry.body
    assert "الرؤوس النشطة" in entry.body
