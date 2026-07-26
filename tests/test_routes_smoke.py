"""اختبارات دخان (Smoke) على مستوى Routes — تتأكد إن الشاشات الأساسية
والجديدة (بند 17 و46) تُقدَّم فعلياً بدون كسر (200) وإن حماية الصلاحيات
شغّالة (403 لدور بدون الصلاحية المطلوبة)."""
from factories import make_animal, make_barn


def _login(client, phone, password="pass1234"):
    return client.post("/login", data={"phone": phone, "password": password}, follow_redirects=True)


def test_worker_without_permission_gets_403_on_animals_list(app, client, worker):
    _login(client, worker.phone)
    resp = client.get("/animals")
    assert resp.status_code == 403


def test_owner_can_view_animals_list(app, logged_in_client):
    resp = logged_in_client.get("/animals")
    assert resp.status_code == 200


def test_owner_can_view_animal_edit_form(app, logged_in_client):
    animal = make_animal(animal_no="ROUTE-01")
    resp = logged_in_client.get(f"/animals/{animal.id}/edit")
    assert resp.status_code == 200
    assert "ROUTE-01".encode() in resp.data


def test_owner_can_view_bulk_purchase_form(app, logged_in_client):
    resp = logged_in_client.get("/animals/bulk-purchase")
    assert resp.status_code == 200


def test_owner_can_view_monthly_cost_report(app, logged_in_client):
    resp = logged_in_client.get("/finance/monthly-cost-report")
    assert resp.status_code == 200


def test_owner_can_view_feed_movement_form(app, logged_in_client):
    resp = logged_in_client.get("/feed/movements/new")
    assert resp.status_code == 200


def test_bulk_select_route_renders_isolation_form(app, logged_in_client):
    animal = make_animal(animal_no="ROUTE-02")
    resp = logged_in_client.post(
        "/animals/bulk/select",
        data={"animal_ids": [str(animal.id)], "bulk_action": "isolation"},
    )
    assert resp.status_code == 200
    assert "عزل جماعي".encode() in resp.data


def test_worker_report_form_scoped_to_assigned_barn(app, client, worker):
    barn = make_barn(barn_no="SCOPED", responsible_worker_id=worker.id)
    other_barn = make_barn(barn_no="NOT-SCOPED")
    make_animal(animal_no="SCOPED-A", barn_id=barn.id)
    make_animal(animal_no="NOT-SCOPED-A", barn_id=other_barn.id)

    _login(client, worker.phone)
    resp = client.get("/team/worker/report/health")
    assert resp.status_code == 200
    assert b"SCOPED-A" in resp.data
    assert b"NOT-SCOPED-A" not in resp.data


def test_animals_list_barn_filter_scopes_to_one_barn(app, logged_in_client):
    barn1 = make_barn(barn_no="BF-1", barn_name="حظيرة أولى")
    barn2 = make_barn(barn_no="BF-2", barn_name="حظيرة ثانية")
    make_animal(animal_no="BF-A1", barn_id=barn1.id)
    make_animal(animal_no="BF-A2", barn_id=barn2.id)

    resp = logged_in_client.get(f"/animals?barn_id={barn1.id}")
    assert resp.status_code == 200
    assert b"BF-A1" in resp.data
    assert b"BF-A2" not in resp.data


def test_worker_report_submission_outside_scope_rejected(app, client, worker):
    make_barn(barn_no="SCOPED2", responsible_worker_id=worker.id)
    other_barn = make_barn(barn_no="NOT-SCOPED2")
    outside_animal = make_animal(animal_no="OUTSIDE-A", barn_id=other_barn.id)

    _login(client, worker.phone)
    resp = client.post(
        "/team/worker/report/health",
        data={"description": "بلاغ اختبار", "animal_id": str(outside_animal.id)},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "خارج نطاق".encode() in resp.data


def test_owner_can_view_climate_dashboard_unconfigured(app, logged_in_client):
    """بدون موقع مضبوط — الشاشة تُقدَّم بأمان (200) وما تحاول تتصل
    بالإنترنت (بند إضافي 49)."""
    resp = logged_in_client.get("/climate/")
    assert resp.status_code == 200
    assert "غير مضبوط".encode() in resp.data


def test_owner_can_view_climate_settings(app, logged_in_client):
    resp = logged_in_client.get("/climate/settings")
    assert resp.status_code == 200


def test_worker_without_permission_gets_403_on_climate_dashboard(app, client, worker):
    _login(client, worker.phone)
    resp = client.get("/climate/")
    assert resp.status_code == 403
