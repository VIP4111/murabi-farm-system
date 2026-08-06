"""بند إضافي 137 — قبل هذا البند، 0 من 52 مرض يستخدم `is_required`
(المحرك الموزون بند 127 يدعمها بدون أي بيانات فعلية تستخدمها). هذا
يزرع عرضاً "إجباري" اجتهادي لـ9 أمراض من الأمراض الأساسية العشرة
الأكثر اكتمالاً، idempotent عبر `flask seed`."""
from app.models import DiseaseType, DiseaseSymptomLink
from app.cli import REQUIRED_SYMPTOM_UPDATES


def test_seed_marks_required_symptoms_on_core_diseases(app):
    runner = app.test_cli_runner()
    runner.invoke(args=["seed"])

    for disease_name, symptom_name in REQUIRED_SYMPTOM_UPDATES.items():
        disease = DiseaseType.query.filter_by(name=disease_name).first()
        assert disease is not None, disease_name
        link = DiseaseSymptomLink.query.filter_by(disease_type_id=disease.id).join(
            DiseaseSymptomLink.symptom
        ).filter_by(name=symptom_name).first()
        assert link is not None, f"{disease_name} / {symptom_name}"
        assert link.is_required is True


def test_enterotoxemia_intentionally_has_no_required_symptom(app):
    """عرضها الأكيد يتفاوت بشدة (فوق حاد بدون أعراض مقابل حاد بإسهال
    دموي) — تعمّدنا ما نلزم بعرض واحد."""
    runner = app.test_cli_runner()
    runner.invoke(args=["seed"])

    disease = DiseaseType.query.filter_by(name="التسمم الدموي المعوي").first()
    assert disease is not None
    links = DiseaseSymptomLink.query.filter_by(disease_type_id=disease.id).all()
    assert not any(l.is_required for l in links)


def test_seed_is_idempotent_for_required_flags(app):
    runner = app.test_cli_runner()
    runner.invoke(args=["seed"])
    first_count = DiseaseSymptomLink.query.filter_by(is_required=True).count()

    runner.invoke(args=["seed"])
    second_count = DiseaseSymptomLink.query.filter_by(is_required=True).count()

    assert first_count == second_count == len(REQUIRED_SYMPTOM_UPDATES)
