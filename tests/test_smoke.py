def test_app_boots(app):
    assert app.testing


def test_home_requires_login(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302)


def test_owner_can_log_in(logged_in_client):
    resp = logged_in_client.get("/")
    assert resp.status_code == 200
