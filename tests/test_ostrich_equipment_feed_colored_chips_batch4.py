"""اختبار بند التصميم "بلاطات مراح" (طلبك: "استمر حتى تغطي كل
الشاشات") — دفعة رابعة: بيض النعام، الحاضنات، استهلاك الطاقة/الماء،
حركة مخزون العلف."""
from datetime import date

from app.extensions import db
from app.models import Feed
from app.models.asset import UtilityReading
from app.models.feed import FeedMovement
from app.models.ostrich import Incubator, OstrichEgg
from tests.factories import make_animal, make_barn


def test_eggs_list_shows_status_chip(logged_in_client):
    barn = make_barn()
    mother = make_animal(animal_no="OS-01", gender="أنثى", barn_id=barn.id)
    egg = OstrichEgg(mother_id=mother.id, lay_date=date.today(), hatch_result="pending")
    db.session.add(egg)
    db.session.commit()

    resp = logged_in_client.get("/ostrich/eggs")
    assert resp.status_code == 200
    assert b"egg-status-chip" in resp.data


def test_incubators_list_shows_status_chip(logged_in_client):
    inc = Incubator(code="INC-01", status="active")
    db.session.add(inc)
    db.session.commit()

    resp = logged_in_client.get("/ostrich/incubators")
    assert resp.status_code == 200
    assert b"incubator-status-chip" in resp.data


def test_utilities_list_shows_type_chip(logged_in_client):
    r = UtilityReading(utility_type="water", date=date.today(), quantity=10)
    db.session.add(r)
    db.session.commit()

    resp = logged_in_client.get("/equipment/utilities")
    assert resp.status_code == 200
    assert b"utility-type-chip" in resp.data


def test_feed_movements_list_shows_type_chip(logged_in_client):
    feed = Feed(name="علف اختبار", available_qty=10, unit="كجم", status="active")
    db.session.add(feed)
    db.session.commit()
    m = FeedMovement(feed_id=feed.id, movement_type="in", quantity=5, before_qty=5, after_qty=10)
    db.session.add(m)
    db.session.commit()

    resp = logged_in_client.get("/feed/movements")
    assert resp.status_code == 200
    assert b"feed-move-type-chip" in resp.data
