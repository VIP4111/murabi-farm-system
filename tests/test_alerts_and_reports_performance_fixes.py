"""اختبار بند فحص الأداء (طلبك: "فحص أداء/سرعة الموقع") — يتحقق من:
1. صحة نتائج التنبيهات بعد إزالة استعلامات N+1/المكرَّرة (تصحيح
   المنطق، مو بس السرعة) لثلاث دوال: تذكير رواتب نهاية الشهر، قرب
   انتهاء صلاحية دواء، معدة تحتاج صيانة.
2. شاشة "البلاغات" فعلياً تسوي استعلام واحد إضافي بس (joinedload)
   بدل استعلام منفصل لكل بلاغ لجلب اسم مقدّم البلاغ — عبر عدّ
   الاستعلامات الفعلية بمستمع SQLAlchemy، لا تخمين."""
from contextlib import contextmanager
from datetime import date, timedelta

from sqlalchemy import event

from app.extensions import db
from app.models import Payroll, Pharmacy, Report, Role, User
from app.models.equipment import Equipment, EquipmentMovement


@contextmanager
def count_queries():
    counter = {"n": 0}

    def _on_execute(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    engine = db.session.get_bind()
    event.listen(engine, "before_cursor_execute", _on_execute)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _on_execute)


def test_reports_list_query_count_does_not_scale_with_report_count(logged_in_client, owner):
    """اختبار حقيقي لعدد الاستعلامات (مو تخمين بسقف فضفاض) — نقيس عدد
    الاستعلامات مرة بـ3 بلاغات ومرة بـ20، ونتأكد إن الفرق صغير جداً
    (تحميل مسبق واحد يجيب الكل بضربة وحدة) بدل فرق يقارب عدد البلاغات
    المضافة (دليل N+1 كلاسيكي لو رجع الخلل). لازم مقدّمو بلاغات مختلفون
    (مو نفس المستخدم) — وإلا SQLAlchemy identity map تخبّئ نفس المستخدم
    من أول تحميل وتُخفي خلل N+1 بالغلط (اكتُشف هذا أثناء كتابة
    الاختبار: أول نسخة استخدمت owner كمقدّم بلاغ ثابت لكل الصفوف، فمرّ
    الاختبار حتى بدون الإصلاح، غلط)."""
    role = Role.query.filter_by(name="worker").first()

    def _make_reports(n, start=0):
        for i in range(start, start + n):
            reporter = User(name=f"مبلّغ {i}", phone=f"05000094{i:02d}", role_id=role.id, language="ar")
            reporter.set_password("pass1234")
            db.session.add(reporter)
            db.session.flush()
            db.session.add(Report(reporter_id=reporter.id, description=f"بلاغ اختبار {i}", status="new"))
        db.session.commit()

    _make_reports(3)
    with count_queries() as counter_small:
        resp = logged_in_client.get("/team/reports")
        assert resp.status_code == 200
    small_count = counter_small["n"]

    _make_reports(20, start=3)
    with count_queries() as counter_big:
        resp = logged_in_client.get("/team/reports")
        assert resp.status_code == 200
    big_count = counter_big["n"]

    growth = big_count - small_count
    assert growth <= 3, (
        f"عدد الاستعلامات نما {growth} مع إضافة 20 بلاغ — يدل على خلل N+1 "
        f"(صغير={small_count}, كبير={big_count})"
    )


def test_payroll_month_end_reminder_still_correct_after_batching(app, owner):
    from app.core.alerts_service import _payroll_month_end_reminder

    role = Role.query.filter_by(name="worker").first()
    from datetime import datetime, timezone
    worker = User(name="عامل راتب", phone="0500009300", role_id=role.id, language="ar", base_salary=1000,
                  created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    worker.set_password("pass1234")
    db.session.add(worker)
    db.session.commit()

    today = date.today()
    last_month_year, last_month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    db.session.add(Payroll(user_id=worker.id, year=last_month_year, month=last_month,
                            base_salary=1000, status="draft"))
    db.session.commit()

    alerts = _payroll_month_end_reminder()
    assert any(a["label"].find(worker.name) != -1 for a in alerts), \
        "لازم يطلع تذكير لراتب الشهر السابق غير المؤكَّد بعد التجميع"


def test_medicine_expiring_soon_still_correct_after_cache_reuse(app):
    from app.core.alerts_service import _medicine_expiring_soon
    from app.models import FarmSettings

    fs = FarmSettings.get()
    med = Pharmacy(name="دواء اختبار", available_qty=10, status="active",
                    expiry_date=date.today() + timedelta(days=1))
    db.session.add(med)
    db.session.commit()

    alerts = _medicine_expiring_soon(fs)
    assert any("دواء اختبار" in a["label"] for a in alerts)


def test_equipment_needs_maintenance_still_correct_with_eager_load(app, owner):
    from app.core.alerts_service import _equipment_needs_maintenance

    item = Equipment(name="أداة اختبار", available_qty=1, unit="قطعة", status="active", needs_maintenance=True)
    db.session.add(item)
    db.session.commit()
    movement = EquipmentMovement(equipment_id=item.id, movement_type="out", quantity=1,
                                  condition_at_handout="needs_maintenance", borrowed_by_id=owner.id)
    db.session.add(movement)
    db.session.commit()

    alerts = _equipment_needs_maintenance()
    assert len(alerts) == 1
    assert owner.name in alerts[0]["detail"]
