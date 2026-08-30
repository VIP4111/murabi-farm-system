"""بند إضافي (2026-08-31) — خلل حقيقي أبلغ عنه المستخدم: تعديل صلاحيات
دور جاهز (مثل "الدكتور") من شاشة الإعدادات يشتغل فوراً، لكن بعد فترة
(النشر التالي على Render) يرجع النظام للتركيبة الافتراضية بصمت.

السبب: `Procfile`'s `release: flask db upgrade && flask seed` يشتغل
تلقائياً بكل نشر، و`flask seed` كان يعيد كتابة `role.permissions` من
`DEFAULT_ROLES` لكل الأدوار الجاهزة بدون قيد — حتى لو الدور مُعدَّل
يدوياً. الحل: `Role.permissions_customized` يصير True بأول حفظ يدوي
فعلي، و`flask seed` يتخطى إعادة الكتابة لأي دور معلَّم بهذا."""
from app.extensions import db
from app.models import Permission, Role


def test_role_edit_marks_permissions_customized(app, owner, client):
    doctor = Role.query.filter_by(name="doctor").first()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.post(f"/settings/roles/{doctor.id}/edit", data={
        "display_name": doctor.display_name,
        "permissions": ["animals.view", "health.view"],  # تقليص صريح عن الافتراضي
    }, follow_redirects=True)
    assert resp.status_code == 200

    db.session.refresh(doctor)
    assert doctor.permissions_customized is True
    assert {p.code for p in doctor.permissions} == {"animals.view", "health.view"}


def test_reseed_does_not_overwrite_customized_role(app, owner, client):
    """الاختبار الجوهري: تعديل يدوي ثم `flask seed` (نفس ما يصير بكل
    نشر Render) — الصلاحيات المخصَّصة لازم تبقى كما هي، لا ترجع
    للتركيبة الافتراضية."""
    doctor = Role.query.filter_by(name="doctor").first()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    client.post(f"/settings/roles/{doctor.id}/edit", data={
        "display_name": doctor.display_name,
        "permissions": ["animals.view", "health.view"],
    })

    runner = app.test_cli_runner()
    runner.invoke(args=["seed"])

    db.session.refresh(doctor)
    codes = {p.code for p in doctor.permissions}
    assert codes == {"animals.view", "health.view"}, (
        f"إعادة seed محت التعديل اليدوي! الصلاحيات الحالية: {codes}"
    )


def test_reseed_still_syncs_untouched_role_with_new_default_permissions(app, owner, client):
    """التوازن المطلوب: دور "ما لُمس يدوياً بعد" لازم يستمر يتزامن مع
    أي صلاحية جديدة تُضاف مستقبلاً لـ`DEFAULT_ROLES` — القيد الجديد ما
    يجمّد كل الأدوار، بس اللي عدَّلها صاحب الحلال فعلاً."""
    accountant = Role.query.filter_by(name="accountant").first()
    assert accountant.permissions_customized is False

    # نفرغ صلاحياته يدوياً بقاعدة البيانات مباشرة (محاكاة أي حالة
    # انحراف) بدون المرور بـ`role_edit()` — يعني الدور يبقى "غير مُعلَّم
    # كمخصَّص". seed لازم تعيد ملء التركيبة الافتراضية كاملة.
    accountant.permissions = []
    db.session.commit()

    runner = app.test_cli_runner()
    runner.invoke(args=["seed"])

    db.session.refresh(accountant)
    codes = {p.code for p in accountant.permissions}
    assert "finance.full.manage" in codes  # التركيبة الافتراضية طُبِّقت فعلاً
