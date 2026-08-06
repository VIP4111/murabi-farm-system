"""اختبارات تنبيهات ومهام البيانات الناقصة (بند إضافي 135) — الحفظ
يبقى بدون شرط، بس أي رأس ناقص حقل مهم يطلع له تنبيه + مهمة مقترحة.
"السعر" مطلوب للشراء/الهدية/الرصيد الافتتاحي بس، مو المولود."""
from app.extensions import db
from app.core import data_completeness_service as dcs
from app.core import alerts_service
from app.models import Task
from app.models.animal import AnimalSource
from factories import make_animal


def _complete_purchase(animal_no="C-01"):
    a = make_animal(animal_no=animal_no, gender="ذكر", source=AnimalSource.PURCHASE, price=500)
    a.weight = 40
    a.purpose = "تسمين"
    db.session.commit()
    return a


def test_purchase_missing_price_is_flagged(app):
    a = make_animal(animal_no="P-01", gender="ذكر", source=AnimalSource.PURCHASE, price=None)
    a.weight = 40
    a.purpose = "تسمين"
    db.session.commit()
    assert "price" in dcs.missing_fields(a)


def test_birth_animal_does_not_require_price(app):
    a = make_animal(animal_no="B-01", gender="ذكر", source=AnimalSource.BIRTH, price=None)
    a.weight = 10
    a.purpose = "تسمين"
    db.session.commit()
    assert "price" not in dcs.missing_fields(a)


def test_gift_missing_price_is_flagged(app):
    a = make_animal(animal_no="G-01", gender="ذكر", source=AnimalSource.GIFT, price=None)
    a.weight = 20
    a.purpose = "تربية"
    db.session.commit()
    assert "price" in dcs.missing_fields(a)


def test_missing_gender_weight_purpose_flagged_regardless_of_source(app):
    a = make_animal(animal_no="B-02", gender=None, source=AnimalSource.BIRTH)
    db.session.commit()
    missing = dcs.missing_fields(a)
    assert "gender" in missing
    assert "weight" in missing
    assert "purpose" in missing


def test_fully_complete_animal_has_no_missing_fields(app):
    a = _complete_purchase()
    assert dcs.missing_fields(a) == []


def test_generate_completion_tasks_creates_task_for_incomplete_animal(app):
    a = make_animal(animal_no="P-02", gender=None, source=AnimalSource.PURCHASE, price=None)
    db.session.commit()

    created = dcs.generate_completion_tasks()
    assert any(t.animal_id == a.id for t in created)
    task = Task.query.filter_by(animal_id=a.id, task_type="animal_data_completion").first()
    assert task is not None
    assert "الجنس" in task.title


def test_generate_completion_tasks_no_task_for_complete_animal(app):
    _complete_purchase(animal_no="C-02")
    created = dcs.generate_completion_tasks()
    assert created == []


def test_second_call_does_not_duplicate_open_task(app):
    a = make_animal(animal_no="P-03", gender=None, source=AnimalSource.PURCHASE, price=None)
    db.session.commit()

    first = dcs.generate_completion_tasks()
    second = dcs.generate_completion_tasks()
    assert any(t.animal_id == a.id for t in first)
    assert not any(t.animal_id == a.id for t in second)


def test_incomplete_animal_data_alert_appears_in_get_alerts(app):
    a = make_animal(animal_no="P-04", gender=None, source=AnimalSource.PURCHASE, price=None)
    db.session.commit()

    alerts = alerts_service.get_alerts()
    assert any(al["category"] == "بيانات ناقصة" and al["animal_id"] == a.id for al in alerts)


def test_no_alert_for_complete_animal(app):
    a = _complete_purchase(animal_no="C-03")
    alerts = alerts_service.get_alerts()
    assert not any(al["category"] == "بيانات ناقصة" and al["animal_id"] == a.id for al in alerts)


def test_incomplete_data_generates_separate_alert_per_missing_field(app):
    """بند إضافي 138 — طلبك الصريح: "وزّع هذا التنبيه لعدة تنبيهات...
    قسمه على حسب المذكور فيه" — بدل تنبيه واحد يجمع كل النواقص بنص
    طويل، تنبيه مستقل لكل حقل ناقص لحاله."""
    a = make_animal(animal_no="P-05", gender="ذكر", source=AnimalSource.PURCHASE, price=None)
    db.session.commit()

    alerts = [al for al in alerts_service.get_alerts()
              if al["category"] == "بيانات ناقصة" and al["animal_id"] == a.id]
    assert len(alerts) == 3
    labels = {al["label"] for al in alerts}
    assert any("الوزن" in l for l in labels)
    assert any("الغرض" in l for l in labels)
    assert any("السعر" in l for l in labels)
