"""بند إضافي 115 — استكمال بند 114: 17 إجابة "كيف" إضافية تغطي بقية
الوحدات الرئيسية (الصحة، التكاثر، العلف، المالية، التقارير، الدفعات،
المستودعات، النعام، المناخ، النسخ الاحتياطي، الصلاحيات)."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


def _hit_codes(question):
    return {entry.code for entry in search(normalize(question), limit=3)}


def test_vet_visit_howto_matches():
    assert "howto_vet_visit" in _hit_codes("كيف أسجل زيارة بيطرية؟")


def test_smart_diagnose_howto_matches():
    assert "howto_smart_diagnose" in _hit_codes("كيف أستخدم أداة التشخيص الذكي؟")


def test_vaccination_schedule_howto_matches():
    assert "howto_vaccination_schedule" in _hit_codes("كيف أجدول تحصين جماعي؟")


def test_treatment_protocol_howto_matches():
    assert "howto_treatment_protocol" in _hit_codes("كيف أطبّق بروتوكول علاج جاهز؟")


def test_mating_pregnancy_howto_matches():
    assert "howto_mating_pregnancy" in _hit_codes("كيف أسجل تلقيح جديد؟")


def test_sonar_howto_matches():
    assert "howto_sonar" in _hit_codes("كيف أسجل فحص سونار؟")


def test_feed_ration_howto_matches():
    assert "howto_feed_ration" in _hit_codes("كيف أبني وصفة علف؟")


def test_feed_optimizer_howto_matches():
    assert "howto_feed_optimizer" in _hit_codes("كيف يشتغل موازن العليقة؟")


def test_finance_entry_howto_matches():
    assert "howto_finance_entry" in _hit_codes("كيف أسجل عملية مالية جديدة؟")


def test_export_reports_howto_matches():
    assert "howto_export_reports" in _hit_codes("كيف أصدّر تقرير Excel؟")


def test_batch_receiving_howto_matches():
    assert "howto_batch_receiving" in _hit_codes("كيف أستقبل دفعة حيوانات جديدة؟")


def test_warehouse_transfer_howto_matches():
    assert "howto_warehouse_transfer" in _hit_codes("كيف أحوّل مخزون بين مستودعين؟")


def test_ostrich_egg_howto_matches():
    assert "howto_ostrich_egg" in _hit_codes("كيف أسجل بيضة نعام جديدة؟")


def test_climate_settings_howto_matches():
    assert "howto_climate_settings" in _hit_codes("كيف أفعّل رادار المناخ؟")


def test_backup_howto_matches():
    assert "howto_backup" in _hit_codes("كيف آخذ نسخة احتياطية؟")


def test_roles_permissions_howto_matches():
    assert "howto_roles_permissions" in _hit_codes("كيف أنشئ دوراً وظيفياً جديداً؟")


def test_setup_checklist_howto_matches():
    assert "howto_setup_checklist" in _hit_codes("وش هي قائمة خطوات التجهيز؟")


def test_readiness_check_howto_matches():
    assert "howto_readiness_check" in _hit_codes("كيف أستخدم فحص الجاهزية قبل النشر؟")
