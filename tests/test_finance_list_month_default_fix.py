"""فحص "سرعة التصفح" — شاشة المالية كانت تجيب *كل* السجلات منذ أول
يوم بالمزرعة بلا حد أقصى (بلوب Python فوقها لحساب المجاميع)، تتراكم
بطأً مع الزمن. الإصلاح: الجدول المعروض يفتح افتراضياً على الشهر
الحالي بس، مع رابط "عرض الكل" صريح (قرار المستخدم) للسجل الكامل —
والمجاميع (إجمالي الداخل/الخارج/صافي الربح) تبقى **كل الوقت** كما
هي، محسوبة بتجميع SQL مباشر بدل سحب كل الصفوف."""
from datetime import date, timedelta

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
