"""بند إضافي 141 — إجراء جماعي جديد "تحديد الغرض" (تربية/تسمين/بيع).
طلبك: لاحظت ما فيه طريقة تسمّن مجموعة حيوانات دفعة وحدة — لازم تعدّل
كل رأس لحاله. هذا يسدّها عبر "الإجراء الجماعي" الموجود أصلاً."""
from app.extensions import db
from factories import make_animal


def test_purpose_option_appears_in_bulk_dropdown(logged_in_client):
    resp = logged_in_client.get("/animals/bulk")
    body = resp.get_data(as_text=True)
    assert 'value="purpose"' in body
    assert "تحديد الغرض جماعياً" in body


def test_bulk_purpose_route_sets_purpose_and_animal_appears_in_fattening_tab(logged_in_client):
    a1 = make_animal(animal_no="BPUR-01")
    a2 = make_animal(animal_no="BPUR-02")

    resp = logged_in_client.post("/animals/bulk/apply/purpose", data={
        "animal_ids": [str(a1.id), str(a2.id)], "purpose": "تسمين",
    }, follow_redirects=True)
    assert resp.status_code == 200

    db.session.refresh(a1)
    db.session.refresh(a2)
    assert a1.purpose == "تسمين"
    assert a2.purpose == "تسمين"

    fattening_resp = logged_in_client.get("/animals?filter=fattening")
    assert "BPUR-01" in fattening_resp.get_data(as_text=True)
