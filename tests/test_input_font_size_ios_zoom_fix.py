"""بحث "مقاسات الجوال" (استكمال) — حجم خط كل حقول الإدخال بالنظام
(input/select/textarea) كان 14.5px. Safari بالآيفون يكبّر الصفحة
تلقائياً (auto-zoom) عند التركيز على أي حقل حجم خطه أقل من 16px — يعني
كل ضغطة على أي حقل بأي فورم بكل النظام كانت تكبّر الشاشة فجأة على
آيفون. الإصلاح: 16px (الحد الأدنى المطلوب لمنع التكبير)."""
import re


def test_form_field_font_size_is_at_least_16px_to_prevent_ios_auto_zoom(client):
    resp = client.get("/login")
    html = resp.data.decode()
    match = re.search(r"input,\s*select,\s*textarea\s*\{([^}]*)\}", html)
    assert match, "ما لقيت قاعدة CSS المشتركة لحقول الإدخال"
    rule_body = match.group(1)
    size_match = re.search(r"font-size\s*:\s*([\d.]+)px", rule_body)
    assert size_match, "ما فيه font-size صريح بالقاعدة"
    assert float(size_match.group(1)) >= 16, (
        f"حجم خط حقول الإدخال {size_match.group(1)}px أقل من 16px — "
        "Safari بالآيفون بيكبّر الصفحة تلقائياً عند التركيز على أي حقل"
    )
