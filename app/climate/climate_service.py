"""
رادار المناخ والإجهاد الحراري (بند إضافي 49) — أول اتصال خارجي فعلي
بالمشروع (Open-Meteo، مجاني بدون مفتاح، بقرارك الصريح). موقع واحد
للمزرعة كلها (FarmSettings.farm_latitude/farm_longitude)، مو لكل
حظيرة، أيضاً بقرارك الصريح.

مؤشر THI بمعادلة NRC (1971) القياسية — مصمّمة أصلاً للأبقار الحلوب،
أقرب مرجع عام متوفر، نطبّقها هنا كتقريب عام للأغنام/الماعز لعدم توفر
معيار رسمي خاص بها (نفس منطق "مرجع عام مو بروتوكول دقيق" المستخدم
بدليل الحقن، بند 48).
"""
from datetime import date, datetime, timedelta, timezone

import requests

from app.extensions import db
from app.models import Barn, FarmSettings, Task, WeatherReading
from app.team import task_service

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 7
STALE_AFTER_HOURS = 3
REQUEST_TIMEOUT_SECONDS = 10

STRESS_LABELS_AR = {
    "normal": "طبيعي",
    "mild": "إجهاد خفيف",
    "moderate": "إجهاد متوسط",
    "severe": "إجهاد شديد",
    "emergency": "إجهاد طارئ",
}

# مستويات تستدعي قائمة تفقد ميدانية فورية بالحظائر (طلبك الصريح: تعديل
# مواعيد الإعلاف + مضاد إجهاد حراري بالماء + تفقد تهوية/مظلات)
CHECKLIST_TRIGGER_LEVELS = {"moderate", "severe", "emergency"}


class WeatherFetchError(Exception):
    pass


def calculate_thi(temp_c: float, humidity_pct: float) -> float:
    """معادلة NRC (1971): THI = (1.8T+32) - [(0.55-0.0055RH)(1.8T-26)]."""
    return round(
        (1.8 * temp_c + 32) - ((0.55 - 0.0055 * humidity_pct) * (1.8 * temp_c - 26)), 1
    )


def classify_stress_level(thi: float, settings: "FarmSettings | None" = None) -> str:
    settings = settings or FarmSettings.get()
    if thi < settings.thi_mild:
        return "normal"
    if thi < settings.thi_moderate:
        return "mild"
    if thi < settings.thi_severe:
        return "moderate"
    if thi < settings.thi_emergency:
        return "severe"
    return "emergency"


def is_configured() -> bool:
    settings = FarmSettings.get()
    return settings.farm_latitude is not None and settings.farm_longitude is not None


def _fetch_raw_hourly(lat: float, lon: float) -> dict:
    try:
        resp = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,relative_humidity_2m",
                "forecast_days": FORECAST_DAYS,
                "timezone": "auto",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise WeatherFetchError(f"تعذّر الاتصال بخدمة الطقس: {exc}") from exc


def _daily_peak_readings(raw: dict) -> dict:
    """لكل يوم: (أعلى حرارة، الرطوبة بنفس ساعة الذروة) — أدق لحساب THI
    عند اللحظة الأخطر باليوم، بدل متوسط يومي مسطّح يخفي الذروة."""
    hourly = raw.get("hourly") or {}
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    hums = hourly.get("relative_humidity_2m") or []
    per_day: dict = {}
    for t, temp, hum in zip(times, temps, hums):
        if temp is None or hum is None:
            continue
        d = datetime.fromisoformat(t).date()
        if d not in per_day or temp > per_day[d][0]:
            per_day[d] = (temp, hum)
    return per_day


