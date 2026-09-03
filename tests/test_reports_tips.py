"""طلب صريح متكرر: "أكمل فقعات" — استكمال فقعات الشرح لمسار "البلاغات"
(صندوق الوارد، بلاغات مستلمة مني، محوّلة لي، وشاشة تفاصيل بلاغ)."""
from app.extensions import db
from app.models import Report


def test_reports_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/team/reports")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 3


def test_report_detail_inbox_actions_have_tip(app, logged_in_client, owner):
    r = Report(reporter_id=owner.id, description="بلاغ اختبار الفقعات", status="new")
    db.session.add(r)
    db.session.commit()

    resp = logged_in_client.get(f"/team/reports/{r.id}")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body
