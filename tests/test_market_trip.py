"""بند إضافي 204 — طلبك: "لو حطيت أمر بيع وأنا مطلّعهم من المزرعة وصادني
ظرف وما بعت، هل فيه طريقة منظّمة كيف أطلّعها من المزرعة وأرجع أسجّل
عملية مستمرة أو تم البيع؟". أضفنا علم "طلع للسوق" (مو حالة `status`
جديدة عمداً — راجع تعليق الموديل) بنفس بوابة `sell_animal` (لازم توصل
مرحلة 'قرار المصير' وبدون فترة تحريم دواء)، ونفس نمط `_force_stage_10`
الموثّق بـtest_sale_invoice.py."""
from app.core import cycle_engine
from app.extensions import db
from app.models import Role, User
from factories import make_animal


def _force_stage_10(animal):
    def _fake_evaluate(a):
        wf = a.workflow
        wf.current_stage = 10
        wf.stage_name = "قرار المصير"
        wf.status = "complete"
        return {
            "route": wf.route, "allowed_stage": 10, "completed_through": 10,
            "first_blocked_stage": None, "cycle_status": "complete",
            "missing_items": None, "out_of_order_count": 0,
        }
    return _fake_evaluate


def _sellable_animal(animal_no, monkeypatch):
    animal = make_animal(animal_no=animal_no, price=500)
    cycle_engine.get_or_create_workflow(animal)
    monkeypatch.setattr(cycle_engine, "evaluate", _force_stage_10(animal))
    return animal


def test_send_to_market_blocked_for_fresh_animal(app):
    animal = make_animal(animal_no="MKT-01", price=500)
    try:
        cycle_engine.send_to_market(animal, actor_user_id=1)
        assert False, "expected CycleExitBlocked"
    except cycle_engine.CycleExitBlocked:
        pass
    assert animal.market_trip_started_at is None
    assert animal.status == "active"


def test_send_to_market_sets_flag_without_touching_status(app, monkeypatch):
    animal = _sellable_animal("MKT-02", monkeypatch)
    cycle_engine.send_to_market(animal, actor_user_id=1, note="سوق الخميس")
    assert animal.market_trip_started_at is not None
    assert animal.market_trip_note == "سوق الخميس"
    assert animal.status == "active"


def test_return_from_market_clears_flag_and_creates_no_finance_row(app, monkeypatch):
    from app.models import Finance
    animal = _sellable_animal("MKT-03", monkeypatch)
    cycle_engine.send_to_market(animal, actor_user_id=1)
    cycle_engine.return_from_market(animal, actor_user_id=1)
    assert animal.market_trip_started_at is None
    assert animal.market_trip_note is None
    assert animal.status == "active"
    assert Finance.query.filter_by(related_animal_id=animal.id).count() == 0


def test_selling_animal_on_market_trip_clears_the_flag_automatically(app, monkeypatch):
    animal = _sellable_animal("MKT-04", monkeypatch)
    cycle_engine.send_to_market(animal, actor_user_id=1, note="سوق الخميس")
    cycle_engine.sell_animal(animal, sale_price=700, actor_user_id=1)
    assert animal.status == "sold"
    assert animal.market_trip_started_at is None
    assert animal.market_trip_note is None


def _make_owner(phone="0599999170"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك اختبار رحلة السوق", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_send_and_return_from_market_routes_roundtrip(app, client, monkeypatch):
    owner = _make_owner()
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    animal = _sellable_animal("MKT-05", monkeypatch)

    client.post(f"/animals/{animal.id}/send-to-market", data={"note": "سوق الخميس"})
    db.session.refresh(animal)
    assert animal.market_trip_started_at is not None
    assert animal.market_trip_note == "سوق الخميس"

    client.post(f"/animals/{animal.id}/return-from-market", data={})
    db.session.refresh(animal)
    assert animal.market_trip_started_at is None
    assert animal.status == "active"
