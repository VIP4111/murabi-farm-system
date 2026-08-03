"""بند إضافي 114 — قاعدة معرفة "مرشد استخدام التطبيق" (9 أسئلة "كيف
أسوي كذا بالتطبيق")، إضافة على قاعدة المعرفة البيطرية الموجودة أصلاً."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


def _hit_codes(question):
    return {entry.code for entry in search(normalize(question), limit=3)}


def test_add_animal_howto_matches():
    assert "howto_add_animal" in _hit_codes("كيف أضيف حيوان جديد؟")


def test_record_disease_howto_matches():
    assert "howto_record_disease" in _hit_codes("كيف أسجل مرض؟")


def test_assign_task_howto_matches():
    assert "howto_assign_task" in _hit_codes("كيف أوزع مهمة على عامل؟")


def test_record_sale_howto_matches():
    assert "howto_record_sale" in _hit_codes("كيف أسجل عملية بيع؟")


def test_pharmacy_stock_howto_matches():
    assert "howto_pharmacy_stock" in _hit_codes("كيف أضيف دواء جديد للصيدلية؟")


def test_worker_report_howto_matches():
    assert "howto_worker_report" in _hit_codes("كيف أرفع بلاغ؟")


def test_alerts_screen_howto_matches():
    assert "howto_alerts_screen" in _hit_codes("ايش تعرض شاشة التنبيهات؟")


def test_add_team_member_howto_matches():
    assert "howto_add_team_member" in _hit_codes("كيف أضيف عضو فريق جديد؟")


def test_family_view_howto_matches():
    assert "howto_family_view" in _hit_codes("وش هي شاشة والدي المتابعة المبسطة؟")
