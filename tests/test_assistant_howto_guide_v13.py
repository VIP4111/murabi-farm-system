"""بند إضافي — طلبك بالنص: "كيف اضيف اعلاف" سألته المساعد الذكي ورد
"ما قدرت أفهم سؤالك بدقة" رغم وجود بند معرفة (howto_feed_item_new)
يشرح بالضبط هذا — فجوة كلمات مفتاحية بحتة، صيغتك الحرفية "اضيف اعلاف"
ما كانت موجودة أصلاً بقائمة الكلمات."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


def test_how_to_add_feed_literal_phrasing_matches_entry():
    results = search(normalize("كيف اضيف اعلاف"))
    assert results
    assert results[0].code == "howto_feed_item_new"
