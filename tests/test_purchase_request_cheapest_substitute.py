"""بند إضافي 156 — طلبك بالمثال الحرفي: "شريت شعير نوعين نوع سعره 50
ونوع سعره 55، النظام إذا كان عندي نقص يرسلي فاتورة شراء يقترح شراء
الأرخص ويطبق على كل شي ينقص ويحتاج شراءه." يجمع نقص الأصناف البديلة
(نفس التصنيف ونفس الوحدة) ويقترح تغطيته من الأرخص سعراً بينهم."""
from datetime import date, timedelta

from app.extensions import db
from app.models import FeedMovement
from app.reports.report_service import purchase_request_report
from factories import make_barn, make_feed


def test_suggests_cheapest_item_to_cover_combined_shortage(app):
    barn = make_barn()
    cheap = make_feed(name="شعير رخيص", available_qty=5, unit_price=50)
    cheap.category = "شعير"
    expensive = make_feed(name="شعير غالي", available_qty=5, unit_price=55)
    expensive.category = "شعير"
    db.session.commit()

    start = date.today() - timedelta(days=9)
    end = date.today()
    db.session.add(FeedMovement(feed_id=cheap.id, movement_type="out", quantity=100,
                                 barn_id=barn.id, created_at=start))
    db.session.add(FeedMovement(feed_id=expensive.id, movement_type="out", quantity=100,
                                 barn_id=barn.id, created_at=start))
    db.session.commit()

    data = purchase_request_report(start, end)
    rows = data["table"]["rows"]
    merged = [r for r in rows if "الأرخص" in r[1]]
    assert len(merged) == 1
    assert "شعير رخيص" in merged[0][1]
    assert "شعير غالي" in merged[0][1]
    # ما يظهر صفين منفصلين لنفس المجموعة
    assert not any(r[1] == "شعير رخيص" for r in rows)
    assert not any(r[1] == "شعير غالي" for r in rows)


def test_no_merge_when_only_one_item_in_category(app):
    feed = make_feed(name="علف منفرد", available_qty=5, unit_price=50)
    feed.category = "تصنيف فريد"
    db.session.commit()

    start = date.today() - timedelta(days=9)
    end = date.today()
    barn = make_barn()
    db.session.add(FeedMovement(feed_id=feed.id, movement_type="out", quantity=100,
                                 barn_id=barn.id, created_at=start))
    db.session.commit()

    data = purchase_request_report(start, end)
    rows = data["table"]["rows"]
    assert any(r[1] == "علف منفرد" for r in rows)
    assert not any("الأرخص" in r[1] for r in rows)


def test_no_merge_when_units_differ(app):
    barn = make_barn()
    a = make_feed(name="صنف أ", available_qty=5, unit_price=50)
    a.category = "مختلط"
    a.unit = "كجم"
    b = make_feed(name="صنف ب", available_qty=5, unit_price=60)
    b.category = "مختلط"
    b.unit = "لتر"
    db.session.commit()

    start = date.today() - timedelta(days=9)
    end = date.today()
    db.session.add(FeedMovement(feed_id=a.id, movement_type="out", quantity=100,
                                 barn_id=barn.id, created_at=start))
    db.session.add(FeedMovement(feed_id=b.id, movement_type="out", quantity=100,
                                 barn_id=barn.id, created_at=start))
    db.session.commit()

    data = purchase_request_report(start, end)
    rows = data["table"]["rows"]
    assert not any("الأرخص" in r[1] for r in rows)
    assert any(r[1] == "صنف أ" for r in rows)
    assert any(r[1] == "صنف ب" for r in rows)


def test_no_merge_when_no_price_set(app):
    barn = make_barn()
    a = make_feed(name="بدون سعر أ", available_qty=5)
    a.category = "بلا أسعار"
    b = make_feed(name="بدون سعر ب", available_qty=5)
    b.category = "بلا أسعار"
    db.session.commit()

    start = date.today() - timedelta(days=9)
    end = date.today()
    db.session.add(FeedMovement(feed_id=a.id, movement_type="out", quantity=100,
                                 barn_id=barn.id, created_at=start))
    db.session.commit()

    data = purchase_request_report(start, end)
    rows = data["table"]["rows"]
    assert not any("الأرخص" in r[1] for r in rows)
    assert any(r[1] == "بدون سعر أ" for r in rows)
