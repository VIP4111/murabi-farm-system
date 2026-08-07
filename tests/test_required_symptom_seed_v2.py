"""بند إضافي (تكملة 137) — طلبك: أكمل توسعة الأعراض الإجبارية لبقية
الـ40 مرض غير المغطاة (بند 137 كان غطّى 9 بس من الأمراض الأساسية).
نفس المنطق idempotent، يحدّث is_required=True على روابط موجودة أصلاً
من مكتبة DISEASE_LIBRARY_V2 الموسّعة."""
from app.models import DiseaseType, DiseaseSymptomLink
from app.cli import REQUIRED_SYMPTOM_UPDATES, REQUIRED_SYMPTOM_UPDATES_V2
from app.disease_library_data import DISEASE_ALIAS_MAP


def test_seed_marks_required_symptoms_on_extended_diseases(app):
    runner = app.test_cli_runner()
    runner.invoke(args=["seed"])

    for disease_name, symptom_name in REQUIRED_SYMPTOM_UPDATES_V2.items():
        target_name = DISEASE_ALIAS_MAP.get(disease_name, disease_name)
        disease = DiseaseType.query.filter_by(name=target_name).first()
        assert disease is not None, disease_name
        link = DiseaseSymptomLink.query.filter_by(disease_type_id=disease.id).join(
            DiseaseSymptomLink.symptom
        ).filter_by(name=symptom_name).first()
        assert link is not None, f"{disease_name} / {symptom_name}"
        assert link.is_required is True


def test_plant_toxicity_intentionally_has_no_required_symptom(app):
    """أعراضها تتفاوت بشدة حسب نوع النبات المتناول — نفس مبدأ استثناء
    التسمم الدموي المعوي ببند 137 الأول."""
    runner = app.test_cli_runner()
    runner.invoke(args=["seed"])

    disease = DiseaseType.query.filter_by(
        name="التسمم بالنباتات السامة / الدفلة (Plant Toxicity)"
    ).first()
    assert disease is not None
    links = DiseaseSymptomLink.query.filter_by(disease_type_id=disease.id).all()
    assert not any(l.is_required for l in links)


def test_seed_is_idempotent_for_extended_required_flags(app):
    runner = app.test_cli_runner()
    runner.invoke(args=["seed"])
    first_count = DiseaseSymptomLink.query.filter_by(is_required=True).count()

    runner.invoke(args=["seed"])
    second_count = DiseaseSymptomLink.query.filter_by(is_required=True).count()

    assert first_count == second_count == len(REQUIRED_SYMPTOM_UPDATES) + len(REQUIRED_SYMPTOM_UPDATES_V2)
