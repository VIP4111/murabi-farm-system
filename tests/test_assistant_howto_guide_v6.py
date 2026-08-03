"""بند إضافي 120 — توسعة سادسة لمرشد التطبيق. 16 موضوع جديد اكتُشفت
بمسح شامل لمسارات التطبيق (معدات، حظائر، صيدلية، تكاثر، علف، دفعات،
مهام، تقارير، مناخ) ما كان لها إجابة بمرشد التطبيق رغم إنها شاشات
حقيقية بالنظام."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


QUESTIONS = {
    "howto_equipment_add": "كيف أضيف معدة جديدة؟",
    "howto_equipment_movement": "كيف أسجل استعارة معدة؟",
    "howto_barn_management": "كيف أضيف حظيرة جديدة؟",
    "howto_pharmacy_purchase": "كيف أسجل شراء دواء جديد؟",
    "howto_pharmacy_dose_table": "كيف أضبط جدول الجرعة حسب العمر؟",
    "howto_usage_drug_catalog": "كيف أضيف طريقة استخدام جديدة؟",
    "howto_repro_program_status": "كيف أغيّر حالة برنامج التزامن؟",
    "howto_pregnancy_abort": "كيف أسجل إجهاض حيوان؟",
    "howto_feed_movements": "كيف أسجل حركة صرف علف؟",
    "howto_feed_barn_plans": "كيف أحدد خطة تغذية لحظيرة؟",
    "howto_feed_calculator": "وش الفرق بين حاسبة العلف والموازن؟",
    "howto_batch_hold_catchup": "كيف ألحق رأس متأخر بالدفعة؟",
    "howto_task_daily_templates": "كيف أضيف مهمة يومية متكررة؟",
    "howto_task_lifecycle_active": "كيف ألغي مهمة فعلية؟",
    "howto_purchase_request_report": "كيف أنشئ قائمة طلب شراء؟",
    "howto_climate_refresh": "كيف أحدث توقعات الطقس يدوياً؟",
}


def test_all_v6_howto_questions_match_expected_entry():
    for expected_code, question in QUESTIONS.items():
        results = search(normalize(question))
        assert results, f"ما رجع أي نتيجة للسؤال: {question}"
        assert results[0].code == expected_code, (
            f"السؤال '{question}' رجع '{results[0].code}' بدل '{expected_code}'"
        )


def test_v6_entries_have_nonempty_body_and_keywords():
    from app.assistant.knowledge_base import ENTRIES
    by_code = {e.code: e for e in ENTRIES}
    for code in QUESTIONS:
        entry = by_code[code]
        assert entry.body.strip()
        assert len(entry.keywords) >= 2
