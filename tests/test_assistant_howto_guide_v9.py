"""بند إضافي — طلبك: "جيت اسجل مولود سألت المساعد الذكي كيف اسجل
مولود رد علي ما قدرت أفهم سؤالك بدقة" و"دخلت حظائر... رجعت للمساعد
الذكي كتبتله كيف اضيف موعد وجبه قالي ما قدرت افهمك". فجوتان بأسئلة
واضحة على بندين معرفة موجودين أصلاً (howto_add_animal يذكر المولود
بس بدون كلمة "مولود" بكلماته المفتاحية، howto_feeding_schedule نفس
الشي مع "موعد وجبة") — أضفت كلمات مفتاحية تغطي صيغتك الحرفية بالضبط."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


def test_register_newborn_question_matches_add_animal_entry():
    results = search(normalize("كيف اسجل مولود"))
    assert results
    assert results[0].code == "howto_add_animal"


def test_add_animal_body_mentions_newborn_price_stays_empty():
    from app.assistant.knowledge_base import ENTRIES
    entry = next(e for e in ENTRIES if e.code == "howto_add_animal")
    assert "اتركه فاضي" in entry.body


def test_add_meal_schedule_question_matches_feeding_schedule_entry():
    results = search(normalize("كيف اضيف موعد وجبه"))
    assert results
    assert results[0].code == "howto_feeding_schedule"