def fetch_and_store_forecast() -> list[WeatherReading]:
    """يجلب توقعات Open-Meteo ويخزّنها/يحدّثها بجدول WeatherReading.
    يرفع WeatherFetchError صراحة لو الموقع غير مضبوط أو فشل الاتصال —
    الشاشة تتعامل معه بعرض آخر بيانات مخزّنة بدل الانهيار."""
    settings = FarmSettings.get()
    if not is_configured():
        raise WeatherFetchError("موقع المزرعة غير مضبوط بعد — اضبطه من إعدادات رادار المناخ.")

    raw = _fetch_raw_hourly(settings.farm_latitude, settings.farm_longitude)
    per_day = _daily_peak_readings(raw)
    if not per_day:
        raise WeatherFetchError("رد خدمة الطقس ما فيه بيانات صالحة.")

    saved = []
    for d, (temp_max, humidity) in sorted(per_day.items()):
        thi = calculate_thi(temp_max, humidity)
        level = classify_stress_level(thi, settings)
        reading = WeatherReading.query.filter_by(date=d).first()
        if reading is None:
            reading = WeatherReading(date=d)
            db.session.add(reading)
        reading.temp_max_c = temp_max
        reading.humidity_at_peak = humidity
        reading.thi = thi
        reading.stress_level = level
        reading.source = "open-meteo"
        reading.fetched_at = datetime.now(timezone.utc)
        saved.append(reading)
    db.session.commit()
    return saved


def get_forecast(*, force_refresh: bool = False) -> dict:
    """نقطة الدخول للشاشات — يجدّد تلقائياً لو آخر تحديث أقدم من
    STALE_AFTER_HOURS، وإلا يستخدم المخزّن مباشرة (تفادي إغراق API
    الخارجي بكل تحميل صفحة). يرجّع dict فيه القراءات + حالة التحديث."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_AFTER_HOURS)
    has_fresh = WeatherReading.query.filter(WeatherReading.fetched_at >= cutoff).first() is not None

    error = None
    if (force_refresh or not has_fresh) and is_configured():
        try:
            fetch_and_store_forecast()
            has_fresh = True
        except WeatherFetchError as exc:
            error = str(exc)

    today = date.today()
    readings = (
        WeatherReading.query.filter(WeatherReading.date >= today)
        .order_by(WeatherReading.date)
        .limit(FORECAST_DAYS)
        .all()
    )
    return {
        "readings": readings,
        "configured": is_configured(),
        "error": error,
        "stale": bool(readings) and not has_fresh,
    }


def generate_heat_checklists(readings: list[WeatherReading]) -> list[Task]:
    """لأي يوم توقّع بمستوى إجهاد متوسط فأعلى، تولّد مهام تفقّد مقترحة
    (تحتاج مراجعة الدكتور — نفس اتفاقية بقية المهام التلقائية بالنظام،
    مثل خطة العزل) لكل حظيرة نشطة عندها عامل مسؤول. اتقاء التكرار:
    source_type="heat_stress"/source_id=barn.id، ما تتولّد مرتين لنفس
    الحظيرة/التاريخ."""
    trigger_days = [r for r in readings if r.stress_level in CHECKLIST_TRIGGER_LEVELS]
    if not trigger_days:
        return []

    worst = max(trigger_days, key=lambda r: r.thi)
    barns = Barn.query.all()
    created = []

    checklist_items = [
        ("heat_feed_timing", "تعديل مواعيد الإعلاف — قدّم البرسيم/المستنبت بأوقات باردة (فجر/مساء)، تجنّب ذروة الحر"),
        ("heat_water_additive", "إضافة مضاد الإجهاد الحراري لحوض الماء — إلزامي أثناء موجة الحر"),
        ("heat_ventilation", "فحص التهوية (مراوح/فتحات) والتأكد من عملها"),
        ("heat_shade", "فحص المظلات وسلامتها وكفايتها لكل رؤوس الحظيرة"),
    ]

    for barn in barns:
        existing = Task.query.filter_by(
            barn_id=barn.id, source_type="heat_stress", source_id=barn.id, due_date=worst.date
        ).first()
        if existing:
            continue
        for item_type, title in checklist_items:
            task = task_service.create_suggested_task(
                title=f"🌡️ {title} — موجة حر متوقعة ({worst.date.strftime('%Y-%m-%d')}، THI={worst.thi})",
                task_type=item_type,
                barn_id=barn.id,
                due_date=worst.date,
                source_type="heat_stress",
                source_id=barn.id,
                notes=f"مستوى الإجهاد المتوقع: {STRESS_LABELS_AR[worst.stress_level]} (THI={worst.thi})",
            )
            created.append(task)
    return created
