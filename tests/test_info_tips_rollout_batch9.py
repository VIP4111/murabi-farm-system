"""طلب متكرر: "اكمل دفعه اكبر" — دفعة كبيرة ثانية من فقعات الشرح
تغطي: التنبيهات، مركز الطبيب، الأمراض، نواقص الصيدلية، دفعات البيع،
التقريع، السونار، مستودع المعدات، أعضاء الفريق، سجل النعام، وصفات
العلف."""


def test_alerts_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/alerts")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_health_dashboard_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/health/dashboard")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_diseases_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/health/diseases")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 2


def test_pharmacy_shortages_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/health/pharmacy/shortages")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_lots_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/finance/lots")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_matings_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/repro/matings")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_sonar_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/repro/sonar")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 2


def test_equipment_items_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/equipment/items")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_team_members_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/team/members")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_eggs_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/ostrich/eggs")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 2


def test_rations_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/feed/rations")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 3
