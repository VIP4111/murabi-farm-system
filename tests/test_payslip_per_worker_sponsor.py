"""بند إضافي — طلبك الصريح: "هل صاحب الحلال راح يكون مكفول جميع العمال
او في امكانيه تسجيل كل عامل بيناته لحالها". قبل هذا البند "صاحب العمل"
بمسير الراتب كان يُطبع دائماً من بيانات صاحب الحلال الوحيدة
(`FarmSettings`) لكل عمال المزرعة بلا استثناء، حتى لو عامل معيّن مكفول
فعلياً على شخص/منشأة ثانية — يخلي المستند مغلوطاً لو استُخدم رسمياً.
`User.sponsor_name/sponsor_national_id/sponsor_phone` حقول اختيارية
جديدة لكل عامل تحل محل بيانات صاحب الحلال بمسير راتبه هو بالذات لو
معبّاة، وترجع تلقائياً لصاحب الحلال (السلوك القديم) لو فاضية."""
from app.extensions import db
from app.models import FarmSettings, Role, User
from app.reports.export_service import resolve_payslip_employer


def _worker(phone, **kwargs):
    role = Role.query.filter_by(name="worker").first()
    u = User(name=f"عامل {phone}", phone=phone, role_id=role.id, language="ar", **kwargs)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_worker_without_sponsor_falls_back_to_farm_owner(app):
    fs = FarmSettings.get()
    fs.farm_name = "مراح بو علي"
    fs.owner_national_id = "1011111111"
    fs.farm_phone = "0501111111"
    db.session.commit()

    worker = _worker("0500077001")
    name, national_id, phone = resolve_payslip_employer(worker, fs)

    assert name == "مراح بو علي"
    assert national_id == "1011111111"
    assert phone == "0501111111"


def test_worker_with_own_sponsor_overrides_farm_owner(app):
    fs = FarmSettings.get()
    fs.farm_name = "مراح بو علي"
    fs.owner_national_id = "1011111111"
    fs.farm_phone = "0501111111"
    db.session.commit()

    worker = _worker(
        "0500077002",
        sponsor_name="مؤسسة الكفيل التجارية", sponsor_national_id="7000222222",
        sponsor_phone="0502222222",
    )
    name, national_id, phone = resolve_payslip_employer(worker, fs)

    assert name == "مؤسسة الكفيل التجارية"
    assert national_id == "7000222222"
    assert phone == "0502222222"

    # صاحب الحلال ما تأثر، وبقية الفريق (بدون كفيل مسجَّل) يستمر يشوفه
    other_worker = _worker("0500077003")
    other_name, _, _ = resolve_payslip_employer(other_worker, fs)
    assert other_name == "مراح بو علي"


def test_salary_update_route_saves_sponsor_fields(app, logged_in_client):
    worker = _worker("0500077004")
    resp = logged_in_client.post(f"/team/salaries/{worker.id}/update", data={
        "sponsor_name": "كفيل مستقل", "sponsor_national_id": "7000333333",
        "sponsor_phone": "0503333333",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(worker)
    assert worker.sponsor_name == "كفيل مستقل"
    assert worker.sponsor_national_id == "7000333333"
    assert worker.sponsor_phone == "0503333333"
