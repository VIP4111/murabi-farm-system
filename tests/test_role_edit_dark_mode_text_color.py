"""بند إصلاح: شاشة صلاحيات الدور (role_edit.html) كانت تلوّن نص الصلاحية
العربي بلون ثابت (#333 غامق) بدل متغيّر الثيم — يختفي/يصعب قراءته
بالوضع الليلي، بينما النص الإنجليزي المجاور (اللي يستخدم var(--muted))
يبان بوضوح. المستخدم أرسل صورة شاشة فعلية توضّح الفرق. الإصلاح: استخدام
var(--text)/var(--muted) بدل الألوان الثابتة عشان يتوافق مع الوضعين."""


def test_role_edit_permission_labels_use_theme_aware_colors(app, logged_in_client):
    from app.models import Role

    with app.app_context():
        role = Role.query.filter_by(name="doctor").first()
        role_id = role.id

    resp = logged_in_client.get(f"/settings/roles/{role_id}/edit")
    body = resp.data.decode()
    assert resp.status_code == 200
    # ما فيه لون ثابت غامق يختفي بالوضع الليلي
    assert "color:#333" not in body
    assert "color: #333" not in body
    assert "color:#999" not in body
    # يستخدم متغيرات الثيم بدلاً منها
    assert "var(--text)" in body
