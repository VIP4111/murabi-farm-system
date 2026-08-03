"""بند إضافي 112 — تنبيه لو خطة عزل (بند 4) اضطرت تولّد مهام بدون
حظيرة عزل فعلية (ما فيه أي حظيرة بنوع "عزل" بالنظام أصلاً)."""
from app.extensions import db
from app.core.animal_service import register_birth
from app.core.alerts_service import get_alerts
from factories import make_animal, make_barn
from app.models import Barn


def test_alert_appears_when_no_isolation_barn_exists(app):
    assert Barn.query.filter_by(barn_type="عزل").count() == 0
    mother = make_animal(animal_no="NB-01", gender="أنثى")
    register_birth(mother=mother, gender="أنثى", weight=3.0)

    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "عزل بدون حظيرة مصنّفة"]
    assert len(matching) == 1
    assert matching[0]["urgent"] is True


def test_no_alert_when_isolation_barn_exists(app):
    make_barn(barn_no="ISO-1", barn_name="حظيرة عزل حقيقية", barn_type="عزل")
    mother = make_animal(animal_no="NB-02", gender="أنثى")
    register_birth(mother=mother, gender="ذكر", weight=3.0)

    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "عزل بدون حظيرة مصنّفة"]
    assert len(matching) == 0


def test_no_alert_when_no_births_happened(app):
    assert Barn.query.filter_by(barn_type="عزل").count() == 0
    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "عزل بدون حظيرة مصنّفة"]
    assert len(matching) == 0
