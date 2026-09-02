"""دفعة رابعة من طلب "فقعة الشروحات على كل الصفحات": تعديل عضو،
تسجيل بيضة نعام، أصل جديد، تسجيل قراءة استهلاك."""


def test_member_edit_form_has_tip(app, logged_in_client, owner):
    resp = logged_in_client.get(f"/team/members/{owner.id}/edit")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body


def test_egg_form_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/ostrich/eggs/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body


def test_asset_form_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/equipment/assets/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body


def test_utility_form_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/equipment/utilities/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body
