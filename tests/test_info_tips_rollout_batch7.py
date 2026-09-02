"""دفعة سابعة من طلب "فقعة الشروحات على كل الصفحات": شاشة دورة
الإنتاج (workflow) — تفسير "قرار المصير"."""
from tests.factories import make_animal


def test_animal_workflow_has_tip(app, logged_in_client):
    a = make_animal(animal_no="TIP-B7-01")
    resp = logged_in_client.get(f"/animals/{a.id}/workflow")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body
