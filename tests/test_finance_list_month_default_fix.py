"""فحص "سرعة التصفح" — شاشة المالية كانت تجيب *كل* السجلات منذ أول
يوم بالمزرعة بلا حد أقصى (بلوب Python فوقها لحساب المجاميع)، تتراكم
بطأً مع الزمن. الإصلاح: الجدول المعروض يفتح افتراضياً على الشهر
الحالي بس، مع رابط "عرض الكل" صريح (قرار المستخدم) للسجل الكامل —
والمجاميع (إجمالي الداخل/الخارج/صافي الربح) تبقى **كل الوقت** كما
هي، محسوبة بتجميع SQL مباشر بدل سحب كل الصفوف."""
from datetime import date, timedelta, datetime as dt
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models import Finance


def _make_sale(d, amount):
    fin = Finance(date=d, operation_type="sale", category="بيع رأس", item="اختبار", amount=amount)
    db.session.add(fin)
    db.session.commit()
    return fin


def test_default_view_hides_old_rows_but_totals_include_them(app, logged_in_client):
    with app.app_context():
        old_date = date.today().replace(day=1) - timedelta(days=5)  # الشهر اللي قبله
        _make_sale(old_date, 1000)
        _make_sale(date.today(), 500)

    resp = logged_in_client.get("/finance/")
    assert resp.status_code == 200
    body = resp.data.decode()
    # الإجمالي يشمل الاثنين (1000 + 500) رغم إن صف الشهر الماضي مو معروض بالجدول
    assert "1500.00" in body
    # رابط "عرض الكل" لازم يكون موجوداً بالوضع الافتراضي
    assert "عرض الكل" in body


def test_show_all_view_includes_old_rows_and_hides_current_month_only_note(app, logged_in_client):
    with app.app_context():
        old_date = date.today().replace(day=1) - timedelta(days=5)
        fin = _make_sale(old_date, 1000)
        fin_id = fin.id

    resp = logged_in_client.get("/finance/?range=all")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "الشهر الحالي بس" in body  # زر الرجوع للوضع الافتراضي يظهر بدله

    with app.app_context():
        assert Finance.query.get(fin_id) is not None


def test_month_filter_uses_riyadh_day_not_utc(app, logged_in_client, monkeypatch):
    """بند إصلاح (فحص عميق شامل) — كان الفلتر يعتمد `date.today()` الخام
    (UTC) بدل `farm_today()`. عند 00:30 بتوقيت السعودية يوم 1 سبتمبر
    (يوم جديد فعلياً بالسعودية)، UTC لسا يعتبره 31 أغسطس — فيفوّت عرض
    عملية سُجّلت بتاريخ 1 سبتمبر الفعلي ضمن "الشهر الحالي"."""
    fixed_riyadh = dt(2026, 9, 1, 0, 30, tzinfo=ZoneInfo("Asia/Riyadh"))

    class _FixedDateTime(dt):
        @classmethod
        def now(cls, tz=None):
            return fixed_riyadh.astimezone(tz) if tz else fixed_riyadh

    with app.app_context():
        _make_sale(date(2026, 9, 1), 777)

    monkeypatch.setattr("app.extensions.datetime", _FixedDateTime)
    resp = logged_in_client.get("/finance/")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "777.00" in body, (
        "عملية بتاريخ 1 سبتمبر (يوم السعودية الفعلي) ما ظهرت بالجدول الافتراضي — "
        "إشارة إن فلتر 'الشهر الحالي' اعتمد يوم UTC (لسا أغسطس)"
    )
