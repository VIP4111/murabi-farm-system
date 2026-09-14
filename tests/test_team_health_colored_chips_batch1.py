"""اختبار بند التصميم "بلاطات مراح" (طلبك: "استمر حتى تغطي كل
الشاشات") — دفعة أولى: أعضاء الفريق، الرواتب، دليل الأطباء."""
from app.extensions import db
from app.models import Doctor


def test_members_list_shows_role_chip(logged_in_client, owner):
    resp = logged_in_client.get("/team/members")
    assert resp.status_code == 200
    assert b"member-role-chip" in resp.data


def test_payroll_list_shows_status_chip(logged_in_client, owner):
    resp = logged_in_client.get("/team/payroll")
    assert resp.status_code == 200
    assert b"payroll-status-chip" in resp.data


def test_doctors_list_shows_type_and_status_chips(logged_in_client):
    doc = Doctor(name="د. اختبار", is_external=True, status="active")
    db.session.add(doc)
    db.session.commit()

    resp = logged_in_client.get("/health/doctors")
    assert resp.status_code == 200
    assert b"doctor-chip" in resp.data
