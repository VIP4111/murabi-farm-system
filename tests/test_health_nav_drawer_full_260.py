"""بند إضافي 260 — إكمال إصلاح بند 258 لبقية شاشات "الصحة" الفعلية
(القابلة للفتح مباشرة عبر GET). القائمة _health_endpoints صارت تغطي
كل الـ42 راوت الفعلي بالقسم."""
from app.extensions import db
from factories import make_disease_type, make_animal


def _drawer_open(html: str) -> bool:
    # بند إضافي 318 — عنوان المجموعة صار "الصحة والتحصين" بعد إعادة
    # هيكلة القائمة الجانبية لـ5 مراكز رئيسية (نفس الرابط/الصلاحية،
    # تسمية فقط).
    idx = html.find(">الصحة والتحصين<")
    assert idx != -1
    details_idx = html.rfind("<details", 0, idx)
    return " open" in html[details_idx:idx]


def test_usage_routes_new(app, logged_in_client):
    resp = logged_in_client.get("/health/usage-routes/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_drug_catalog_new(app, logged_in_client):
    resp = logged_in_client.get("/health/drug-catalog/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_disease_types_list(app, logged_in_client):
    resp = logged_in_client.get("/health/disease-types")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_disease_types_new(app, logged_in_client):
    resp = logged_in_client.get("/health/disease-types/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_disease_type_detail(app, logged_in_client):
    dt = make_disease_type()
    resp = logged_in_client.get(f"/health/disease-types/{dt.id}")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_symptoms_list(app, logged_in_client):
    resp = logged_in_client.get("/health/symptoms")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_symptoms_new(app, logged_in_client):
    resp = logged_in_client.get("/health/symptoms/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_link_wizard(app, logged_in_client):
    resp = logged_in_client.get("/health/disease-types/link-wizard")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_emergency_symptoms_list(app, logged_in_client):
    resp = logged_in_client.get("/health/emergency-symptoms")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_doctors_new(app, logged_in_client):
    resp = logged_in_client.get("/health/doctors/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_vet_visits_new(app, logged_in_client):
    resp = logged_in_client.get("/health/vet-visits/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_diseases_new_simple(app, logged_in_client):
    resp = logged_in_client.get("/health/diseases/new-simple")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_diseases_new(app, logged_in_client):
    resp = logged_in_client.get("/health/diseases/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_vaccinations_new(app, logged_in_client):
    resp = logged_in_client.get("/health/vaccinations/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_protocols_new(app, logged_in_client):
    resp = logged_in_client.get("/health/protocols/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_protocols_apply(app, logged_in_client):
    from app.models import TreatmentProtocol
    protocol = TreatmentProtocol(name="بروتوكول اختبار")
    db.session.add(protocol)
    db.session.commit()
    resp = logged_in_client.get(f"/health/protocols/{protocol.id}/apply")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_vaccination_schedule_new(app, logged_in_client):
    resp = logged_in_client.get("/health/vaccination-schedule/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())
