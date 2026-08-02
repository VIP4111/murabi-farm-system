"""بند إضافي 95 — تقرير طلب الشراء الشهري. الاحتياج يُحسب من الاستهلاك
الفعلي الحقيقي بالفترة (علف من FeedMovement الصادرة، دواء من مجموع
quantity_used بسجلات المرض/الزيارة/التطعيم)، مو تخمين حسب عدد الرؤوس."""
from datetime import date, timedelta

from app.extensions import db
from app.models import FeedMovement, Disease
from app.reports.report_service import purchase_request_report
from factories import make_animal, make_barn, make_feed, make_pharmacy


def test_feed_below_projected_need_appears_with_suggested_qty(app):
    barn = make_barn()
    feed = make_feed(available_qty=20)  # مخزون قليل
    start = date.today() - timedelta(days=9)
    end = date.today()
    # استهلاك 100 كجم خلال 10 أيام = 10 كجم/يوم → متوقع 300 كجم لـ30 يوم
    db.session.add(FeedMovement(feed_id=feed.id, movement_type="out", quantity=100,
                                 barn_id=barn.id, created_at=start))
    db.session.commit()

    data = purchase_request_report(start, end)
    matching = [r for r in data["table"]["rows"] if r[1] == feed.name]
    assert len(matching) == 1
    row = matching[0]
    assert row[0] == "علف"
    assert float(row[5]) > 0  # الكمية المقترح شراؤها


def test_feed_with_ample_stock_does_not_appear(app):
    barn = make_barn()
    feed = make_feed(available_qty=100000)  # مخزون ضخم يكفي
    start = date.today() - timedelta(days=9)
    end = date.today()
    db.session.add(FeedMovement(feed_id=feed.id, movement_type="out", quantity=10,
                                 barn_id=barn.id, created_at=start))
    db.session.commit()

    data = purchase_request_report(start, end)
    matching = [r for r in data["table"]["rows"] if r[1] == feed.name]
    assert len(matching) == 0


def test_medicine_consumption_from_disease_records(app):
    animal = make_animal()
    pharmacy = make_pharmacy(available_qty=5)
    start = date.today() - timedelta(days=9)
    end = date.today()
    db.session.add(Disease(animal_id=animal.id, disease_name="مرض اختبار", date=start,
                            pharmacy_id=pharmacy.id, quantity_used=50))
    db.session.commit()

    data = purchase_request_report(start, end)
    matching = [r for r in data["table"]["rows"] if r[1] == pharmacy.name]
    assert len(matching) == 1
    assert matching[0][0] == "دواء"


def test_item_never_consumed_does_not_appear(app):
    make_feed(name="علف ما استُهلك أبداً", available_qty=1)
    start = date.today() - timedelta(days=9)
    end = date.today()

    data = purchase_request_report(start, end)
    matching = [r for r in data["table"]["rows"] if r[1] == "علف ما استُهلك أبداً"]
    assert len(matching) == 0
