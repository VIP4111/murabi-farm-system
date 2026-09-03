"""طلب صريح: "الحيونات لم تضيف فقعات اضف كميه كبيره" — دفعة كبيرة
مركَّزة على شاشتي "تفاصيل الرأس" و"دورة الإنتاج" تحديداً (شاشات
"الحيوانات" الأهم اللي كانت ناقصة فقعات كافية)."""
from tests.factories import make_animal


def test_animal_detail_has_many_tips(app, logged_in_client):
    with app.app_context():
        a = make_animal(animal_no="TIP-BIG-01")
        animal_id = a.id
    resp = logged_in_client.get(f"/animals/{animal_id}")
    body = resp.data.decode()
    assert resp.status_code == 200
    # كانت فقعة وحدة بس قبل هالدفعة — الآن لازم ٦ على الأقل (فقعة واحدة
    # شرطية على وجود أم مسجَّلة، فما تظهر لهذا الرأس التجريبي بدون أم).
    assert body.count('class="info-tip"') >= 6


def test_animal_workflow_has_tips(app, logged_in_client):
    with app.app_context():
        a = make_animal(animal_no="TIP-BIG-02")
        animal_id = a.id
    resp = logged_in_client.get(f"/animals/{animal_id}/workflow")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 2
