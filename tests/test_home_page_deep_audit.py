"""فحص شامل سطر بسطر — الصفحة الرئيسية (بند بعد فحص صفحة تسجيل الدخول).

اختباران لخللين حقيقيين اكتُشفا:
1. `get_alerts()` (24 دالة توليد/تجميع تفحص جداول كاملة) كانت تُستدعى
   مرتين كاملتين بنفس تحميل الصفحة الرئيسية (`_today_counts` ثم
   `alert_counts_by_animal`) — صار فيها تخزين مؤقت لعمر الطلب الواحد.
2. بطاقة "مركز الطبيب" كانت تُفحَص بالاسم الحرفي `role.name == 'doctor'`
   بدل صلاحية `health.view` الفعلية — أي دور مخصَّص بنفس الصلاحية بدون
   الاسم "doctor" بالضبط ما كان يشوفها أبداً.
"""
from app.core import alerts_service
from app.models import Role, User
from app.extensions import db


def test_get_alerts_generators_only_scanned_once_per_home_request(logged_in_client, owner, monkeypatch):
    call_count = {"n": 0}
    original = alerts_service._vaccinations_due

    def _counting_wrapper(*args, **kwargs):
        call_count["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(alerts_service, "_vaccinations_due", _counting_wrapper)

    resp = logged_in_client.get("/")
    assert resp.status_code == 200
    assert call_count["n"] == 1, (
        "الصفحة الرئيسية استدعت مجموعة دوال التجميع الثقيلة أكثر من مرة "
        "بنفس الطلب (_today_counts ثم alert_counts_by_animal) — لازم "
        "تُخزَّن مؤقتاً لعمر الطلب الواحد"
    )


def test_doctor_center_tile_shown_by_permission_not_literal_role_name(app, client):
    """دور مخصَّص اسمه غير 'doctor' لكن يملك صلاحية health.view فعلياً
    (نفس صلاحية health.dashboard نفسها) — لازم يشوف بطاقة "مركز الطبيب"."""
    from app.permissions_registry import PERMISSIONS
    from app.models import Permission

    custom_role = Role(name="نائب طبي مخصَّص", display_name="نائب طبي مخصَّص")
    # animals.view لازم تكون موجودة أيضاً — بدونها `home()` نفسها توجّه
    # المستخدم لواجهة `worker_home.html` المبسّطة (بند 295) قبل ما توصل
    # أصلاً لجزء بطاقة "مركز الطبيب" بـ`home.html`.
    custom_role.permissions = Permission.query.filter(
        Permission.code.in_(["health.view", "animals.view"])).all()
    db.session.add(custom_role)
    db.session.commit()

    nurse = User(name="نائب طبي", phone="0500009999", role_id=custom_role.id, language="ar",
                 is_active_account=True)
    nurse.set_password("pass1234")
    db.session.add(nurse)
    db.session.commit()

    client.post("/login", data={"phone": "0500009999", "password": "pass1234"})
    resp = client.get("/")
    # نص خاص ببطاقة "مركز الطبيب" بالرئيسية تحديداً (مو رابط القائمة
    # الجانبية اللي يظهر بكل صفحة أصلاً ومحمي بشكل صحيح من الأساس —
    # النص "مركز الطبيب" وحده يطابق الاثنين معاً، فلازم نميّز الوصف
    # الفريد لبطاقة الرئيسية).
    assert "التحصينات القادمة، والموسوعة المرجعية بصفحة وحدة".encode() in resp.data, (
        "دور مخصَّص يملك صلاحية health.view لازم يشوف بطاقة مركز الطبيب "
        "بالرئيسية بغض النظر عن اسم الدور الحرفي"
    )
