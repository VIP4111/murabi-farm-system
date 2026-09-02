"""بلّغ المستخدم بصورة/رسالة حقيقية: "حصلت الفقعة لكن ما يطلع شرح منها
بعد اضغط" — فقاعة .info-tip-bubble كانت position:absolute نسبةً لأقرب
عنصر position:relative، فأي حاوية أب فيها overflow:hidden (زي
.chat-card بشاشة المساعد الذكي، لأجل رؤوس البطاقة المستديرة) تقص
الفقاعة تماماً حتى لو انفتحت فعلياً (class="open" ينضاف صح، بس العرض
المرئي يُقصّ بصمت). الإصلاح: position:fixed + إحداثيات مُحسَبة
بجافاسكربت وقت الفتح (positionTipBubble) تهرب من أي تقييد عرض بأي
حاوية أب. تحقّق فعلي كامل بمحاكاة DOM (jsdom) خارج بيئة الاختبار
موثَّق بسجل الكوميت — هذا الاختبار يثبّت الحماية بالمصدر."""


def test_info_tip_bubble_uses_fixed_positioning_not_absolute():
    with open("app/templates/base.html", encoding="utf-8") as f:
        content = f.read()

    bubble_css_start = content.index(".info-tip-bubble{")
    bubble_css = content[bubble_css_start: bubble_css_start + 300]
    assert "position:fixed" in bubble_css
    assert "position:absolute" not in bubble_css

    assert "function positionTipBubble(tip)" in content
    assert "getBoundingClientRect()" in content
