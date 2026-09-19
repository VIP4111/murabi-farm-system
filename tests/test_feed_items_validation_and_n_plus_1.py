"""فحص شامل سطر بسطر — ميزة العلف: حقول غير مفحوصة تفسد حسابات الحاسبة
الغذائية/مُحسِّن الخلطات بصمت، وN+1 على شاشة "مكوّنات العلف".

قبل الإصلاح: unit_price/energy_kcal_per_kg/unit_weight_kg وأي نسبة
مئوية (بروتين/ألياف/كالسيوم/فوسفور) كانت تُحفَظ مباشرة بلا أي فحص —
سعر سالب يصير "ربح مجاني" وهمي بمعادلة مُحسِّن الخلطات، ونسبة خارج
0-100 تكسر أي حساب غذائي لاحق يعتمد عليها، بصمت تماماً."""
from contextlib import contextmanager
from datetime import date, timedelta

import pytest
from sqlalchemy import event

from app.core import validation_service
from app.extensions import db
from app.feed import feed_service as svc
from app.models import Feed, FeedMovement


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


def test_validate_percent_rejects_out_of_range():
    with pytest.raises(ValueError):
        validation_service.validate_percent(-1)
    with pytest.raises(ValueError):
        validation_service.validate_percent(101)
    validation_service.validate_percent(0)
    validation_service.validate_percent(100)
    validation_service.validate_percent(None)


def test_items_new_rejects_negative_unit_price(logged_in_client):
    resp = logged_in_client.post("/feed/items/new", data={
        "name": "علف اختبار سعر سالب", "unit": "كجم", "available_qty": "10",
        "min_stock_qty": "1", "unit_price": "-5",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Feed.query.filter_by(name="علف اختبار سعر سالب").first() is None, \
        "ما يفترض يُحفَظ مكوّن علف بسعر سالب"


def test_items_new_rejects_out_of_range_protein_percent(logged_in_client):
    resp = logged_in_client.post("/feed/items/new", data={
        "name": "علف اختبار بروتين غلط", "unit": "كجم", "available_qty": "10",
        "min_stock_qty": "1", "protein_percent": "150",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Feed.query.filter_by(name="علف اختبار بروتين غلط").first() is None, \
        "ما يفترض يُحفَظ مكوّن علف بنسبة بروتين خارج 0-100"


def test_items_new_still_accepts_valid_values(logged_in_client):
    resp = logged_in_client.post("/feed/items/new", data={
        "name": "علف اختبار صحيح", "unit": "كجم", "available_qty": "10",
        "min_stock_qty": "1", "unit_price": "3.5", "protein_percent": "16",
    }, follow_redirects=True)
    assert resp.status_code == 200
    item = Feed.query.filter_by(name="علف اختبار صحيح").first()
    assert item is not None
    assert item.unit_price == 3.5
    assert item.protein_percent == 16


def _make_feed_with_movements(name, n_movements):
    feed = Feed(name=name, unit="كجم", available_qty=1000)
    db.session.add(feed)
    db.session.commit()
    for i in range(n_movements):
        db.session.add(FeedMovement(feed_id=feed.id, movement_type="out", quantity=1,
                                     created_at=date.today() - timedelta(days=i % 5)))
    db.session.commit()
    return feed


def test_items_list_query_count_does_not_scale_with_item_count(logged_in_client):
    for i in range(3):
        _make_feed_with_movements(f"FQ-SMALL-{i}", 2)
    with count_queries() as small:
        logged_in_client.get("/feed/items")

    for i in range(20):
        _make_feed_with_movements(f"FQ-BIG-{i}", 2)
    with count_queries() as big:
        logged_in_client.get("/feed/items")

    growth = big["n"] - small["n"]
    assert growth <= 3, (
        f"عدد الاستعلامات نما {growth} مع إضافة 20 مكوّن علف — يدل على "
        f"خلل N+1 (صغير={small['n']}, كبير={big['n']})"
    )
