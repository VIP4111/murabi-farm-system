"""اختبارات المساعد التشخيصي — محرك المطابقة والشجرة التفاعلية
(بند إضافي 48، القسم الأول)."""
from app.health import health_service
from factories import make_disease_type, make_symptom, link_symptom


def test_score_diagnoses_ranks_by_weighted_symptom_match(app):
    fever = make_symptom("حرارة", is_primary=True)
    cough = make_symptom("سعال")
    limp = make_symptom("عرج")

    pneumonia = make_disease_type("التهاب رئوي")
    link_symptom(pneumonia, fever, weight=2)
    link_symptom(pneumonia, cough, weight=3)

    footrot = make_disease_type("تعفن الظلف")
    link_symptom(footrot, limp, weight=3)

    results = health_service.score_diagnoses(symptom_ids=[fever.id, cough.id])
    assert results[0]["disease_type"].name == "التهاب رئوي"
    assert results[0]["score"] == 5
    assert set(results[0]["matched_symptoms"]) == {"حرارة", "سعال"}
    assert len(results) == 1  # تعفن الظلف ما له أي عرض مطابق


def test_score_diagnoses_empty_symptoms_returns_empty(app):
    assert health_service.score_diagnoses(symptom_ids=[]) == []


def test_related_symptoms_narrows_to_diseases_sharing_primary(app):
    fever = make_symptom("حرارة", is_primary=True)
    cough = make_symptom("سعال")
    discharge = make_symptom("إفرازات أنف")
    unrelated = make_symptom("حكة جلدية")

    pneumonia = make_disease_type("التهاب رئوي")
    link_symptom(pneumonia, fever, weight=2)
    link_symptom(pneumonia, cough, weight=3)
    link_symptom(pneumonia, discharge, weight=2)

    mange = make_disease_type("جرب")
    link_symptom(mange, unrelated, weight=3)

    related = health_service.related_symptoms(fever.id)
    related_names = {s.name for s in related}
    assert related_names == {"سعال", "إفرازات أنف"}
    assert "حكة جلدية" not in related_names
    assert "حرارة" not in related_names  # العرض الرئيسي نفسه لا يتكرر


def test_related_symptoms_for_unlinked_primary_returns_empty(app):
    lonely = make_symptom("عرض معزول", is_primary=True)
    assert health_service.related_symptoms(lonely.id) == []
