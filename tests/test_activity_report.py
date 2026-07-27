"""اختبارات تقرير إنجاز اليوم (بند إضافي 55.2) — يجمع من الجداول الفعلية
الموجودة (مهام، أمراض، تحصينات، أوزان، حليب، مالية) لنفس نطاق التاريخ
المشترك مع بقية التقارير، بدون أي جدول نشاط جديد."""
from datetime import date, datetime, timezone

from app.extensions import db
from app.reports.report_service import activity_report
from app.models import Disease, Vaccination, AnimalWeight, MilkRecord, Finance, Task
from factories import make_animal


def test_empty_range_has_no_rows(app):
    data = activity_report(date(2020, 1, 1), date(2020, 1, 2))
    assert data["table"]["rows"] == []


def test_disease_and_weight_appear_in_range(app):
    animal = make_animal(animal_no="ACT-01")
    today = date.today()
    db.session.add(Disease(animal_id=animal.id, disease_name="مرض اختبار",
                            date=today, status="active"))
    db.session.add(AnimalWeight(animal_id=animal.id, date=today, weight=42.5))
    db.session.commit()

    data = activity_report(today, today)
    categories = {row[1] for row in data["table"]["rows"]}
    assert "مرض" in categories
    assert "وزن" in categories
    animal_nos = {row[3] for row in data["table"]["rows"]}
    assert "ACT-01" in animal_nos


def test_completed_and_failed_tasks_appear_with_correct_category(app):
    today = date.today()
    now = datetime.now(timezone.utc)
    done = Task(title="مهمة منجزة", status="done", completed_at=now)
    failed = Task(title="مهمة متعذّرة", status="failed", failed_at=now, failure_reason="نقص الأدوات")
    db.session.add_all([done, failed])
    db.session.commit()

    data = activity_report(today, today)
    titles_by_category = {row[1]: row[2] for row in data["table"]["rows"]}
    assert titles_by_category.get("مهمة مكتملة") == "مهمة منجزة"
    assert titles_by_category.get("مهمة متعذّرة") == "مهمة متعذّرة"


def test_out_of_range_records_excluded(app):
    animal = make_animal(animal_no="ACT-02")
    db.session.add(Vaccination(animal_id=animal.id, vaccine_name="تحصين قديم",
                                date=date(2020, 1, 1)))
    db.session.commit()

    data = activity_report(date.today(), date.today())
    assert not any(row[2] == "تحصين قديم" for row in data["table"]["rows"])


def test_kpis_summarize_counts_per_category(app):
    animal = make_animal(animal_no="ACT-03")
    today = date.today()
    db.session.add(MilkRecord(animal_id=animal.id, date=today, session="صباح", quantity_liters=2.5))
    db.session.add(Finance(date=today, operation_type="expense", item="علف",
                            amount=100, is_cancelled=False))
    db.session.commit()

    data = activity_report(today, today)
    kpi_categories = {name for name, _ in data["kpis"]}
    assert "حليب" in kpi_categories
    assert "مالية" in kpi_categories
