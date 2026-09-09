"""بند إصلاح (فحص عميق — طلبك: "ابدا فحص باقي الشاشات المتبقيه بعمق") —
شاشة "النسخ الاحتياطي" (settings_backup.html) فيها عنوانين (`<h2>`)
مكتوبين مباشرة بالتمبلت عربي بحت بدون `_()` — "تحذير: استرجاع من نسخة
احتياطية" و"تأكيد الاسترجاع" — بخلاف كل بقية نصوص نفس الشاشة اللي
مغلَّفة صح. تظهر عربي دايماً حتى لمستخدم لغته إنجليزي."""
from app.extensions import db
from app.models import Role, User


def _english_owner():
    role = Role.query.filter_by(name="owner").first()
    u = User(name="EO", phone="0500099922", role_id=role.id, language="en")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_backup_screen_headers_translate_to_english(app, client):
    owner = _english_owner()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/settings/backup")
    assert resp.status_code == 200
    assert "تحذير: استرجاع من نسخة احتياطية".encode() not in resp.data
    assert "تأكيد الاسترجاع".encode() not in resp.data
    assert b"Warning: restore from backup" in resp.data
    assert b"Confirm restore" in resp.data
