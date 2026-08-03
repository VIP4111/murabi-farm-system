"""بند إضافي 116 — توسعة ثانية لمرشد التطبيق: 11 إجابة "كيف" إضافية
(عمليات جماعية، البيع الذكي، الحليب، الفاتورة، القوائم المرجعية،
الأطباء، البروتوكولات، البلاغات، FCR، برامج الشياع، التكلفة الشهرية)."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


def _hit_codes(question):
    return {entry.code for entry in search(normalize(question), limit=3)}


def test_bulk_operations_howto_matches():
    assert "howto_bulk_operations" in _hit_codes("كيف أطبّق عملية جماعية على عدة رؤوس؟")


def test_smart_sale_screen_howto_matches():
    assert "howto_smart_sale_screen" in _hit_codes("كيف أستخدم شاشة البيع الذكي؟")


def test_milk_record_howto_matches():
    assert "howto_milk_record" in _hit_codes("كيف أسجل إنتاج الحليب؟")


def test_sale_invoice_howto_matches():
    assert "howto_sale_invoice" in _hit_codes("كيف أطبع فاتورة بيع؟")


def test_species_breed_color_howto_matches():
    assert "howto_species_breed_color" in _hit_codes("كيف أضيف سلالة جديدة؟")


def test_doctor_management_howto_matches():
    assert "howto_doctor_management" in _hit_codes("كيف أضيف طبيباً جديداً؟")


def test_create_protocol_howto_matches():
    assert "howto_create_protocol" in _hit_codes("كيف أنشئ بروتوكول علاج جديد؟")


def test_report_lifecycle_howto_matches():
    assert "howto_report_lifecycle" in _hit_codes("كيف يتحرك البلاغ بعد ما يرفعه العامل؟")


def test_fcr_calculator_howto_matches():
    assert "howto_fcr_calculator" in _hit_codes("كيف أحسب معدل التحويل الغذائي؟")


def test_twin_estrus_program_howto_matches():
    assert "howto_twin_estrus_program" in _hit_codes("كيف أدير برنامج شياع توأمي؟")


def test_monthly_cost_report_howto_matches():
    assert "howto_monthly_cost_report" in _hit_codes("كيف أشوف تكلفة الشهر الإجمالية؟")
