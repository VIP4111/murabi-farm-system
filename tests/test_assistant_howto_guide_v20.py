"""بند إضافي 280 — طلبك الصريح "اكيد لازم تضيف" لما سألت هل المساعد
تحدّث بسلوك "المهام المقترحة" الجديد (نافذة اليوم/بكرة + حذف تلقائي
بعد يومين تأخر). بند معرفة جديد يشرح هذا السلوك."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


def test_suggested_tasks_window_question_matches_entry():
    results = search(normalize("ليش المهام المقترحة اليوم فقط تطلع لي"))
    assert results
    assert results[0].code == "howto_suggested_tasks_window"


def test_suggested_task_auto_delete_question_matches_entry():
    results = search(normalize("وين راحت مهام مقترحة قديمة، هل تحذف تلقائي مهمة مقترحة؟"))
    assert results
    assert results[0].code == "howto_suggested_tasks_window"
