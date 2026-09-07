"""بند إضافي — طلبك الصريح: "لو رفعت صور في البلاغات اقدر احذفهم...
تقيد فقط لصاحب الحلال". قبل هذا البند ما فيه أي طريقة تحذف صورة دليل
مرفقة ببلاغ (لا الأصلية ولا صورة دليل التنفيذ) — تضل معلَّقة بالسجل
للأبد. الحذف هنا حصري لصاحب الحلال بفحص الدور مباشرة (نفس نمط ضبط
المصنع بـcore.routes)، حتى الدكتور المستلم أو حامل صلاحية
reports.manage ما يقدر يحذفها."""
from app.extensions import db
from app.models import Report, Role, User
from app.team import report_service as svc


def _worker(phone, role_name="worker"):
    role = Role.query.filter_by(name=role_name).first()
    u = User(name=f"مستخدم {phone}", phone=phone, role_id=role.id, language="ar")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def _report_with_images(reporter):
    report = svc.submit_report(
        reporter=reporter, description="بلاغ فيه صورة",
        evidence_image_url="/uploads/images/aaa.jpg",
    )
    report.execution_evidence_image_url = "/uploads/images/bbb.jpg"
    db.session.commit()
    return report


def test_owner_can_delete_evidence_image(app, owner, logged_in_client):
    report = _report_with_images(owner)
    resp = logged_in_client.post(f"/team/reports/{report.id}/delete-image", data={
        "field": "evidence",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(report)
    assert report.evidence_image_url is None


def test_owner_can_delete_execution_evidence_image(app, owner, logged_in_client):
    report = _report_with_images(owner)
    resp = logged_in_client.post(f"/team/reports/{report.id}/delete-image", data={
        "field": "execution",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(report)
    assert report.execution_evidence_image_url is None


def test_non_owner_forbidden_even_with_reports_manage(app, client, owner):
    """حتى حامل صلاحية reports.manage (زي الدكتور) ما يقدر يحذف — طلبك
    الصريح كان "تقيد فقط لصاحب الحلال" بلا استثناء."""
    doctor = _worker("0500088001", role_name="doctor")
    report = _report_with_images(owner)
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.post(f"/team/reports/{report.id}/delete-image", data={"field": "evidence"})
    assert resp.status_code == 403
    db.session.refresh(report)
    assert report.evidence_image_url == "/uploads/images/aaa.jpg"
