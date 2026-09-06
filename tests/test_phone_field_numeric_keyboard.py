"""بحث "مقاسات الجوال" (استكمال) — حقول رقم الجوال (تسجيل الدخول،
إضافة/تعديل عضو فريق) كانت `type="text"` أو بدون `type` إطلاقاً، فتطلع
لوحة مفاتيح كاملة بالجوال بدل لوحة أرقام رغم إن المحتوى رقم دايماً —
نفس نمط شاشة الدكتور (`doctor_form.html`) اللي كانت مضبوطة صح أصلاً
(`type="tel"`), يعني كان تناقضاً بين الشاشات مو قراراً متعمَّداً.
الإصلاح: `type="tel" inputmode="numeric"` بكل حقول رقم الجوال."""
import re


def _phone_input_attrs(html: str, field_id_or_name: str) -> str:
    match = re.search(
        r'<input[^>]*name="' + re.escape(field_id_or_name) + r'"[^>]*>', html,
    )
    assert match, f"ما لقيت حقل phone (name={field_id_or_name}) بالصفحة"
    return match.group(0)


def test_login_phone_field_uses_numeric_keyboard(client):
    resp = client.get("/login")
    tag = _phone_input_attrs(resp.data.decode(), "phone")
    assert 'type="tel"' in tag
    assert 'inputmode="numeric"' in tag


def test_new_team_member_phone_field_uses_numeric_keyboard(logged_in_client):
    resp = logged_in_client.get("/team/members/new")
    tag = _phone_input_attrs(resp.data.decode(), "phone")
    assert 'type="tel"' in tag
    assert 'inputmode="numeric"' in tag
