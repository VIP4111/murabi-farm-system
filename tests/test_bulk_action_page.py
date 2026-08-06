"""اختبارات فصل "سجل الحيوانات" (تصفح عادي) عن "الإجراء الجماعي"
(بند إضافي 132) — نقلنا شريط التأشير الجماعي وعمود المربعات من سجل
الحيوانات لشاشة مستقلة مربوطة بالقائمة الجانبية، وأضفنا خيار "استقبال
دفعة جديدة" داخل قائمة الإجراءات نفسها بدل الزر المنفصل السابق."""
from factories import make_animal


def test_animals_list_has_no_bulk_checkboxes(logged_in_client):
    make_animal(animal_no="BX-01")
    resp = logged_in_client.get("/animals")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "animalChk" not in body
    assert "bulk_action" not in body
    assert "استقبال دفعة جديدة" not in body
    assert "شراء دفعة جديدة" not in body


def test_animals_bulk_home_has_checkboxes_and_new_batch_option(logged_in_client):
    make_animal(animal_no="BX-02")
    resp = logged_in_client.get("/animals/bulk")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "animalChk" in body
    assert 'name="bulk_action"' in body
    assert 'value="new_batch"' in body
    assert "استقبال دفعة جديدة" in body
    assert "متابعة الحجر الصحي" in body


def test_bulk_action_bar_shows_even_with_no_animals(logged_in_client):
    resp = logged_in_client.get("/animals/bulk")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'value="new_batch"' in body


def test_new_batch_action_redirects_to_bulk_purchase_form(logged_in_client):
    resp = logged_in_client.post("/animals/bulk/select", data={"bulk_action": "new_batch"})
    assert resp.status_code == 302
    assert "/animals/bulk-purchase" in resp.headers["Location"]


def test_bulk_select_missing_animals_redirects_to_bulk_home(logged_in_client):
    resp = logged_in_client.post("/animals/bulk/select", data={"bulk_action": "weight"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/animals/bulk")


def test_sidebar_link_points_to_bulk_home(logged_in_client):
    resp = logged_in_client.get("/animals")
    body = resp.get_data(as_text=True)
    assert "الإجراء الجماعي" in body
    assert "/animals/bulk" in body
