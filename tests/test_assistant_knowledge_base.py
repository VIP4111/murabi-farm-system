"""اختبارات البنود الخمسة الجديدة بقاعدة معرفة المساعد الذكي (بند إضافي
55.3): كل بند يُطابَق فعلياً بكلماته المفتاحية، وما فيه أي رقم جرعة."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


def _hit_codes(question):
    return {entry.code for entry in search(normalize(question), limit=3)}


def test_buying_checklist_matches():
    assert "buying_checklist" in _hit_codes("وش أفحص قبل الشراء؟")


def test_biosecurity_matches():
    assert "biosecurity" in _hit_codes("كيف أمنع انتقال العدوى بين الحيوانات؟")


def test_heat_stress_matches():
    assert "heat_stress" in _hit_codes("شلون أدير الإجهاد الحراري بالصيف؟")


def test_water_minerals_matches():
    assert "water_minerals" in _hit_codes("وش أفضل أملاح للمشرب؟")


def test_smart_sale_explained_matches():
    assert "smart_sale_explained" in _hit_codes("وش يعني توصية بيع من النظام؟")


def test_no_dosage_numbers_in_new_entries():
    import re
    from app.assistant.knowledge_base import ENTRIES
    new_codes = {"buying_checklist", "biosecurity", "heat_stress", "water_minerals", "smart_sale_explained"}
    dosage_pattern = re.compile(r"\d+\s*(مل|ملغم|ملجم|سم3|مليلتر)")
    for entry in ENTRIES:
        if entry.code in new_codes:
            assert not dosage_pattern.search(entry.body), entry.code
