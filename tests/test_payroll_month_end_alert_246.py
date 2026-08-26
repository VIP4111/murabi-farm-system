"""بند إضافي 246 — طلبك الصريح: "احتاج تنبيه برواتب كل اخر شهر مع
تأكيد لو فيه خصومات على العامل". تنبيه حي (بدون Cron، نفس فلسفة كل
تنبيهات alerts_service.py) يظهر آخر PAYROLL_MONTH_END_REMINDER_DAYS
أيام من الشهر لكل عامل عنده راتب أساسي وما تجهَّز/تأكَّد راتبه بعد،
+ حالة "متأخر" دائمة لأي شهر سابق كامل ما تأكَّد راتبه (طلب متابع:
لو فات الشهر بدون فتح التطبيق، ما فيه شي يذكّر — أُضيفت هذي الحالة
عشان يستمر التذكير لين يتحل)."""
from datetime import date, datetime

from app.extensions import db
from app.core import alerts_service
from app.core.alerts_service import get_alerts
from app.team import payroll_service
from app.models import Role, User


def _worker(phone, base_salary=1500):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar", base_salary=base_salary)
    u.set_password("pass1234")
    # created_at ثابت وقديم عمداً — عشان اختبارات "شهر متأخر" اللي
    # تجمّد التاريخ بأشهر ماضية ما تُستبعد بسبب فحص "created_at" الجديد
    # (ما نطالب عامل براتب شهر قبل ما كان له حساب أصلاً).
    u.created_at = datetime(2020, 1, 1)
    db.session.add(u)
    db.session.commit()
    return u


class _FixedDate(date):
    _fixed = None

    @classmethod
    def today(cls):
        return cls._fixed


def _freeze(monkeypatch, year, month, day):
    _FixedDate._fixed = date(year, month, day)
    monkeypatch.setattr(alerts_service, "date", _FixedDate)


def test_no_reminder_mid_month(app, monkeypatch):
    _worker("0500046001")
    _freeze(monkeypatch, 2026, 8, 15)  # أغسطس 2026 = 31 يوم، منتصف الشهر
    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "تذكير رواتب نهاية الشهر"]
    assert matching == []


def test_reminder_appears_in_last_days_of_month(app, monkeypatch):
    worker = _worker("0500046002")
    _freeze(monkeypatch, 2026, 8, 30)  # آخر 3 أيام من شهر بـ31 يوم يبدأ يوم 29
    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "تذكير رواتب نهاية الشهر" and worker.name in a["label"]]
    assert len(matching) == 1
    assert "لسا ما تجهَّز راتب هذا الشهر له" in matching[0]["detail"]


def test_last_day_of_month_is_urgent(app, monkeypatch):
    worker = _worker("0500046003")
    _freeze(monkeypatch, 2026, 8, 31)
    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "تذكير رواتب نهاية الشهر" and worker.name in a["label"]]
    assert len(matching) == 1
    assert matching[0]["urgent"] is True


def test_reminder_disappears_once_confirmed(app, owner, monkeypatch):
    worker = _worker("0500046004")
    _freeze(monkeypatch, 2026, 8, 30)
    payroll = payroll_service.get_or_create_draft(user=worker, year=2026, month=8)
    payroll_service.save_draft(payroll, base_salary=1500, bonus_amount=0, deductions=[], recipient_name=None)
    payroll_service.confirm(payroll, actor=owner)

    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "تذكير رواتب نهاية الشهر" and worker.name in a["label"]]
    assert matching == []


def test_reminder_mentions_deductions_when_draft_has_them(app, monkeypatch):
    worker = _worker("0500046005")
    _freeze(monkeypatch, 2026, 8, 30)
    payroll = payroll_service.get_or_create_draft(user=worker, year=2026, month=8)
    payroll_service.save_draft(payroll, base_salary=1500, bonus_amount=0,
                                deductions=[(50, "تأخير")], recipient_name=None)

    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "تذكير رواتب نهاية الشهر" and worker.name in a["label"]]
    assert len(matching) == 1
    assert "خصومات بقيمة 50.00" in matching[0]["detail"]


def test_worker_without_base_salary_not_included(app, monkeypatch):
    worker = _worker("0500046006", base_salary=None)
    _freeze(monkeypatch, 2026, 8, 30)
    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "تذكير رواتب نهاية الشهر" and worker.name in a["label"]]
    assert matching == []


def test_fully_missed_past_month_stays_flagged_regardless_of_current_day(app, monkeypatch):
    worker = _worker("0500046007")
    _freeze(monkeypatch, 2026, 6, 15)
    payroll_service.get_or_create_draft(user=worker, year=2026, month=6)  # يؤسّس earliest = يونيو

    _freeze(monkeypatch, 2026, 8, 10)  # منتصف أغسطس، بعيد عن نهاية الشهر
    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "تذكير رواتب نهاية الشهر"
                and worker.name in a["label"] and "6/2026" in a["label"]]
    assert len(matching) == 1
    assert "متأخر" in matching[0]["detail"]
    assert matching[0]["urgent"] is True


def test_missed_past_month_disappears_once_confirmed(app, owner, monkeypatch):
    worker = _worker("0500046008")
    _freeze(monkeypatch, 2026, 6, 15)
    payroll = payroll_service.get_or_create_draft(user=worker, year=2026, month=6)
    payroll_service.save_draft(payroll, base_salary=1500, bonus_amount=0, deductions=[], recipient_name=None)
    payroll_service.confirm(payroll, actor=owner)

    _freeze(monkeypatch, 2026, 8, 10)
    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "تذكير رواتب نهاية الشهر"
                and worker.name in a["label"] and "6/2026" in a["label"]]
    assert matching == []


def test_worker_not_flagged_for_months_before_account_created(app, monkeypatch):
    worker = _worker("0500046009")
    worker.created_at = datetime(2026, 7, 1)
    db.session.commit()

    _freeze(monkeypatch, 2026, 6, 15)
    other = _worker("0500046010")
    payroll_service.get_or_create_draft(user=other, year=2026, month=6)  # earliest = يونيو

    _freeze(monkeypatch, 2026, 8, 10)
    alerts = get_alerts()
    matching = [a for a in alerts if a["category"] == "تذكير رواتب نهاية الشهر"
                and worker.name in a["label"] and "6/2026" in a["label"]]
    assert matching == []  # يونيو قبل ما ينشأ حسابه (يوليو)
