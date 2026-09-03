"""طلب صريح متكرر: "أكمل فقعات" — استكمال فقعات الشرح لشاشات الرواتب
(الفرق بين مسودة/تأكيد نهائي، وحالات الراتب بشاشة "رواتب الشهر")."""


def test_payroll_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/team/payroll")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 2


def test_payroll_prepare_has_tip(app, logged_in_client, owner):
    resp = logged_in_client.get(f"/team/payroll/{owner.id}/prepare")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body
