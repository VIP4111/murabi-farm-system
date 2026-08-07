"""بند إضافي 141 — توسعة ثامنة لمرشد التطبيق. سألت المساعد الذكي
"كيف أسمّن مجموعة حيوانات؟" وما فهمها — بند جديد يغطيها، + تحديث بند
"howto_bulk_operations" الموجود أصلاً عشان يذكر إجراء "تحديد الغرض
جماعياً" الجديد بقائمة الإجراءات (نفس ملاحظتك: ما يكفي نضيف بند جديد
بدون ما نحدّث البند اللي يسرد كل الإجراءات)."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


def test_fattening_group_question_matches_new_entry():
    results = search(normalize("كيف أسمّن مجموعة حيوانات؟"))
    assert results
    assert results[0].code == "howto_bulk_fattening_group"


def test_bulk_operations_entry_mentions_new_purpose_action():
    from app.assistant.knowledge_base import ENTRIES
    entry = next(e for e in ENTRIES if e.code == "howto_bulk_operations")
    assert "تحديد الغرض جماعياً" in entry.body
