"""اختبارات app/core/bulk_service.py — محرك العمليات الجماعية (بند 17،
التسع عمليات + الشراء الجماعي). التركيز: كل عملية جماعية ترجع نتيجة
لكل رأس على حدة، ورأس واحد يفشل ما يوقف بقية الدفعة ("لا شيء يختفي
بصمت")."""
from datetime import date

import pytest

from app.core import bulk_service
from app.core import cycle_engine
from app.models import Barn, Finance, SonarResult
from app.models.animal_log import AnimalNote
from factories import make_animal, make_barn, make_pharmacy


def test_bulk_weight_updates_each_animal(app):
    a1 = make_animal(animal_no="BW-01")
    a2 = make_animal(animal_no="BW-02")
    results = bulk_service.apply_bulk_weight(
        animal_ids=[a1.id, a2.id], record_date=date.today(),
        weights_by_id={a1.id: 40, a2.id: 45}, notes_by_id={}, actor_user_id=1,
    )
    assert a1.weight == 40 and a2.weight == 45
    assert all(r.startswith("تم") for r in results.values())


def test_bulk_weight_skips_animal_without_weight_entered(app):
    a1 = make_animal(animal_no="BW-03")
    results = bulk_service.apply_bulk_weight(
        animal_ids=[a1.id], record_date=date.today(),
        weights_by_id={}, notes_by_id={}, actor_user_id=1,
    )
    assert "تخطّي" in results[a1.id]
    assert a1.weight is None


def test_bulk_note_appends_extra_note_per_animal(app):
    a1 = make_animal(animal_no="BN-01")
    bulk_service.apply_bulk_note(
        animal_ids=[a1.id], general_note="فحص عام", note_date=date.today(),
        extra_notes_by_id={a1.id: "يعرج قليلاً"}, actor_user_id=1,
    )
    notes = AnimalNote.query.filter_by(animal_id=a1.id).all()
    assert len(notes) == 1
    assert "فحص عام" in notes[0].note and "يعرج قليلاً" in notes[0].note


def test_bulk_barn_move_moves_all_and_logs_audit(app):
    from app.models import AuditLog
    a1 = make_animal(animal_no="BM-01")
    a2 = make_animal(animal_no="BM-02")
    barn = make_barn(barn_no="TGT")
    bulk_service.apply_bulk_barn_move(animal_ids=[a1.id, a2.id], barn_id=barn.id, actor_user_id=1)
    assert a1.barn_id == barn.id and a2.barn_id == barn.id
    assert AuditLog.query.filter_by(action="animal.bulk_barn_move").count() == 2


def test_bulk_vaccination_rejects_animal_when_stock_runs_out_mid_batch(app):
    """كمية مشتركة (2) لكل رأس، مخزون 3 وحدات بس — الرأس الأول ينجح
    (يستهلك 2)، الثاني يُرفض (المتبقي 1 أقل من المطلوب)."""
    a1 = make_animal(animal_no="BV-01")
    a2 = make_animal(animal_no="BV-02")
    pharmacy = make_pharmacy(name="لقاح جماعي", available_qty=3)
    results = bulk_service.apply_bulk_vaccination(
        animal_ids=[a1.id, a2.id], vaccine_name="لقاح", record_date=date.today(),
        next_due_date=None, pharmacy_id=pharmacy.id, quantity_used_per_head=2, actor_user_id=1,
    )
    outcomes = list(results.values())
    assert outcomes.count("تم") == 1
    assert sum(1 for r in outcomes if r.startswith("مرفوض")) == 1
    assert pharmacy.available_qty == 1


def test_bulk_sale_rejects_animal_not_at_destiny_stage(app):
    a1 = make_animal(animal_no="BS-01")
    results = bulk_service.apply_bulk_sale(
        animal_ids=[a1.id], sale_date=date.today(),
        prices_by_id={a1.id: 500}, notes=None, actor_user_id=1,
    )
    assert results[a1.id].startswith("مرفوض")
    assert a1.status == "active"


def test_bulk_sale_skips_animal_with_no_price(app):
    a1 = make_animal(animal_no="BS-02")
    results = bulk_service.apply_bulk_sale(
        animal_ids=[a1.id], sale_date=date.today(),
        prices_by_id={}, notes=None, actor_user_id=1,
    )
    assert "تخطّي" in results[a1.id]


