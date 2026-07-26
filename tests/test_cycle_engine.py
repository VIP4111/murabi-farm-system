"""اختبارات app/core/cycle_engine.py — بوابة الخروج (بيع/أرشفة) والنفوق
بدون بوابة. النطاق مقصود: نختبر رفض البيع المبكر ونجاح النفوق، مو
المسار الكامل للعشر مراحل (يحتاج بيانات تكاثر/صحة/إلخ حقيقية كثيرة —
مغطّى فعلياً باختبار المتصفح اليدوي أثناء بند 17، مو هنا)."""
from app.core import cycle_engine
from factories import make_animal


def test_sell_fresh_animal_is_blocked(app):
    animal = make_animal(animal_no="S-01", price=500)
    try:
        cycle_engine.sell_animal(animal, sale_price=600, actor_user_id=1)
        assert False, "expected CycleExitBlocked"
    except cycle_engine.CycleExitBlocked as e:
        assert "قرار المصير" in str(e)
    assert animal.status == "active"


def test_mark_dead_has_no_gate_and_records_finance_loss(app):
    from app.models import Finance
    animal = make_animal(animal_no="S-02", price=700)
    cycle_engine.mark_animal_dead(animal, actor_user_id=1, reason="اختبار")
    assert animal.status == "dead"
    rows = Finance.query.filter_by(related_animal_id=animal.id).all()
    assert len(rows) == 1
    assert rows[0].operation_type == "expense"
    assert rows[0].amount == 700


def test_mark_dead_without_price_records_no_finance_row(app):
    from app.models import Finance
    animal = make_animal(animal_no="S-03", price=None)
    cycle_engine.mark_animal_dead(animal, actor_user_id=1)
    assert Finance.query.filter_by(related_animal_id=animal.id).count() == 0
