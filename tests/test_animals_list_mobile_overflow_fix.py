"""بحث "مقاسات الجوال" (2026-09-06) — لقيت شاشة "سجل الحيوانات" تسبب
تمرير أفقي لكامل الصفحة على شاشة 375px (تحقّقت فعلياً بمتصفح حي):
فورم فلترة الحظيرة كان `display:flex` بدون `flex-wrap`، وتسميته
("فلترة بحظيرة لعملية جماعية على حظيرة كاملة") معلَّمة
`white-space:nowrap` — النص الطويل يفرض عرض الفورم أكبر من الشاشة،
وبما إنه ما فيه flex-wrap، الفورم يدفع الصفحة كلها للتمرير أفقياً
(document.documentElement.scrollWidth=531 بدل 375 على viewport 375px
حقيقي — قِس فعلياً قبل الإصلاح). الإصلاح: flex-wrap على الفورم +
إلغاء nowrap عن التسمية."""


def test_barn_filter_form_wraps_instead_of_forcing_horizontal_overflow(logged_in_client):
    resp = logged_in_client.get("/animals")
    assert resp.status_code == 200
    body = resp.data.decode()

    form_start = body.index("فلترة بحظيرة")
    # التسمية نفسها ما لازم تحمل white-space:nowrap (كانت السبب المباشر)
    label_start = body.rindex("<label", 0, form_start)
    label_end = body.index("</label>", form_start)
    label_html = body[label_start:label_end]
    assert "white-space:nowrap" not in label_html

    # الفورم المحيط لازم يلف محتواه (flex-wrap) بدل ما يفرض عرضاً أكبر من الشاشة
    form_tag_start = body.rindex("<form", 0, label_start)
    form_tag_end = body.index(">", form_tag_start)
    form_tag = body[form_tag_start:form_tag_end]
    assert "flex-wrap" in form_tag
