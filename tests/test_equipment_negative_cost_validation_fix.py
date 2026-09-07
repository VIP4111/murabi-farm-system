"""فحص عميق — قسم المعدات: نفس ثغرة تكلفة الزيارة البيطرية اليدوية —
`record_maintenance_cost`/`record_utility_cost` تتجاوز إنشاء عملية
مالية لو `cost <= 0` بس القيمة السالبة كانت تبقى مخزَّنة مباشرة على
`AssetMaintenanceLog.cost`/`UtilityReading.cost` بصمت."""
from datetime import date

from app.extensions import db
from app.models import Asset, AssetMaintenanceLog, UtilityReading


def test_negative_maintenance_cost_rejected(app, logged_in_client):
    asset = Asset(name="أصل اختبار", category="other")
    db.session.add(asset)
    db.session.commit()

    resp = logged_in_client.post(f"/equipment/assets/{asset.id}/maintenance", data={
        "date": date.today().isoformat(), "cost": "-100", "notes": "اختبار",
    }, follow_redirects=True)
    assert resp.status_code == 200

    assert AssetMaintenanceLog.query.filter_by(asset_id=asset.id).count() == 0, \
        "سجل صيانة بتكلفة سالبة انحفظ رغم إنها غير منطقية"


def test_negative_utility_cost_rejected(app, logged_in_client):
    resp = logged_in_client.post("/equipment/utilities/new", data={
        "date": date.today().isoformat(), "utility_type": "electricity",
        "cost": "-50", "quantity": "10",
    }, follow_redirects=True)
    assert resp.status_code == 200

    assert UtilityReading.query.filter_by(utility_type="electricity", cost=-50).count() == 0, \
        "قراءة فاتورة بتكلفة سالبة انحفظت رغم إنها غير منطقية"


def test_positive_maintenance_cost_still_accepted(app, logged_in_client):
    asset = Asset(name="أصل اختبار ب", category="other")
    db.session.add(asset)
    db.session.commit()

    resp = logged_in_client.post(f"/equipment/assets/{asset.id}/maintenance", data={
        "date": date.today().isoformat(), "cost": "150", "notes": "اختبار",
    }, follow_redirects=True)
    assert resp.status_code == 200

    log = AssetMaintenanceLog.query.filter_by(asset_id=asset.id).first()
    assert log is not None
    assert log.cost == 150
