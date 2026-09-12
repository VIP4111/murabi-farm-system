"""بند إصلاح — طلبك: "النصوص القانونية مسودة عامة. هل هاذي قابله
لتعديل عن طريق البرنامج ولا ثابته" ثم "نعم خليه قابل لتعديل". نص
إقرار المخالصة النهائية كان ثابتاً بالكود (`DEFAULT_SETTLEMENT_
PLEDGE_TEXT`)، صار قابلاً للتعديل من شاشة الإعدادات (نفس صفحة نماذج
بنود العقد) ومحفوظاً بـ`FarmSettings.settlement_pledge_text`."""
from app.extensions import db
from app.models import FarmSettings, Role, User


def _new_worker():
    role = Role.query.filter_by(name="worker").first()
    u = User(name="عامل تجريبي", phone="0500055502", role_id=role.id)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_settlement_pledge_text_defaults_to_none_and_page_shows_default_placeholder(app, logged_in_client):
    resp = logged_in_client.get("/settings/contract-templates")
    assert resp.status_code == 200
    assert FarmSettings.get().settlement_pledge_text is None


def test_saving_custom_pledge_text_persists_and_reverts_to_default_when_cleared(app, logged_in_client):
    resp = logged_in_client.post("/settings/settlement-pledge/save", data={
        "settlement_pledge_text": "نص تعهد مخصَّص لهذي المزرعة يذكر {اسم_العامل} و{اسم_الكفيل}.",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert FarmSettings.get().settlement_pledge_text == "نص تعهد مخصَّص لهذي المزرعة يذكر {اسم_العامل} و{اسم_الكفيل}."

    # حفظ نص فاضي يرجّع للسلوك الافتراضي (None)
    logged_in_client.post("/settings/settlement-pledge/save", data={"settlement_pledge_text": ""})
    assert FarmSettings.get().settlement_pledge_text is None


def test_settlement_pdf_uses_custom_pledge_text_with_placeholders_substituted(app, logged_in_client):
    worker = _new_worker()
    fs = FarmSettings.get()
    fs.settlement_pledge_text = "أنا {اسم_العامل} أقرّ بالاستلام من {اسم_الكفيل}."
    db.session.commit()

    resp = logged_in_client.post(f"/team/members/{worker.id}/settlement/print", data={
        "last_work_day": "2026-09-12", "reason": "سفر نهائي",
        "final_salary": "1000", "end_of_service": "0", "leave_balance": "0", "deductions": "0",
    })
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:4] == b"%PDF"


def test_settlement_pdf_falls_back_to_default_pledge_when_not_customized(app, logged_in_client):
    """يتأكد إن السلوك القديم (بدون تعديل من صاحب الحلال) يستمر يشتغل
    بدون أي كسر — نفس فلسفة كل الحقول الاختيارية الثانية بالمشروع."""
    worker = _new_worker()
    assert FarmSettings.get().settlement_pledge_text is None
    resp = logged_in_client.post(f"/team/members/{worker.id}/settlement/print", data={
        "last_work_day": "", "reason": "",
        "final_salary": "500", "end_of_service": "0", "leave_balance": "0", "deductions": "0",
    })
    assert resp.status_code == 200
    assert resp.data[:4] == b"%PDF"
