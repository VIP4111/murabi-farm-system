"""اختبارات رادار المناخ والإجهاد الحراري (بند إضافي 49) — THI، جلب
Open-Meteo (مع تزييف requests.get)، وتوليد قوائم التفقد."""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import FarmSettings, Task
from app.climate import climate_service as svc
from factories import make_barn, make_weather_reading


def test_calculate_thi_known_value(app):
    assert svc.calculate_thi(35, 30) == 80.8


def test_classify_stress_level_boundaries(app):
    fs = FarmSettings.get()
    assert svc.classify_stress_level(71.9, fs) == "normal"
    assert svc.classify_stress_level(72.0, fs) == "mild"
    assert svc.classify_stress_level(79.0, fs) == "moderate"
    assert svc.classify_stress_level(89.0, fs) == "severe"
    assert svc.classify_stress_level(98.0, fs) == "emergency"


def test_is_configured_false_without_location(app):
    assert svc.is_configured() is False


def test_get_forecast_skips_network_when_not_configured(app, monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("ما يفترض يتصل بالإنترنت بدون موقع مضبوط")
    monkeypatch.setattr(svc.requests, "get", _boom)
    result = svc.get_forecast()
    assert result["configured"] is False
    assert result["readings"] == []


def test_fetch_and_store_forecast_requires_location(app, monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("ما يفترض يتصل قبل التحقق من الموقع")
    monkeypatch.setattr(svc.requests, "get", _boom)
    with pytest.raises(svc.WeatherFetchError):
        svc.fetch_and_store_forecast()


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _fake_hourly_payload(base_day, days=2):
    """يبني رد Open-Meteo مزيّف — ذروة حر الساعة 14 كل يوم (42°م/20%
    رطوبة)، وبرودة نسبية بقية الساعات، للتأكد إن الكود ياخذ ساعة
    الذروة فعلاً مو متوسطاً يومياً مسطّحاً."""
    times, temps, hums = [], [], []
    for d in range(days):
        day = base_day + timedelta(days=d)
        for h in range(24):
            times.append(f"{day.isoformat()}T{h:02d}:00")
            if h == 14:
                temps.append(42.0)
                hums.append(20.0)
            else:
                temps.append(25.0)
                hums.append(40.0)
    return {"hourly": {"time": times, "temperature_2m": temps, "relative_humidity_2m": hums}}


def _configure_location():
    fs = FarmSettings.get()
    fs.farm_latitude = 24.7
    fs.farm_longitude = 46.7
    db.session.commit()
    return fs


def test_fetch_and_store_forecast_uses_peak_hour(app, monkeypatch):
    _configure_location()
    payload = _fake_hourly_payload(date.today(), days=2)
    monkeypatch.setattr(svc.requests, "get", lambda *a, **k: _FakeResponse(payload))

    readings = svc.fetch_and_store_forecast()
    assert len(readings) == 2
    first = readings[0]
    assert first.temp_max_c == 42.0
    assert first.humidity_at_peak == 20.0
    assert first.thi == svc.calculate_thi(42.0, 20.0)


def test_fetch_and_store_forecast_wraps_network_error(app, monkeypatch):
    import requests as real_requests
    _configure_location()

    def _raise(*a, **k):
        raise real_requests.exceptions.ConnectionError("no network")
    monkeypatch.setattr(svc.requests, "get", _raise)
    with pytest.raises(svc.WeatherFetchError):
        svc.fetch_and_store_forecast()


def test_get_forecast_uses_cache_without_refetching(app, monkeypatch):
    """آخر تحديث حديث (أقل من STALE_AFTER_HOURS) — ما لازم يستدعي
    requests.get إطلاقاً، تفادياً لإغراق API الخارجي بكل تحميل صفحة."""
    _configure_location()
    make_weather_reading(date.today(), temp_max_c=30, humidity_at_peak=30, thi=75.0, stress_level="mild")

    def _boom(*a, **k):
        raise AssertionError("ما يفترض يتصل — البيانات المخزّنة حديثة")
    monkeypatch.setattr(svc.requests, "get", _boom)

    result = svc.get_forecast()
    assert result["stale"] is False
    assert result["error"] is None
    assert len(result["readings"]) == 1


def test_generate_heat_checklists_creates_tasks_for_moderate_and_above(app):
    barn = make_barn()
    hot = make_weather_reading(date.today(), temp_max_c=42, humidity_at_peak=20, thi=80.8, stress_level="moderate")

    tasks = svc.generate_heat_checklists([hot])

    assert len(tasks) == 4  # أربع بنود قائمة التفقد
    assert all(t.status == "suggested" for t in tasks)
    assert all(t.barn_id == barn.id for t in tasks)
    assert all(t.source_type == "heat_stress" for t in tasks)


def test_generate_heat_checklists_skips_normal_days(app):
    make_barn()
    cool = make_weather_reading(date.today(), temp_max_c=25, humidity_at_peak=40, thi=70.7, stress_level="normal")

    tasks = svc.generate_heat_checklists([cool])

    assert tasks == []
    assert Task.query.count() == 0


def test_generate_heat_checklists_idempotent(app):
    make_barn()
    hot = make_weather_reading(date.today(), temp_max_c=42, humidity_at_peak=20, thi=80.8, stress_level="moderate")

    first = svc.generate_heat_checklists([hot])
    second = svc.generate_heat_checklists([hot])

    assert len(first) == 4
    assert len(second) == 0
    assert Task.query.count() == 4
