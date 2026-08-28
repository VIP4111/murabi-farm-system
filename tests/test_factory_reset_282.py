"""بند إضافي 282 — طلبك الصريح "سولي زر ضبط المصنع" بعد ما وضّحت إن
هذي الجلسة ما عندها اتصال مباشر بقاعدة البيانات الحية على Render، فبنينا
زر حقيقي بشاشة الإعدادات ينفّذه صاحب الحلال بنفسه على السيرفر الحي.
حصري لدور المالك (`system.factory_reset`)، محمي بتأكيد مزدوج (عبارة +
كلمة مرور)، ويحافظ على حساب المالك الحالي (نفس الجوال وكلمة المرور)
بعد الحذف الكامل — بدل ما يرجع لحساب `.env` الافتراضي."""
from datetime import date

from app.extensions import db
from app.models import Animal, Barn, Finance, Task, Role, User
from app.core.routes import FACTORY_RESET_CONFIRM_PHRASE
from factories import make_barn


def _seed_some_farm_data():
    barn = make_barn(barn_no="FR-01")
    db.session.add(Finance(date=date.today(), operation_type="sale", amount=500, category="بيع"))
    db.session.add(Task(title="مهمة قبل الحذف", task_type="custom", status="pending"))
    db.session.commit()
    return barn


def test_wrong_confirm_phrase_rejected_no_data_touched(app, logged_in_client, owner):
    barn = _seed_some_farm_data()
    resp = logged_in_client.post("/settings/factory-reset", data={
        "confirm_phrase": "غلط", "password": "pass1234",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Barn.query.filter_by(id=barn.id).first() is not None
    assert User.query.filter_by(phone=owner.phone).first() is not None


def test_wrong_password_rejected_no_data_touched(app, logged_in_client, owner):
    barn = _seed_some_farm_data()
    resp = logged_in_client.post("/settings/factory-reset", data={
        "confirm_phrase": FACTORY_RESET_CONFIRM_PHRASE, "password": "wrong-password",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert Barn.query.filter_by(id=barn.id).first() is not None


def test_worker_without_permission_forbidden(app, client, worker):
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.post("/settings/factory-reset", data={
        "confirm_phrase": FACTORY_RESET_CONFIRM_PHRASE, "password": "pass1234",
    })
    assert resp.status_code == 403


def test_correct_confirmation_wipes_farm_data(app, logged_in_client, owner):
    _seed_some_farm_data()
    resp = logged_in_client.post("/settings/factory-reset", data={
        "confirm_phrase": FACTORY_RESET_CONFIRM_PHRASE, "password": "pass1234",
    })
    assert resp.status_code == 302

    assert Barn.query.count() == 0
    assert Finance.query.count() == 0
    assert Task.query.count() == 0
    assert Animal.query.count() == 0


def test_default_roles_reseeded_after_reset(app, logged_in_client):
    logged_in_client.post("/settings/factory-reset", data={
        "confirm_phrase": FACTORY_RESET_CONFIRM_PHRASE, "password": "pass1234",
    })
    assert Role.query.filter_by(name="owner").first() is not None
    assert Role.query.filter_by(name="doctor").first() is not None
    assert Role.query.filter_by(name="worker").first() is not None


def test_original_owner_login_still_works_after_reset(app, logged_in_client, owner, client):
    """أهم فحص: بعد الحذف الكامل، حساب المالك الأصلي (نفس الجوال
    وكلمة المرور) لازم يبقى شغّال — مو حساب .env الافتراضي المختلف."""
    original_phone = owner.phone
    logged_in_client.post("/settings/factory-reset", data={
        "confirm_phrase": FACTORY_RESET_CONFIRM_PHRASE, "password": "pass1234",
    })

    fresh_client = app.test_client()
    login_resp = fresh_client.post("/login", data={"phone": original_phone, "password": "pass1234"},
                                    follow_redirects=True)
    assert login_resp.status_code == 200
    assert "تسجيل الخروج".encode() in login_resp.data or "الرئيسية".encode() in login_resp.data

    user = User.query.filter_by(phone=original_phone).first()
    assert user is not None
    assert user.role.name == "owner"


def test_default_env_owner_phone_not_left_as_duplicate_login(app, logged_in_client):
    """بعد الترميم، ما يفضل حساب مالك ثانٍ برقم .env الافتراضي —
    الحساب الوحيد هو حساب المالك الأصلي المُرمَّم."""
    logged_in_client.post("/settings/factory-reset", data={
        "confirm_phrase": FACTORY_RESET_CONFIRM_PHRASE, "password": "pass1234",
    })
    owners = User.query.join(Role).filter(Role.name == "owner").all()
    assert len(owners) == 1


def test_current_session_logged_out_after_reset(app, logged_in_client):
    logged_in_client.post("/settings/factory-reset", data={
        "confirm_phrase": FACTORY_RESET_CONFIRM_PHRASE, "password": "pass1234",
    })
    resp = logged_in_client.get("/team/tasks", follow_redirects=True)
    assert "تسجيل الدخول".encode() in resp.data or resp.request.path == "/login"
