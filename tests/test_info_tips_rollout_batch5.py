"""دفعة خامسة من طلب "فقعة الشروحات على كل الصفحات" — أول توسّع
لشاشات القوائم/التقارير (مو فقط نماذج إدخال): سجل الحيوانات
(عمود "المرحلة" و"فترة سحب")، رادار المناخ (THI)، تقرير FCR،
التحليل المالي ونقطة التعادل (الهامش)."""


def test_animals_list_has_tips(app, logged_in_client):
    resp = logged_in_client.get("/animals")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 2


def test_climate_dashboard_has_tip(app, logged_in_client):
    from datetime import date
    from app.extensions import db
    from app.models import FarmSettings
    from tests.factories import make_weather_reading

    with app.app_context():
        settings = FarmSettings.get()
        settings.farm_latitude = 24.7
        settings.farm_longitude = 46.7
        db.session.commit()
        make_weather_reading(date.today())

    resp = logged_in_client.get("/climate/")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body


def test_break_even_report_has_tip(app, logged_in_client):
    resp = logged_in_client.get("/finance/break-even-report")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body
