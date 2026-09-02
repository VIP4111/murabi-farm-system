"""دفعة ثانية من طلب "فقعة الشروحات على كل الصفحات": تسجيل تطعيم،
تسجيل زيارة بيطرية، وصفة علف جديدة، خطة تغذية جديدة، تشخيص حمل جديد،
فحص سونار جديد، صنف معدات جديد."""
from tests.factories import make_animal


def test_vaccination_form_has_tips_and_collapsed_override(app, logged_in_client):
    resp = logged_in_client.get("/health/vaccinations/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body
    assert '<details class="drawer-group">' in body


def test_vet_visit_form_has_tips_and_collapsed_override(app, logged_in_client):
    resp = logged_in_client.get("/health/vet-visits/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body
    assert '<details class="drawer-group">' in body


def test_ration_form_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/feed/rations/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 2


def test_barn_plan_form_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/feed/barn-plans/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 2


def test_pregnancy_form_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/repro/pregnancies/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body


def test_sonar_form_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/repro/sonar/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body


def test_equipment_item_form_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/equipment/items/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body
