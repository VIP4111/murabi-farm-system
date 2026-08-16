"""بند إضافي 203 — بعد إضافة زر "شراء" موحّد بالعلف/المعدات (يزيد
المخزون ويسجّل العملية المالية معاً)، أضفنا بند معرفة يشرحه، مع
كلمات مفتاحية كافية عشان يتغلّب على تصادم الاسم مع buying_checklist
(فحص الحيوان قبل الشراء) اللي يشترك بكلمة "شراء" العامة."""
from app.assistant.knowledge_base import ENTRIES, search
from app.assistant.text_utils import normalize


def test_feed_purchase_question_matches_stock_purchase_entry():
    results = search(normalize("شراء علف"))
    assert results
    assert results[0].code == "howto_stock_purchase"


def test_equipment_purchase_question_matches_stock_purchase_entry():
    results = search(normalize("شراء معدات"))
    assert results
    assert results[0].code == "howto_stock_purchase"


def test_stock_purchase_entry_mentions_combined_stock_and_finance_effect():
    entry = next(e for e in ENTRIES if e.code == "howto_stock_purchase")
    assert "يزيد المخزون" in entry.body
    assert "العملية المالية" in entry.body
