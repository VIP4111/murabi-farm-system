"""طلب "اكمل بنفس المستوا" — دفعة سابعة: وصفات العلف (تفاصيل)، تقرير
علف الحظيرة، مسمّى وظيفي جديد."""
from app.extensions import db
from tests.factories import make_feed


def test_ration_detail_has_tip(app, logged_in_client):
    with app.app_context():
        from app.models import FeedRation
        from app.models.feed import FeedRationItem
        feed = make_feed(name="مكوّن اختبار الفقعات", protein_percent=16)
        r = FeedRation(name="وصفة اختبار الفقعات")
        db.session.add(r)
        db.session.flush()
        db.session.add(FeedRationItem(ration_id=r.id, feed_id=feed.id, percent=100))
        db.session.commit()
        ration_id = r.id
    resp = logged_in_client.get(f"/feed/rations/{ration_id}")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_barn_report_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/feed/barn-report")
    body = resp.data.decode()
    assert resp.status_code == 200


def test_role_new_form_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/settings/roles/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1
