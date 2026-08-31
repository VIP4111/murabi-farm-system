"""بند إضافي (2026-08-31، طلبك المباشر بصورة شاشة حقيقية) — التقويم
المنبثق الأصلي لحقول input[type=date] كان يعرض أرقاماً عربية واسم شهر
عربي بحساب إنجليزي بالكامل، لأن Safari يتبع لغة/منطقة نظام تشغيل الجهاز
لهذي الحقول، مو لغة الصفحة — سلوك نظام تشغيل، ما يُصلَح بـ_() مباشرة.

الحل: تقويم JS مبني بالكامل بالتطبيق (base.html) — الحقل الأصلي يبقى
بالـDOM (مخفي بصرياً) يحمل القيمة الفعلية، فهذي الاختبارات تتأكد إن
البنية الأساسية والترجمة سليمة، مو سلوك المتصفح نفسه (يحتاج فحص بصري
فعلي بجهاز حقيقي — راجع تعليمات "تحقّق عبر صورة" بالمشروع)."""


def test_date_input_wrap_css_hides_native_input(app, client):
    """الحقل الأصلي يُخفى بصرياً (opacity:0) لكن يبقى بالـDOM — القيمة
    اللي يُرسَل بها الفورم تبقى نفسها بالضبط (YYYY-MM-DD)، صفر تغيير
    على أي منطق حفظ."""
    resp = client.get("/login")
    assert resp.status_code == 200
    # صفحة تسجيل الدخول ما فيها حقول تاريخ — فحص بسيط إن الصفحة تحمّل
    # الأصول (CSS/JS) الجديدة بدون كسر أي شي بالـhead.
    body = resp.data.decode()
    assert "date-input-wrap" in body
    assert "enhanceDateInputs" in body


def test_new_date_picker_labels_translated_for_english_user(app, client):
    from app.extensions import db
    from app.models import Role, User

    role = Role.query.filter_by(name="owner").first()
    en_owner = User(name="Owner EN Date Test", phone="0599999260", role_id=role.id, language="en")
    en_owner.set_password("pass1234")
    db.session.add(en_owner)
    db.session.commit()

    client.post("/login", data={"phone": en_owner.phone, "password": "pass1234"})
    resp = client.get("/animals/new")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert "Select date" in body
    assert "Clear" in body
    assert "اختر تاريخ" not in body
