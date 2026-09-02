"""حادثة حقيقية جذرية (2026-09-02) — بلّغ المستخدم مراراً إن فقاعة
التلميح (؟) ما تظهر بعد الضغط، رغم إصلاحين سابقين (clipping، ثم
position:fixed). السبب الفعلي الجذري (اكتُشف بتشغيل نسخة محلية حقيقية
ومراقبة الكونسول مباشرة): `new MutationObserver(...).observe(document.body,
...)` (بند تغليف حقول التاريخ التلقائي) كان مكتوباً *خارج*
DOMContentLoaded — يُنفَّذ فوراً وقت تفسير السكربت بـ<head>، قبل ما
<body> يوجد أصلاً بالـDOM. `document.body` يرجّع null بهذي اللحظة،
فـ.observe(null, ...) يرمي TypeError فوري. الخطأ غير الملتقَط يوقف
تنفيذ *باقي* نفس وسم <script> بالكامل — يعني أي كود مكتوب بعده بنفس
الوسم (معالج نقر .info-tip بالأسفل، وأي كود مستقبلي يُضاف بنفس الوسم)
ما كان يوصله الدور إطلاقاً، بصمت تام بدون أي أثر ظاهر بالواجهة.

تحقّق فعلي: شغّلنا نسخة محلية حقيقية (run.py) وسجّلنا دخول فعلياً —
الكونسول أظهر بالضبط `TypeError: parameter 1 is not of type 'Node'`
عند observe(document.body)، واختفى الخلل تماماً بعد نقل السطر داخل
DOMContentLoaded (الفقاعة صارت تفتح وتُظهر النص الصحيح فعلياً بالمتصفح
الحقيقي، مو محاكاة)."""


def test_mutation_observer_observe_call_is_inside_domcontentloaded():
    with open("app/templates/base.html", encoding="utf-8") as f:
        content = f.read()

    dcl_start = content.index("document.addEventListener('DOMContentLoaded', function(){\n        enhanceDateInputs(document);")
    observe_call = "}).observe(document.body, {childList: true, subtree: true});"
    observe_pos = content.index(observe_call)

    # لازم يكون بعد بداية معالج DOMContentLoaded (جوّاه، مو قبله بالخطأ
    # نفسه)، وقبل نهاية نفس السكربت اللي فيه معالج نقر .info-tip.
    assert dcl_start < observe_pos

    info_tip_click_handler = "document.addEventListener('click', function(e){\n      var tip = e.target.closest('.info-tip');"
    info_tip_pos = content.index(info_tip_click_handler)
    # نفس النقطة اللي كانت تنكسر: أي كود بعد استدعاء .observe() الفاشل
    # (زي معالج نقر التلميحات) لازم يبقى قابلاً للتنفيذ فعلياً — نتأكد
    # هنا إنه موجود أصلاً بنفس الملف بعد نقطة observe (دليل غير مباشر
    # على السياق، الفحص الحاسم الفعلي كان بمتصفح حقيقي).
    assert info_tip_pos > observe_pos
