"""مصانع بيانات اختبار خفيفة — تُنشئ الحد الأدنى من الحقول المطلوبة
فقط، بدون منطق عمل (المنطق نفسه مسؤولية الدوال المختبَرة، مو المصنع)."""
from datetime import date

from app.extensions import db
from app.models import Barn, Pharmacy, Feed, DiseaseType, Symptom, DiseaseSymptomLink, WeatherReading, Equipment
from app.models.animal import Animal, AnimalSource


def make_barn(barn_no="B-01", barn_name="حظيرة اختبار", barn_type="عادية", responsible_worker_id=None):
    barn = Barn(barn_no=barn_no, barn_name=barn_name, barn_type=barn_type,
                responsible_worker_id=responsible_worker_id)
    db.session.add(barn)
    db.session.commit()
    return barn


def make_animal(animal_no="A-01", gender="أنثى", source=AnimalSource.PURCHASE,
                 barn_id=None, price=None, status="active", breed="عام/غير محدد"):
    animal = Animal(
        animal_no=animal_no, source=source, gender=gender, species="sheep_goat",
        barn_id=barn_id, purchase_date=date.today() if source == AnimalSource.PURCHASE else None,
        price=price, lifecycle_stage="source", status=status, breed=breed,
    )
    db.session.add(animal)
    db.session.commit()
    return animal


def make_pharmacy(name="دواء اختبار", available_qty=10, unit_price=None, withdrawal_days=0,
                   medicine_class=None, contains_high_copper=False):
    item = Pharmacy(name=name, available_qty=available_qty, unit_price=unit_price,
                     withdrawal_days=withdrawal_days, medicine_class=medicine_class,
                     contains_high_copper=contains_high_copper, status="active")
    db.session.add(item)
    db.session.commit()
    return item


def make_feed(name="علف اختبار", available_qty=100, unit_price=None,
              protein_percent=None, energy_kcal_per_kg=None, calcium_percent=None,
              phosphorus_percent=None, feed_class=None, contains_high_copper=False):
    item = Feed(name=name, available_qty=available_qty, unit_price=unit_price,
                protein_percent=protein_percent, energy_kcal_per_kg=energy_kcal_per_kg,
                calcium_percent=calcium_percent, phosphorus_percent=phosphorus_percent,
                feed_class=feed_class, contains_high_copper=contains_high_copper,
                unit="كجم", status="active")
    db.session.add(item)
    db.session.commit()
    return item


def make_equipment(name="أداة اختبار", available_qty=10, unit="قطعة", unit_price=None):
    item = Equipment(name=name, available_qty=available_qty, unit=unit, unit_price=unit_price, status="active")
    db.session.add(item)
    db.session.commit()
    return item


def make_disease_type(name="مرض اختبار"):
    dt = DiseaseType(name=name)
    db.session.add(dt)
    db.session.commit()
    return dt


def make_symptom(name="عرض اختبار", is_primary=False):
    s = Symptom(name=name, is_primary=is_primary)
    db.session.add(s)
    db.session.commit()
    return s


def link_symptom(disease_type, symptom, weight=1):
    link = DiseaseSymptomLink(disease_type_id=disease_type.id, symptom_id=symptom.id, weight=weight)
    db.session.add(link)
    db.session.commit()
    return link


def make_weather_reading(day, temp_max_c=35, humidity_at_peak=30, thi=None, stress_level="normal"):
    from app.climate.climate_service import calculate_thi
    reading = WeatherReading(
        date=day, temp_max_c=temp_max_c, humidity_at_peak=humidity_at_peak,
        thi=thi if thi is not None else calculate_thi(temp_max_c, humidity_at_peak),
        stress_level=stress_level, source="manual-test",
    )
    db.session.add(reading)
    db.session.commit()
    return reading