def test_bulk_mark_dead_succeeds_for_all_with_no_gate(app):
    a1 = make_animal(animal_no="BD-01", price=300)
    a2 = make_animal(animal_no="BD-02", price=400)
    results = bulk_service.apply_bulk_mark_dead(
        animal_ids=[a1.id, a2.id], death_date=date.today(), reason="اختبار", actor_user_id=1,
    )
    assert a1.status == "dead" and a2.status == "dead"
    assert all(r == "تم تسجيل النفوق" for r in results.values())
    assert Finance.query.filter_by(operation_type="expense").count() == 2


def test_bulk_disease_rejects_when_medicine_selected_without_quantity(app):
    a1 = make_animal(animal_no="BDZ-01")
    pharmacy = make_pharmacy(name="دواء مرض جماعي", available_qty=10)
    results = bulk_service.apply_bulk_disease(
        animal_ids=[a1.id], disease_name="مرض اختبار", record_date=date.today(),
        severity="light", pharmacy_id=pharmacy.id, quantity_used_per_head=None, actor_user_id=1,
    )
    assert results[a1.id].startswith("مرفوض")


def test_bulk_disease_success_path(app):
    a1 = make_animal(animal_no="BDZ-02")
    results = bulk_service.apply_bulk_disease(
        animal_ids=[a1.id], disease_name="مرض اختبار", record_date=date.today(),
        severity="light", pharmacy_id=None, quantity_used_per_head=None, actor_user_id=1,
    )
    assert results[a1.id] == "تم تسجيل الحالة"


def test_bulk_isolation_rejects_when_no_isolation_barn_exists(app):
    a1 = make_animal(animal_no="BI-01")
    results = bulk_service.apply_bulk_isolation(
        animal_ids=[a1.id], reason=None, note_date=date.today(), actor_user_id=1,
    )
    assert "مرفوض" in results[a1.id]


def test_bulk_isolation_moves_animals_and_adds_note(app):
    make_barn(barn_no="ISO", barn_type="عزل")
    a1 = make_animal(animal_no="BI-02")
    results = bulk_service.apply_bulk_isolation(
        animal_ids=[a1.id], reason="اشتباه مرض", note_date=date.today(), actor_user_id=1,
    )
    iso_barn = Barn.query.filter_by(barn_type="عزل").first()
    assert a1.barn_id == iso_barn.id
    assert "تم" in results[a1.id]
    notes = AnimalNote.query.filter_by(animal_id=a1.id).all()
    assert len(notes) == 1 and "اشتباه مرض" in notes[0].note


def test_bulk_sonar_records_distinct_result_per_animal(app):
    a1 = make_animal(animal_no="BSN-01", gender="أنثى")
    a2 = make_animal(animal_no="BSN-02", gender="أنثى")
    bulk_service.apply_bulk_sonar(
        animal_ids=[a1.id, a2.id], exam_date=date.today(),
        result_by_id={a1.id: "حامل", a2.id: "غير حامل"},
        embryo_count_by_id={a1.id: 2}, doctor_id=None, actor_user_id=1,
    )
    r1 = SonarResult.query.filter_by(ewe_id=a1.id).first()
    r2 = SonarResult.query.filter_by(ewe_id=a2.id).first()
    assert r1.result == "حامل" and r1.embryo_count == 2
    assert r2.result == "غير حامل" and r2.embryo_count is None


def test_bulk_purchase_creates_all_animals_with_finance_rows(app):
    results = bulk_service.apply_bulk_purchase(
        rows=[
            {"animal_no": "BP-01", "gender": "ذكر", "weight": 30, "price": 500},
            {"animal_no": "BP-02", "gender": "أنثى", "weight": 28, "price": 450},
        ],
        barn_id=None, purchase_date=date.today(), species="sheep_goat", actor_user_id=1,
    )
    assert results["BP-01"] == "تمت الإضافة"
    assert results["BP-02"] == "تمت الإضافة"
    assert Finance.query.filter_by(operation_type="purchase").count() == 2


def test_bulk_purchase_rejects_duplicate_animal_no(app):
    make_animal(animal_no="DUP-01")
    results = bulk_service.apply_bulk_purchase(
        rows=[{"animal_no": "DUP-01", "gender": "ذكر", "weight": None, "price": None}],
        barn_id=None, purchase_date=date.today(), species="sheep_goat", actor_user_id=1,
    )
    assert results["DUP-01"].startswith("مرفوض")


def test_bulk_purchase_skips_row_with_empty_animal_no(app):
    results = bulk_service.apply_bulk_purchase(
        rows=[{"animal_no": "", "gender": "ذكر", "weight": None, "price": None}],
        barn_id=None, purchase_date=date.today(), species="sheep_goat", actor_user_id=1,
    )
    assert results == {}
