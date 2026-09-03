"""طلب صريح متكرر: "تعبتني معاك ليه ماسك ٣ ارفع العدد" — دفعة أكبر بكثير
من فقعات الشرح دفعة وحدة (بدل ٣-٤ بكل مرة) تغطي: التطعيمات، الزيارات
البيطرية، برامج الشياع، تشخيص الحمل، الأصول والصيانة، الجرد، المالية،
الرواتب، الحاضنات، تقييم أداء الفحول."""


def test_vaccinations_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/health/vaccinations")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_vet_visits_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/health/vet-visits")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_repro_programs_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/repro/programs")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_repro_pregnancies_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/repro/pregnancies")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 2


def test_equipment_assets_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/equipment/assets")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_inventory_counts_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/warehouses/inventory-counts")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 2


def test_finance_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/finance/")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 2


def test_salaries_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/team/salaries")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_incubators_list_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/ostrich/incubators")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_sires_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/repro/sires")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 3
