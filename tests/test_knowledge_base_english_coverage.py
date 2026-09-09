"""بند إصلاح (فحص عميق — طلبك: "افحص شاشة المساعد الذكي كمان"، وقرارك:
"ترجم كل الـ١٢٢ بند") — قاعدة معرفة المساعد الذكي (`knowledge_base.py`)
كانت مبنية بآلية ترجمة جاهزة (`translations` بكل بند + `localized_entry()`)
لكن صفر بند فعلياً مترجَم. هذا الاختبار يثبّت الاكتمال ويمنع أي بند
جديد يُضاف بلا ترجمة إنجليزية من المرور بصمت."""
from app.assistant import knowledge_base
from flask_babel import force_locale


def test_every_kb_entry_has_english_translation():
    missing = [e.code for e in knowledge_base.ENTRIES if "en" not in e.translations]
    assert not missing, f"بنود بدون ترجمة إنجليزية: {missing}"


def test_every_kb_entry_english_translation_is_non_empty():
    empty = []
    for e in knowledge_base.ENTRIES:
        en = e.translations.get("en", {})
        if not en.get("title", "").strip() or not en.get("body", "").strip():
            empty.append(e.code)
    assert not empty, f"بنود لها ترجمة فاضية: {empty}"


def test_localized_entry_returns_english_for_sample_entries(app):
    with force_locale("en"):
        for code in ("ostrich_hatching", "vaccination_protocol", "howto_add_animal", "howto_payroll_prepare"):
            entry = next(e for e in knowledge_base.ENTRIES if e.code == code)
            title, body = knowledge_base.localized_entry(entry, "en")
            assert title != entry.title
            assert body != entry.body
