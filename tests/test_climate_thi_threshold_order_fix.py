"""فحص عميق — قسم المناخ: `climate.settings` كانت تحفظ عتبات مؤشر
الإجهاد الحراري (mild/moderate/severe/emergency) بدون أي تحقق من
ترتيبها التصاعدي — `classify_stress_level` مبنية بالكامل على افتراض
إنها تصاعدية (سلسلة if/elif). عتبة بترتيب خاطئ (خطأ كتابة) كانت
تكسر تصنيف الإجهاد الحراري كله بصمت للمزرعة."""
from app.extensions import db
from app.models import FarmSettings


def test_out_of_order_thresholds_rejected(app, logged_in_client):
    fs = FarmSettings.get()
    original_moderate = fs.thi_moderate

    resp = logged_in_client.post("/climate/settings", data={
        "farm_latitude": "24.7", "farm_longitude": "46.7",
        "thi_mild": "80", "thi_moderate": "70",  # عكس الترتيب الصحيح
        "thi_severe": "89", "thi_emergency": "98",
    }, follow_redirects=True)
    assert resp.status_code == 200

    db.session.refresh(fs)
    assert fs.thi_moderate == original_moderate, "عتبات بترتيب خاطئ انحفظت رغم إنها تكسر التصنيف"
    assert fs.farm_latitude is None, "الإحداثيات انحفظت رغم فشل تحقق العتبات — يفترض رفض العملية كاملة"


def test_valid_ascending_thresholds_still_accepted(app, logged_in_client):
    resp = logged_in_client.post("/climate/settings", data={
        "farm_latitude": "24.7", "farm_longitude": "46.7",
        "thi_mild": "72", "thi_moderate": "79",
        "thi_severe": "89", "thi_emergency": "98",
    }, follow_redirects=True)
    assert resp.status_code == 200

    fs = FarmSettings.get()
    assert fs.thi_mild == 72
    assert fs.thi_moderate == 79
    assert fs.farm_latitude == 24.7
