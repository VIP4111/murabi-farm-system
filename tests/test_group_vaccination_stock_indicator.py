"""اختبار شريط فحص المخزون المباشر بشاشة التحصين الجماعي (بند إضافي 64):
نقطة الـJSON صارت ترجع available_qty/unit — الحساب والتلوين نفسه
جافاسكربت بالمتصفح (يظهر بس، ما يخصم/يرفض شي — السيرفر يبقى الحاسم)."""
from app.extensions import db
from app.models import Pharmacy


def test_dose_rules_json_includes_available_qty_and_unit(app, logged_in_client):
    item = Pharmacy(name="لقاح مخزون 64", medicine_class="vaccine",
                     available_qty=45, unit="مل", status="active")
    db.session.add(item)
    db.session.commit()
    resp = logged_in_client.get(f"/health/pharmacy/{item.id}/dose-rules")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["available_qty"] == 45
    assert data["unit"] == "مل"
