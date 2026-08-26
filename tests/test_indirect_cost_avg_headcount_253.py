"""بند إضافي 253 — نصيب الرأس من المصاريف غير المباشرة (تحليل الرأس
الفردي ونقطة التعادل) كان يقسم على عدد الرؤوس *الحالي* الثابت، غير
متسق مع الحساب الدقيق شهر-بشهر اللي صار بالتقرير الشهري (بند 251).
صار يستخدم متوسط عدد الرؤوس خلال فترة وجود الرأس بالقطيع بدل ذلك —
أخف حسابياً من تفصيل شهري كامل (مناسب لصفحة تُفتح لكل رأس بتكرار)."""
from datetime import date

from app.core.finance_report_service import average_head_count_between
from app.core.animal_profile_service import get_profile, break_even_summary
from app.extensions import db
from app.models import Finance
from factories import make_animal


def _months_ago(n):
    today = date.today()
    y, m = today.year, today.month - n
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def test_average_head_count_between_reflects_growth_over_time(app):
    a1 = make_animal(animal_no="AVG-01")
    a1.purchase_date = _months_ago(2)
    a2 = make_animal(animal_no="AVG-02")  # اشترى هالشهر بس
    db.session.commit()

    avg = average_head_count_between(_months_ago(2), date.today())
    # شهرين كان فيهم رأس وحد، الشهر الحالي فيه رأسين = (1+1+2)/3
    assert round(avg, 3) == round((1 + 1 + 2) / 3, 3)


def test_indirect_cost_share_uses_average_not_current_head_count(app):
    a1 = make_animal(animal_no="AVG-03")
    a1.purchase_date = _months_ago(2)
    make_animal(animal_no="AVG-04")  # رأس ثاني اشترى هالشهر بس، يكبّر العدد الحالي
    db.session.add(Finance(date=date.today(), operation_type="expense", amount=300, is_indirect=True))
    db.session.commit()

    profile = get_profile(a1)
    avg_head_count = (1 + 1 + 2) / 3
    assert round(profile["indirect_cost_share"], 2) == round(300 / avg_head_count, 2)
    # السلوك القديم (القسمة على العدد الحالي 2) كان يعطي 150 — تأكيد إن الرقم اختلف فعلاً
    assert profile["indirect_cost_share"] != 150


def test_break_even_summary_uses_average_head_count_too(app):
    a1 = make_animal(animal_no="AVG-05")
    a1.purchase_date = _months_ago(2)
    make_animal(animal_no="AVG-06")
    db.session.add(Finance(date=date.today(), operation_type="expense", amount=300, is_indirect=True))
    db.session.commit()

    rows = break_even_summary()
    row = next(r for r in rows if r["animal"].animal_no == "AVG-05")
    avg_head_count = (1 + 1 + 2) / 3
    expected_share = round(300 / avg_head_count, 2)
    assert row["break_even_price"] == expected_share  # ما فيه purchase_cost/direct_medical/feed هنا


def test_average_head_count_stable_when_herd_unchanged(app):
    """رأسين دخلوا بنفس الشهر (بدون نمو بالقطيع) — المتوسط لازم يساوي
    العدد الحالي بالضبط، مطابق للسلوك القديم بهذي الحالة."""
    make_animal(animal_no="AVG-07")
    make_animal(animal_no="AVG-08")
    avg = average_head_count_between(date.today(), date.today())
    assert avg == 2
