"""بند إضافي 263 (متابعة) — نفس خلل القائمة الجانبية (بند 252/258/262)
بقسم "المعدات": 13 من 15 شاشة كانت غايبة عن _equipment_endpoints."""
from factories import make_equipment


def _drawer_open(html: str) -> bool:
    idx = html.find(">المعدات<")
    assert idx != -1
    details_idx = html.rfind("<details", 0, idx)
    return " open" in html[details_idx:idx]


def test_equipment_drawer_stays_open_on_items_new(app, logged_in_client):
    resp = logged_in_client.get("/equipment/items/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_equipment_drawer_stays_open_on_purchase_new(app, logged_in_client):
    resp = logged_in_client.get("/equipment/purchase")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_equipment_drawer_stays_open_on_assets_list(app, logged_in_client):
    resp = logged_in_client.get("/equipment/assets")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_equipment_drawer_stays_open_on_assets_new(app, logged_in_client):
    resp = logged_in_client.get("/equipment/assets/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_equipment_drawer_stays_open_on_utilities_list(app, logged_in_client):
    resp = logged_in_client.get("/equipment/utilities")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_equipment_drawer_stays_open_on_utilities_new(app, logged_in_client):
    resp = logged_in_client.get("/equipment/utilities/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_equipment_drawer_stays_open_on_items_edit(app, logged_in_client):
    item = make_equipment()
    resp = logged_in_client.get(f"/equipment/items/{item.id}/edit")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())
