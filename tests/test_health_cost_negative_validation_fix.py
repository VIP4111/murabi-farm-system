"""فحص عميق — قسم الصحة: `record_vet_visit`/`record_disease` كانتا
تحفظان `cost`/`treatment_cost` اليدوي (أجرة كشف/خدمة بدون دواء) مباشرة
بدون أي تحقق. قيمة سالبة تتجاوز فحص `_link_finance_for_cost`'s
`cost <= 0` (فتفوّت إنشاء عملية مالية فقط)، لكن تبقى مخزَّنة سالبة على
`VetVisit.cost`/`Disease.treatment_cost` نفسها — تكسر بها "مالية
الدكتور" (`finance_health_view`) اللي تجمع القيم مباشرة، فتُنقص
الإجمالي المعروض بدل ما تعكس التكلفة الحقيقية."""
import pytest

from datetime import date

from app.health import health_service
from app.models import Doctor
from factories import make_animal


def test_vet_visit_negative_manual_cost_rejected(app):
    animal = make_animal(animal_no="HC-01")
    with pytest.raises(health_service.IncompleteRecordError):
        health_service.record_vet_visit(
            actor_user_id=1, animal_id=animal.id, doctor_id=1,
            date_=date.today(), diagnosis="فحص", cost=-50,
        )


def test_disease_negative_manual_treatment_cost_rejected(app):
    animal = make_animal(animal_no="HC-02")
    with pytest.raises(health_service.IncompleteRecordError):
        health_service.record_disease(
            actor_user_id=1, animal_id=animal.id, disease_name="مرض اختبار",
            date_=date.today(), severity="light", treatment_cost=-100,
        )


def test_vet_visit_positive_manual_cost_still_accepted(app):
    from app.extensions import db
    animal = make_animal(animal_no="HC-03")
    doctor = Doctor(name="د. اختبار هـ", status="active")
    db.session.add(doctor)
    db.session.flush()
    visit = health_service.record_vet_visit(
        actor_user_id=1, animal_id=animal.id, doctor_id=doctor.id,
        date_=date.today(), diagnosis="فحص", cost=75,
    )
    assert visit.cost == 75
