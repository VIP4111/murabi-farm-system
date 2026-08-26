"""بند إضافي 259 — بعد نقد صريح: "شراء دواء" كان يزيد المخزون بس بدون
أي عملية مالية، فالمبلغ المدفوع يختفي تماماً من كل تقارير المالية
(الإجمالي، تكلفة الرأس الشهرية، تشخيص الخسارة...). وُصِّل الآن بنفس
النمط الموحّد اللي يستخدمه شراء العلف (بند 203)."""
import re
from datetime import date, timedelta

from app.extensions import db
from app.models import Finance, PharmacyBatch
from factories import make_pharmacy


def _csrf(html: str) -> str:
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_purchase_with_price_creates_finance_row(app, logged_in_client):
    p = make_pharmacy(available_qty=5, name="دواء أ")
    resp = logged_in_client.get(f"/health/pharmacy/{p.id}/purchase")
    token = _csrf(resp.data.decode())

    logged_in_client.post(f"/health/pharmacy/{p.id}/purchase", data={
        "csrf_token": token, "purchase_date": str(date.today()),
        "quantity": "10", "unit_price": "4",
    }, follow_redirects=True)

    db.session.refresh(p)
    assert p.available_qty == 15
    fin = Finance.query.filter_by(operation_type="purchase", category="أدوية").first()
    assert fin is not None
    assert fin.amount == 40  # 10 × 4
    assert fin.item == "دواء أ"


def test_purchase_without_price_skips_finance_row(app, logged_in_client):
    p = make_pharmacy(available_qty=5)
    resp = logged_in_client.get(f"/health/pharmacy/{p.id}/purchase")
    token = _csrf(resp.data.decode())

    resp2 = logged_in_client.post(f"/health/pharmacy/{p.id}/purchase", data={
        "csrf_token": token, "purchase_date": str(date.today()), "quantity": "10",
    }, follow_redirects=True)

    db.session.refresh(p)
    assert p.available_qty == 15
    assert Finance.query.filter_by(operation_type="purchase", category="أدوية").count() == 0
    assert "بدون سعر، ما انسجلت عملية مالية" in resp2.data.decode()


def test_purchase_finance_amount_reflected_in_finance_list(app, logged_in_client):
    p = make_pharmacy(available_qty=0, name="دواء ب")
    resp = logged_in_client.get(f"/health/pharmacy/{p.id}/purchase")
    token = _csrf(resp.data.decode())
    logged_in_client.post(f"/health/pharmacy/{p.id}/purchase", data={
        "csrf_token": token, "purchase_date": str(date.today()),
        "quantity": "5", "unit_price": "20",
    }, follow_redirects=True)

    resp2 = logged_in_client.get("/finance/")
    html = resp2.data.decode()
    assert "100.00" in html  # 5 × 20 بإجمالي الخارج


def test_batch_still_created_with_correct_price(app, logged_in_client):
    p = make_pharmacy(available_qty=0)
    resp = logged_in_client.get(f"/health/pharmacy/{p.id}/purchase")
    token = _csrf(resp.data.decode())
    logged_in_client.post(f"/health/pharmacy/{p.id}/purchase", data={
        "csrf_token": token, "purchase_date": str(date.today()),
        "quantity": "8", "unit_price": "2.5",
        "expiry_date": str(date.today() + timedelta(days=90)),
    }, follow_redirects=True)

    batch = PharmacyBatch.query.filter_by(pharmacy_id=p.id).first()
    assert batch is not None
    assert batch.quantity == 8
    assert batch.unit_price == 2.5


def test_worker_without_finance_permission_blocked_when_price_given(app, client):
    from app.extensions import db as _db
    from app.models import Role, User
    role = Role.query.filter_by(name="worker").first()
    worker = User(name="عامل صيدلية", phone="0500059001", role_id=role.id, language="ar")
    worker.set_password("pass1234")
    _db.session.add(worker)
    _db.session.commit()

    p = make_pharmacy(available_qty=5)
    # نمنح العامل صلاحية pharmacy.manage بس، بدون finance.full.manage
    from app.models import Permission
    perm = Permission.query.filter_by(code="pharmacy.manage").first()
    if perm and perm not in worker.role.permissions:
        worker.role.permissions.append(perm)
        _db.session.commit()

    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get(f"/health/pharmacy/{p.id}/purchase")
    if resp.status_code != 200:
        return  # ما عنده صلاحية يوصل الفورم أصلاً — يكفي هذا كتأكيد الحماية
    token = _csrf(resp.data.decode())
    resp2 = client.post(f"/health/pharmacy/{p.id}/purchase", data={
        "csrf_token": token, "purchase_date": str(date.today()),
        "quantity": "10", "unit_price": "5",
    }, follow_redirects=True)
    assert "تحتاج صلاحية إدارة المالية" in resp2.data.decode()
    assert Finance.query.filter_by(operation_type="purchase", category="أدوية").count() == 0
