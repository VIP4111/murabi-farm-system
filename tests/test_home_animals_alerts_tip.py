"""طلب صريح: "زر الحيونات في الرايسيه يعرض فقعه برقم ٢ ... اذا دخلت
المرحله يطلع عندي ثلاث متطلبات ناقصه. المطلوب اضافة فقعه تبين انواقص"
— المستخدم لاحظ إن رقم التنبيهات بالرئيسية ("٢") مختلف عن "المتطلبات
الناقصة" بصفحة دورة الإنتاج ("٣") — نظامان منفصلان فعلياً. أضفنا فقعة
شرح توضّح الفرق بدل ما يظن إنه نفس الرقم."""
from datetime import date

from app.extensions import db
from tests.factories import make_animal


def test_home_shows_tip_next_to_animals_alerts_badge(app, logged_in_client):
    with app.app_context():
        from app.models.health import Disease
        a = make_animal(animal_no="TIP-HOME-01")
        d = Disease(animal_id=a.id, disease_name="مرض اختبار الفقعة", date=date.today(), status="active")
        db.session.add(d)
        db.session.commit()
    resp = logged_in_client.get("/")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_home_has_no_tip_when_no_alerts(app, logged_in_client):
    resp = logged_in_client.get("/")
    body = resp.data.decode()
    assert resp.status_code == 200
    # ما فيه تنبيهات — الفقعة الشرطية ما لازم تظهر (بدون ما نمنع فقعات
    # ثانية بالصفحة لو أُضيفت لاحقاً بمكان ثاني)
    assert 'إجمالي تنبيهات كل الحيوانات مجتمعة' not in body
