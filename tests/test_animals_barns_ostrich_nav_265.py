"""بند إضافي 265 — متابعة المراجعة المنهجية (بند 258/262/263/264):
الحيوانات، الحظائر، والنعام (باقي أعضاء _animals_endpoints اللي ما
راجعتها ببند 264). الجانب المالي لشراء الرؤوس (فردي/دفعة) موصول صح
أصلاً من قبل هذا البند — كلاهما يمر بـ`create_animal()` الموحّدة."""
from factories import make_animal, make_barn


def _drawer_open(html: str) -> bool:
    idx = html.find(">الحيوانات<")
    assert idx != -1
    details_idx = html.rfind("<details", 0, idx)
    return " open" in html[details_idx:idx]


def test_animals_drawer_stays_open_on_animals_new(app, logged_in_client):
    resp = logged_in_client.get("/animals/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_animals_bulk_purchase(app, logged_in_client):
    resp = logged_in_client.get("/animals/bulk-purchase")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_animal_detail(app, logged_in_client):
    animal = make_animal(animal_no="NAV-01")
    resp = logged_in_client.get(f"/animals/{animal.id}")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_animal_edit(app, logged_in_client):
    animal = make_animal(animal_no="NAV-02")
    resp = logged_in_client.get(f"/animals/{animal.id}/edit")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_animal_workflow(app, logged_in_client):
    animal = make_animal(animal_no="NAV-03")
    resp = logged_in_client.get(f"/animals/{animal.id}/workflow")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_barns_new(app, logged_in_client):
    resp = logged_in_client.get("/barns/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_barns_edit(app, logged_in_client):
    barn = make_barn()
    resp = logged_in_client.get(f"/barns/{barn.id}/edit")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_smart_sale_report(app, logged_in_client):
    resp = logged_in_client.get("/animals/smart-sale")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_ostrich_eggs_new(app, logged_in_client):
    resp = logged_in_client.get("/ostrich/eggs/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_ostrich_incubators_list(app, logged_in_client):
    resp = logged_in_client.get("/ostrich/incubators")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_ostrich_incubators_new(app, logged_in_client):
    resp = logged_in_client.get("/ostrich/incubators/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())
