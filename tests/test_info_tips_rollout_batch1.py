"""طلبك المباشر: "المطلوب الان اضافة فقعة الشروحات على كل الصفحات" —
دفعة أولى (باقي الشاشات تُغطّى تدريجياً بدفعات لاحقة): عضو فريق جديد،
عملية مالية جديدة، وإعدادات المزرعة."""


def test_member_form_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/team/members/new")
    assert resp.status_code == 200
    assert resp.data.decode().count('class="info-tip"') >= 2


def test_finance_form_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/finance/new")
    assert resp.status_code == 200
    assert resp.data.decode().count('class="info-tip"') >= 2


def test_settings_page_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/settings")
    assert resp.status_code == 200
    assert resp.data.decode().count('class="info-tip"') >= 3
