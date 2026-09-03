"""طلب متكرر: "اكمل" — دفعة ثالثة من فقعات الشرح تغطي: الحيوانات
(بطاقات)، الحظائر، بروتوكولات العلاج، الأعراض (شجرة التشخيص)، تقويم
التحصينات، المستودعات، دفعات استقبال قطيع جديد، المعدات (شخصية)."""


def test_animals_list_simple_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/animals")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_barns_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/barns")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_protocols_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/health/protocols")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_symptoms_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/health/symptoms")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_vaccination_schedule_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/health/vaccination-schedule")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_warehouses_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/warehouses/")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_batches_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/batches/")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_equipment_items_mine_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/equipment/items/mine")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1
