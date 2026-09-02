"""دفعة ثالثة من طلب "فقعة الشروحات على كل الصفحات": مستودع جديد،
إضافة دواء للصيدلية، محاولة تقريع، جهاز تكاثر، حقنة هرمونية،
دفعة بيع جديدة، الإجراء الجماعي (تسجيل مرض)."""
from tests.factories import make_animal


def test_warehouse_form_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/warehouses/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body


def test_drug_catalog_form_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/health/drug-catalog/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body


def test_lot_form_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/finance/lots/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body


def test_bulk_action_disease_form_has_tip(app, logged_in_client):
    a = make_animal(animal_no="TIP-B3-01")
    resp = logged_in_client.post(
        "/animals/bulk/select",
        data={"bulk_action": "disease", "animal_ids": [a.id]},
    )
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body
