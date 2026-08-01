"""بند إضافي 79 — حارس آلي دائم ضد انجراف الترجمة (نقطة 4 من قائمة
نقاط الضعف). يستخرج فعلياً كل نصوص `_()`/`_l()` من app/**.py و
app/templates/**.html (نفس babel.cfg + الكلمات المفتاحية الصحيحة —
`_l` لازم تُذكر صراحة، DEFAULT_KEYWORDS ما تتضمنها، وهذا بالضبط سبب
فجوة حقيقية اكتشفناها هالبند: كل قواميس STATUS_LABELS_AR/
TASK_TYPE_LABELS_AR/... من بند 74 كانت مكتوبة بـ_l() صحيح، لكن
الاستخراج وقتها ما شافها، فبقيت غير مترجمة فعلياً رغم كل الشغل).

لو أي بند مستقبلي أضاف نص `_()`/`_l()` جديد ونسى يترجمه بالثلاث لغات،
هذا الاختبار يفشل بوضوح ويسمّي النص الناقص — بدل ما يكتشف بالصدفة بعد
أسابيع زي ما صار هالمرة."""
from babel.messages.extract import extract_from_dir, DEFAULT_KEYWORDS
from babel.messages.pofile import read_po

LANGUAGES = ["am", "hi", "en"]


def _extract_live_msgids():
    keywords = dict(DEFAULT_KEYWORDS)
    keywords["_l"] = None
    results = extract_from_dir(
        "app",
        method_map=[("**.py", "python"), ("templates/**.html", "jinja2")],
        keywords=keywords,
    )
    msgids = set()
    for filename, lineno, message, comments, context in results:
        msgids.add(message[0] if isinstance(message, tuple) else message)
    return msgids


def test_every_live_translatable_string_is_translated_in_all_languages():
    msgids = _extract_live_msgids()
    assert len(msgids) > 100  # فحص أمانة — لو رجعت قليلة، الاستخراج نفسه معطوب

    failures = {}
    for lang in LANGUAGES:
        with open(f"app/translations/{lang}/LC_MESSAGES/messages.po", "rb") as f:
            catalog = read_po(f)
        missing = sorted(
            msgid for msgid in msgids
            if (entry := catalog.get(msgid)) is None or not entry.string or "fuzzy" in entry.flags
        )
        if missing:
            failures[lang] = missing

    assert not failures, (
        "نصوص غير مترجمة (أو fuzzy) بلغة واحدة أو أكثر — شغّل:\n"
        "  pybabel extract -F babel.cfg -k _l -o messages.pot .\n"
        "  pybabel update -i messages.pot -d app/translations\n"
        "ثم ترجم النصوص الناقصة وشغّل pybabel compile.\n"
        f"التفاصيل: {failures}"
    )
