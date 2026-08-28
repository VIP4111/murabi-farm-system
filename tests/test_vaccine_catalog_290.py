"""بند إضافي 290 — طلبك الصريح "شنهو جدول التحصين... ابدأ" بعد بحث
خارجي فعلي (مصادر بيطرية + تقرير محلي عن التحصينات الموسمية). 3 أصناف
لقاحات مرجعية بالصيدلية — بدون جرعة أو سعر مفروضين (الدكتور يعبّيهم
لما يستقبل المنتج الفعلي)، لأن النظام كله مبني على قاعدة "ما يخترع
جرعة دواء"."""
from app.extensions import db
from app.health import health_service
from app.models import Pharmacy
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize


def test_seed_creates_three_vaccine_catalog_entries(app):
    health_service.seed_default_vaccine_catalog()
    items = Pharmacy.query.filter_by(medicine_class="vaccine").all()
    names = {i.name for i in items}
    assert len(items) == 3
    assert any("CDT" in n for n in names)
    assert any("PPR" in n for n in names)
    assert any("قلاعية" in n for n in names)


def test_seed_never_fabricates_dose_or_price(app):
    """أهم فحص: صفر جرعة، صفر سعر — قرار الدكتور حصراً."""
    health_service.seed_default_vaccine_catalog()
    for item in Pharmacy.query.filter_by(medicine_class="vaccine").all():
        assert item.default_dose_ml is None
        assert item.unit_price is None
        assert item.available_qty == 0


def test_seed_idempotent_no_duplicates(app):
    health_service.seed_default_vaccine_catalog()
    health_service.seed_default_vaccine_catalog()
    assert Pharmacy.query.filter_by(medicine_class="vaccine").count() == 3


def test_seed_preserves_existing_farm_pharmacy_data(app):
    """نفس درس بند 289 — idempotent بالاسم، ما يلمس أصناف موجودة أصلاً
    حتى لو كانت مزرعة شغّالة عندها أدوية مسجَّلة مسبقاً."""
    existing = Pharmacy(name="دواء المزرعة الحقيقي", medicine_class="antibiotic", available_qty=50)
    db.session.add(existing)
    db.session.commit()

    health_service.seed_default_vaccine_catalog()

    db.session.refresh(existing)
    assert existing.available_qty == 50
    assert Pharmacy.query.filter_by(medicine_class="vaccine").count() == 3


def test_pharmacy_list_route_triggers_seed(app, logged_in_client):
    resp = logged_in_client.get("/health/pharmacy")
    assert resp.status_code == 200
    assert Pharmacy.query.filter_by(medicine_class="vaccine").count() == 3


def test_kb_answers_vaccination_schedule_question():
    results = search(normalize("متى احصن اغنامي الجديدة، شنو جدول تحصين الماعز"))
    assert results
    assert results[0].code == "vaccination_schedule_reference"
