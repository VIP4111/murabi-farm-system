"""بند إضافي 261 — بعد نقد صريح: تكلفة الزيارة البيطرية/علاج المرض
(VetVisit.cost / Disease.treatment_cost) كانت تُخزَّن على السجل نفسه
بس، بدون أي أثر بسجل "المالية" العام. **مهم**: لو التكلفة محسوبة من
استهلاك دواء صيدلية (كمية × سعر الوحدة)، ما تُنشأ عملية مالية جديدة
— قيمة الدواء اتُّحسبت فعلياً وقت شرائه (بند 259) — تُنشأ عملية بس
للتكلفة اليدوية (أجرة كشف/خدمة) اللي ما لها أي أثر مالي مسجَّل غيرها،
عشان نتفادى احتساب مزدوج."""
from datetime import date

from app.extensions import db
from app.health import health_service
from app.models import Finance
from app.models import Doctor
from factories import make_animal, make_pharmacy


def test_medicine_derived_cost_does_not_create_finance_row(app):
    """التكلفة من دواء = اتُّحسبت وقت الشراء أصلاً — إنشاء Finance
    هنا يكون احتساب مزدوج."""
    animal = make_animal(animal_no="VF-01")
    pharmacy = make_pharmacy(name="دواء أ", available_qty=10, unit_price=4)
    disease = health_service.record_disease(
        actor_user_id=1, animal_id=animal.id, disease_name="مرض اختبار",
        date_=date.today(), severity="light", pharmacy_id=pharmacy.id, quantity_used=2,
    )
    assert disease.treatment_cost == 8
    assert disease.finance_id is None
    assert Finance.query.filter_by(category="علاج مرض").count() == 0


def test_manual_service_fee_creates_finance_row(app):
    """تكلفة يدوية (أجرة كشف، بدون دواء) = مصروف حقيقي جديد، لازم
    يُسجَّل بالمالية."""
    animal = make_animal(animal_no="VF-02")
    doctor = Doctor(name="د. اختبار", status="active")
    db.session.add(doctor)
    db.session.commit()
    visit = health_service.record_vet_visit(
        actor_user_id=1, animal_id=animal.id, doctor_id=doctor.id,
        date_=date.today(), diagnosis="فحص عام", cost=150,
    )
    assert visit.cost == 150
    assert visit.finance_id is not None
    fin = Finance.query.get(visit.finance_id)
    assert fin is not None
    assert fin.operation_type == "expense"
    assert fin.category == "زيارة بيطرية"
    assert fin.amount == 150
    assert fin.related_animal_id == animal.id


def test_zero_cost_creates_no_finance_row(app):
    animal = make_animal(animal_no="VF-03")
    doctor = Doctor(name="د. اختبار ب", status="active")
    db.session.add(doctor)
    db.session.commit()
    visit = health_service.record_vet_visit(
        actor_user_id=1, animal_id=animal.id, doctor_id=doctor.id,
        date_=date.today(), diagnosis="فحص روتيني بدون تكلفة", cost=0,
    )
    assert visit.finance_id is None
    assert Finance.query.filter_by(category="زيارة بيطرية").count() == 0


def test_manual_disease_treatment_cost_creates_finance_row(app):
    animal = make_animal(animal_no="VF-04")
    disease = health_service.record_disease(
        actor_user_id=1, animal_id=animal.id, disease_name="مرض بدون دواء",
        date_=date.today(), severity="light", treatment_cost=75,
    )
    assert disease.treatment_cost == 75
    assert disease.finance_id is not None
    fin = Finance.query.get(disease.finance_id)
    assert fin.category == "علاج مرض"
    assert fin.amount == 75


def test_vet_visit_cost_reflected_in_finance_totals(app):
    animal = make_animal(animal_no="VF-05")
    doctor = Doctor(name="د. اختبار ج", status="active")
    db.session.add(doctor)
    db.session.commit()
    health_service.record_vet_visit(
        actor_user_id=1, animal_id=animal.id, doctor_id=doctor.id,
        date_=date.today(), diagnosis="كشف", cost=200,
    )
    total_out = sum(
        r.amount for r in Finance.query.filter(
            Finance.operation_type.in_(("purchase", "expense")), Finance.is_cancelled.is_(False),
        ).all()
    )
    assert total_out == 200
