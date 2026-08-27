"""بند إضافي 271 — تدقيق عميق بقاعدة معرفة المساعد الذكي: 3 بنود
قديمة (شراء دواء، تسجيل مرض، تسجيل زيارة بيطرية) ما كانت تذكر إطلاقاً
الربط المالي التلقائي الجديد (بند 259/261) — لا خطأ صريح، بس معلومة
ناقصة تخلي رد المساعد غير كامل لو سُئل عن هذا التفصيل بالذات."""
from app.assistant.knowledge_base import ENTRIES


def test_pharmacy_purchase_mentions_finance_link():
    entry = next(e for e in ENTRIES if e.code == "howto_pharmacy_purchase")
    assert "عملية" in entry.body and "مالية" in entry.body
    assert "أدوية" in entry.body


def test_record_disease_mentions_finance_link():
    entry = next(e for e in ENTRIES if e.code == "howto_record_disease")
    assert "علاج مرض" in entry.body


def test_vet_visit_mentions_finance_link():
    entry = next(e for e in ENTRIES if e.code == "howto_vet_visit")
    assert "زيارة بيطرية" in entry.body and "مصروف" in entry.body


def test_finance_health_view_entry_unaffected_and_still_present():
    entry = next(e for e in ENTRIES if e.code == "howto_finance_health_view")
    assert "مالية الصحة" in entry.body
