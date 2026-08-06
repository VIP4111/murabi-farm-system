"""بند إضافي 139 — توسعة سابعة لمرشد التطبيق. سألك المستخدم صراحة هل
المساعد الذكي ملم بكامل أقسام المشروع، وطلب إكمال كل البنود بدون
اللجوء لـ Claude API. 4 مواضيع جديدة تغطي بند 131/133/134/135 (كانت
غائبة تماماً)، + تحديث 4 بنود قديمة كانت تصف شاشات قديمة انبنت من
جديد ببند 132/136/137 (الإجراء الجماعي، دمج التنبيهات بصفحة اليوم،
العرض الإجباري بالتشخيص)."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


QUESTIONS = {
    "howto_feeding_schedule": "كيف أجدول مواعيد وجبات العلف؟",
    "howto_feed_blend_auto": "كيف يحسب النظام خلطة الحظيرة تلقائياً؟",
    "howto_barn_physiology_sort": "شنو فرز حظائر الحوامل والرضاعة؟",
    "howto_incomplete_data_alerts": "ليش يطلعلي تنبيه بيانات ناقصة؟",
}


def test_all_v7_howto_questions_match_expected_entry():
    for expected_code, question in QUESTIONS.items():
        results = search(normalize(question))
        assert results, f"ما رجع أي نتيجة للسؤال: {question}"
        assert results[0].code == expected_code, (
            f"السؤال '{question}' رجع '{results[0].code}' بدل '{expected_code}'"
        )


def test_v7_entries_have_nonempty_body_and_keywords():
    from app.assistant.knowledge_base import ENTRIES
    by_code = {e.code: e for e in ENTRIES}
    for code in QUESTIONS:
        entry = by_code[code]
        assert entry.body.strip()
        assert len(entry.keywords) >= 2


def test_updated_entries_reflect_current_screens_not_stale_ones():
    """بند 132/136 غيّروا شاشات فعلية — تأكيد إن النص القديم اتشال."""
    from app.assistant.knowledge_base import ENTRIES
    by_code = {e.code: e for e in ENTRIES}

    bulk = by_code["howto_bulk_operations"]
    assert "الإجراء الجماعي" in bulk.body
    assert "من شاشة 'الحيوانات' اضغط 'تحديد جماعي'" not in bulk.body

    alerts = by_code["howto_alerts_screen"]
    assert "صفحة اليوم" in alerts.body

    barn = by_code["howto_barn_management"]
    assert "حامل - الشهور الأخيرة" in barn.body
