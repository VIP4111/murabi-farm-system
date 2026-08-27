"""بند إضافي 263 — بعد نقد صريح على قسم "المعدات والصيانة": تكلفة
صيانة الأصل (AssetMaintenanceLog.cost) وفاتورة الكهرباء/الماء
(UtilityReading.cost) كانتا تُخزَّنان بس، بدون أي أثر بسجل "المالية"
العام — نفس فئة مشكلة بند 261 (زيارة بيطرية/علاج مرض). مصاريف حقيقية
جديدة (مو استهلاك مخزون مدفوع من قبل)، فربطها مباشر بدون قلق احتساب
مزدوج."""
import re
from datetime import date

from app.extensions import db
from app.models import Asset, Finance


def _csrf(html: str) -> str:
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def _make_asset(name="مولّد اختبار"):
    a = Asset(name=name, category="generator")
    db.session.add(a)
    db.session.commit()
    return a


def test_maintenance_with_cost_creates_finance_row(app, logged_in_client):
    asset = _make_asset()
    resp = logged_in_client.get(f"/equipment/assets/{asset.id}/maintenance")
    token = _csrf(resp.data.decode())
    logged_in_client.post(f"/equipment/assets/{asset.id}/maintenance", data={
        "csrf_token": token, "date": str(date.today()), "cost": "300", "notes": "تغيير زيت",
    }, follow_redirects=True)

    fin = Finance.query.filter_by(category="صيانة معدات").first()
    assert fin is not None
    assert fin.amount == 300
    assert fin.item == "مولّد اختبار"

    from app.models import AssetMaintenanceLog
    log = AssetMaintenanceLog.query.filter_by(asset_id=asset.id).first()
    assert log.finance_id == fin.id


def test_maintenance_without_cost_creates_no_finance_row(app, logged_in_client):
    asset = _make_asset()
    resp = logged_in_client.get(f"/equipment/assets/{asset.id}/maintenance")
    token = _csrf(resp.data.decode())
    logged_in_client.post(f"/equipment/assets/{asset.id}/maintenance", data={
        "csrf_token": token, "date": str(date.today()), "notes": "فحص روتيني بدون تكلفة",
    }, follow_redirects=True)

    assert Finance.query.filter_by(category="صيانة معدات").count() == 0


def test_utility_reading_with_cost_creates_finance_row(app, logged_in_client):
    resp = logged_in_client.get("/equipment/utilities/new")
    token = _csrf(resp.data.decode())
    logged_in_client.post("/equipment/utilities/new", data={
        "csrf_token": token, "utility_type": "electricity", "date": str(date.today()),
        "quantity": "500", "unit": "kWh", "cost": "450",
    }, follow_redirects=True)

    fin = Finance.query.filter_by(category="فاتورة كهرباء").first()
    assert fin is not None
    assert fin.amount == 450

    from app.models.asset import UtilityReading
    reading = UtilityReading.query.filter_by(utility_type="electricity").first()
    assert reading.finance_id == fin.id


def test_water_utility_uses_correct_category_label(app, logged_in_client):
    resp = logged_in_client.get("/equipment/utilities/new")
    token = _csrf(resp.data.decode())
    logged_in_client.post("/equipment/utilities/new", data={
        "csrf_token": token, "utility_type": "water", "date": str(date.today()),
        "quantity": "20", "unit": "m3", "cost": "80",
    }, follow_redirects=True)

    assert Finance.query.filter_by(category="فاتورة ماء", amount=80).count() == 1


def test_utility_reading_without_cost_creates_no_finance_row(app, logged_in_client):
    resp = logged_in_client.get("/equipment/utilities/new")
    token = _csrf(resp.data.decode())
    logged_in_client.post("/equipment/utilities/new", data={
        "csrf_token": token, "utility_type": "water", "date": str(date.today()),
        "quantity": "15", "unit": "m3",
    }, follow_redirects=True)

    assert Finance.query.filter_by(category="فاتورة ماء").count() == 0


def test_maintenance_cost_reflected_in_finance_totals(app, logged_in_client):
    asset = _make_asset()
    resp = logged_in_client.get(f"/equipment/assets/{asset.id}/maintenance")
    token = _csrf(resp.data.decode())
    logged_in_client.post(f"/equipment/assets/{asset.id}/maintenance", data={
        "csrf_token": token, "date": str(date.today()), "cost": "500",
    }, follow_redirects=True)

    resp2 = logged_in_client.get("/finance/")
    assert "500.00" in resp2.data.decode()
