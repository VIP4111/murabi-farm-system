"""بند إضافي 249 — بعد نقد صريح: زر "سفر" (بند 247) يسجّل فترة بس
ما فيه شاشة تراجع/تصحح فيها فترات السفر السابقة. أضفنا سجل كامل
قابل للإضافة/التعديل/الحذف."""
import re
from datetime import date

from app.extensions import db
from app.models import Role, User, WorkerTravelPeriod


def _worker(phone):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar", base_salary=1500)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def _csrf(html: str) -> str:
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_history_page_lists_periods_newest_first(app, logged_in_client):
    worker = _worker("0500049001")
    db.session.add_all([
        WorkerTravelPeriod(user_id=worker.id, start_date=date(2026, 1, 1), end_date=date(2026, 1, 10)),
        WorkerTravelPeriod(user_id=worker.id, start_date=date(2026, 6, 1), end_date=date(2026, 6, 5)),
    ])
    db.session.commit()

    resp = logged_in_client.get(f"/team/salaries/{worker.id}/travel-history")
    assert resp.status_code == 200
    html = resp.data.decode()
    idx_june = html.index("2026-06-01")
    idx_jan = html.index("2026-01-01")
    assert idx_june < idx_jan  # الأحدث أول


def test_add_period_manually(app, logged_in_client):
    worker = _worker("0500049002")
    resp = logged_in_client.get(f"/team/salaries/{worker.id}/travel-history")
    token = _csrf(resp.data.decode())

    resp2 = logged_in_client.post(f"/team/salaries/{worker.id}/travel-history/add", data={
        "csrf_token": token, "start_date": "2026-03-01", "end_date": "2026-03-10",
    }, follow_redirects=True)
    assert resp2.status_code == 200
    assert WorkerTravelPeriod.query.filter_by(user_id=worker.id).count() == 1


def test_add_period_rejects_end_before_start(app, logged_in_client):
    worker = _worker("0500049003")
    resp = logged_in_client.get(f"/team/salaries/{worker.id}/travel-history")
    token = _csrf(resp.data.decode())

    resp2 = logged_in_client.post(f"/team/salaries/{worker.id}/travel-history/add", data={
        "csrf_token": token, "start_date": "2026-03-10", "end_date": "2026-03-01",
    }, follow_redirects=True)
    assert resp2.status_code == 200
    assert "لازم يكون بعد" in resp2.data.decode()
    assert WorkerTravelPeriod.query.filter_by(user_id=worker.id).count() == 0


def test_update_period_fixes_wrong_date(app, logged_in_client):
    worker = _worker("0500049004")
    period = WorkerTravelPeriod(user_id=worker.id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
    db.session.add(period)
    db.session.commit()

    resp = logged_in_client.get(f"/team/salaries/{worker.id}/travel-history")
    token = _csrf(resp.data.decode())
    resp2 = logged_in_client.post(f"/team/travel-history/{period.id}/update", data={
        "csrf_token": token, "start_date": "2026-03-02", "end_date": "2026-03-05",
    }, follow_redirects=True)
    assert resp2.status_code == 200
    db.session.refresh(period)
    assert period.start_date == date(2026, 3, 2)


def test_delete_period(app, logged_in_client):
    worker = _worker("0500049005")
    period = WorkerTravelPeriod(user_id=worker.id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 5))
    db.session.add(period)
    db.session.commit()
    period_id = period.id

    resp = logged_in_client.get(f"/team/salaries/{worker.id}/travel-history")
    token = _csrf(resp.data.decode())
    resp2 = logged_in_client.post(f"/team/travel-history/{period_id}/delete", data={
        "csrf_token": token,
    }, follow_redirects=True)
    assert resp2.status_code == 200
    assert WorkerTravelPeriod.query.get(period_id) is None


def test_worker_cannot_access_travel_history(app, client):
    worker = _worker("0500049006")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get(f"/team/salaries/{worker.id}/travel-history")
    assert resp.status_code == 403
