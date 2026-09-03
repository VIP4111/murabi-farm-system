"""طلب "اكمل" — دفعة خامسة من فقعات الشرح تغطي: صلاحيات الدور،
تفاصيل دفعة استقبال قطيع جديد، موازِن العليقة التلقائي، حاسبة الاحتياج
اليومي."""
from datetime import date

from app.extensions import db
from app.models.role import Role
from app.models.animal_batch import AnimalBatch


def test_role_edit_has_tip(app, logged_in_client):
    with app.app_context():
        role = Role.query.filter_by(name="worker").first()
        role_id = role.id
    resp = logged_in_client.get(f"/settings/roles/{role_id}/edit")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_batch_detail_has_tip(app, logged_in_client):
    with app.app_context():
        b = AnimalBatch(batch_no="TIP-B-01", source="purchase", arrival_date=date.today())
        db.session.add(b)
        db.session.commit()
        batch_id = b.id
    resp = logged_in_client.get(f"/batches/{batch_id}")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_feed_optimizer_page_loads(app, logged_in_client):
    # tip بهذي الشاشة يظهر فقط داخل قسم النتيجة (بعد POST بوزن/حيوان)
    # — هذا الاختبار يتأكد إن الصفحة نفسها ما انهارت بإضافة الفقعة.
    resp = logged_in_client.get("/feed/optimizer")
    assert resp.status_code == 200


def test_feed_calculator_has_tip_after_result(app, logged_in_client):
    resp = logged_in_client.post("/feed/calculator", data={"weight": "40"})
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1
