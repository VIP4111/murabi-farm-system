"""بند إضافي 117 — توسعة ثالثة لمرشد التطبيق: 10 إجابات "كيف" إضافية
(شراء جماعي، نواقص الصيدلية، دليل الحقن، الخدمات الاختيارية، مستودع
جديد، جدولة تحصين، قوائم مرجعية، مالية الصحة، تعطيل عضو، خطة الرأس)."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


def _hit_codes(question):
    return {entry.code for entry in search(normalize(question), limit=3)}


def test_bulk_purchase_intake_howto_matches():
    assert "howto_bulk_purchase_intake" in _hit_codes("كيف أستقبل عدة رؤوس مشتراة دفعة وحدة؟")


def test_pharmacy_shortages_howto_matches():
    assert "howto_pharmacy_shortages" in _hit_codes("كيف أشوف نواقص الصيدلية؟")


def test_injection_guide_howto_matches():
    assert "howto_injection_guide" in _hit_codes("وين ألقى دليل طرق الحقن؟")


def test_service_toggles_howto_matches():
    assert "howto_service_toggles" in _hit_codes("كيف أفعّل خدمة اختيارية؟")


def test_new_warehouse_howto_matches():
    assert "howto_new_warehouse" in _hit_codes("كيف أنشئ مستودعاً جديداً؟")


def test_manage_vaccination_schedule_entry_howto_matches():
    assert "howto_manage_vaccination_schedule_entry" in _hit_codes("كيف ألغي جدولة تحصين جماعي؟")


def test_disease_drug_admin_lists_howto_matches():
    assert "howto_disease_drug_admin_lists" in _hit_codes("كيف أضيف نوع مرض جديد؟")


def test_finance_health_view_howto_matches():
    assert "howto_finance_health_view" in _hit_codes("كيف أشوف مالية الصحة فقط؟")


def test_edit_team_member_howto_matches():
    assert "howto_edit_team_member" in _hit_codes("كيف أعطّل حساب عضو فريق؟")


def test_animal_workflow_plan_howto_matches():
    assert "howto_animal_workflow_plan" in _hit_codes("كيف أشوف خطة دورة إنتاج رأس معيّن؟")
