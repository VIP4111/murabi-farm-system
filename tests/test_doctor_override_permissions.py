"""بند إضافي (2026-08-31، طلبك المباشر بعد نقاش صلاحيات الدكتور) —
`sales.override_withdrawal` و`repro.override_close_relation` قراران
استثنائيان طبيان/تكاثريان بحتان، كانا مقصورين على صاحب الحلال بس رغم
إن الدكتور هو أنسب شخص يقيّم صحتهما فعلياً. أضيفا لصلاحيات دور
'الدكتور' الافتراضية (app/permissions_registry.py).

اكتشفنا بالطريق إن sales.override_withdrawal لحالها بلا فايدة عملياً:
شاشة "بيع الحيوان" كاملة (اللي فيها خيار التجاوز) محجوبة خلف
animals.manage، والدكتور ما يملكها. طلبك: أعطه animals.manage كاملة."""
from app.permissions_registry import DEFAULT_ROLES

_DOCTOR_EXPECTED_NEW_PERMS = [
    "sales.override_withdrawal",
    "repro.override_close_relation",
    "animals.manage",
]


def test_doctor_default_role_has_withdrawal_and_relation_overrides():
    doctor_perms = DEFAULT_ROLES["doctor"]["permissions"]
    for code in _DOCTOR_EXPECTED_NEW_PERMS:
        assert code in doctor_perms


def test_seeded_doctor_role_grants_overrides(app):
    from app.models import Role

    doctor = Role.query.filter_by(name="doctor").first()
    codes = {p.code for p in doctor.permissions}
    for code in _DOCTOR_EXPECTED_NEW_PERMS:
        assert code in codes


def test_doctor_can_actually_reach_sell_screen(app, client):
    """الفحص الحاسم — قبل هذا الإصلاح، sales.override_withdrawal كانت
    بلا فايدة لأن شاشة البيع محجوبة خلف animals.manage اللي الدكتور ما
    يملكها. الآن يفترض يشوف نموذج البيع فعلياً."""
    from app.extensions import db
    from app.models import Role, User
    from tests.factories import make_animal

    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="دكتور اختبار البيع", phone="0599999233", role_id=role.id)
    doctor.set_password("pass1234")
    db.session.add(doctor)
    animal = make_animal(animal_no="923")
    db.session.commit()

    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.get(f"/animals/{animal.id}/workflow")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'name="sale_price"' in body
