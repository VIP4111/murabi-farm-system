"""حذف حظيرة (بند إضافي، طلبك الصريح: "زر حذف حظيرة يطلع شرط اذا كان
يوجد حيوانات داخل الحظيرة يطلع تنبيه نقل الحيوانات... بعد اتمام النقل
تستطيع الحذف") — قبل هذا البند ما فيه أي مسار حذف حظيرة إطلاقاً."""
from app.extensions import db
from app.models import Barn
from tests.factories import make_barn, make_animal


def test_delete_empty_barn_succeeds(app, logged_in_client):
    barn = make_barn(barn_no="DEL-01")
    resp = logged_in_client.post(f"/barns/{barn.id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert Barn.query.get(barn.id) is None


def test_delete_barn_with_animals_blocked_and_redirects_to_bulk_move(app, logged_in_client):
    barn = make_barn(barn_no="DEL-02")
    make_animal(animal_no="ADEL-01", barn_id=barn.id)
    resp = logged_in_client.post(f"/barns/{barn.id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    # الحظيرة ما تحذفت — لسا موجودة
    assert Barn.query.get(barn.id) is not None
    # وصلت لشاشة الإجراء الجماعي مفلترة على نفس الحظيرة (تقدر تنقل الرؤوس منها)
    assert f"barn_id={barn.id}".encode() in resp.request.url.encode() or str(barn.id).encode() in resp.data


def test_delete_barn_after_moving_animals_out_succeeds(app, logged_in_client):
    barn = make_barn(barn_no="DEL-03")
    other = make_barn(barn_no="DEL-04")
    animal = make_animal(animal_no="ADEL-02", barn_id=barn.id)
    # ينقل الرأس لحظيرة ثانية (نفس مسار "نقل حظيرة جماعي" الموجود)
    animal.barn_id = other.id
    db.session.commit()

    resp = logged_in_client.post(f"/barns/{barn.id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert Barn.query.get(barn.id) is None
