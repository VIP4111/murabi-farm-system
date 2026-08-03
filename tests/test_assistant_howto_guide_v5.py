"""بند إضافي 118 — توسعة رابعة (وأخيرة لهذي الجلسة) لمرشد التطبيق: 6
إجابات "كيف" إضافية (حاضنات، العمل بدون إنترنت، دورة حياة البلاغ
التفصيلية، إزالة جهاز تكاثر، معلومات سريعة، تقارير النفوق/الولادات)."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


def _hit_codes(question):
    return {entry.code for entry in search(normalize(question), limit=3)}


def test_incubator_management_howto_matches():
    assert "howto_incubator_management" in _hit_codes("كيف أضيف حاضنة جديدة؟")


def test_offline_mode_howto_matches():
    assert "howto_offline_mode" in _hit_codes("هل التطبيق يشتغل بدون إنترنت؟")


def test_report_execute_vs_transfer_howto_matches():
    assert "howto_report_execute_vs_transfer" in _hit_codes("ما الفرق بين تنفيذ وتحويل البلاغ؟")


def test_remove_repro_device_howto_matches():
    assert "howto_remove_repro_device" in _hit_codes("كيف أسجّل إزالة إسفنجة؟")


def test_animal_quick_info_howto_matches():
    assert "howto_animal_quick_info" in _hit_codes("وش تعرض معلومات سريعة عن الحيوان؟")


def test_mortality_births_reports_howto_matches():
    assert "howto_mortality_births_reports" in _hit_codes("كيف أفهم تقرير النفوق؟")
