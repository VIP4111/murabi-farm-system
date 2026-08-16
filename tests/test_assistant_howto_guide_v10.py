"""بند إضافي 202 — بعد تحويل وحدة العلف من نص حر لقائمة ثابتة وإضافة
حقل "وزن الوحدة بالكيلو" (للربطة/الكيس)، أضفنا بند معرفة جديد يشرح
للمستخدم ليش الوحدة صارت قائمة ثابتة ووش فايدة حقل وزن الوحدة."""
from app.assistant.knowledge_base import ENTRIES, search
from app.assistant.text_utils import normalize


def test_bale_weight_question_matches_feed_item_entry():
    results = search(normalize("كم كيلو بالربطة"))
    assert results
    assert results[0].code == "howto_feed_item_new"


def test_add_feed_item_question_matches_feed_item_entry():
    results = search(normalize("اضافة مكون علف جديد"))
    assert results
    assert results[0].code == "howto_feed_item_new"


def test_feed_item_entry_mentions_fixed_unit_list_and_optional_weight_field():
    entry = next(e for e in ENTRIES if e.code == "howto_feed_item_new")
    assert "قائمة ثابتة" in entry.body
    assert "ربطة" in entry.body
    assert "اختياري" in entry.body
