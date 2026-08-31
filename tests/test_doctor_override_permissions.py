"""بند إضافي (2026-08-31، طلبك المباشر بعد نقاش صلاحيات الدكتور) —
`sales.override_withdrawal` و`repro.override_close_relation` قراران
استثنائيان طبيان/تكاثريان بحتان، كانا مقصورين على صاحب الحلال بس رغم
إن الدكتور هو أنسب شخص يقيّم صحتهما فعلياً. أضيفا لصلاحيات دور
'الدكتور' الافتراضية (app/permissions_registry.py)."""
from app.permissions_registry import DEFAULT_ROLES


def test_doctor_default_role_has_withdrawal_and_relation_overrides():
    doctor_perms = DEFAULT_ROLES["doctor"]["permissions"]
    assert "sales.override_withdrawal" in doctor_perms
    assert "repro.override_close_relation" in doctor_perms


def test_seeded_doctor_role_grants_overrides(app):
    from app.models import Role

    doctor = Role.query.filter_by(name="doctor").first()
    codes = {p.code for p in doctor.permissions}
    assert "sales.override_withdrawal" in codes
    assert "repro.override_close_relation" in codes
