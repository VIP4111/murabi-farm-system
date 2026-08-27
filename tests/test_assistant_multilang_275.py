"""بند إضافي 275 — طلبك الصريح "نعم" ثم "كل شي دفعة وحدة" لما سألت هل
المساعد الذكي بعدة لغات. يضيف دعم en/am/hi للنيات الحية (نفس مجموعة
اللغات المدعومة أصلاً بـ8 شاشات ميدانية عبر User.language)، مع رجوع
تلقائي للعربي لأي شيء لسا ما تُرجم (قاعدة المعرفة تُترجم تدريجياً)."""
from app.assistant import nlu_service, knowledge_base


def test_lang_defaults_to_user_language(app, owner):
    owner.language = "en"
    result = nlu_service.answer(owner, "how many animals")
    assert result["intent_code"] == "herd_count"
    assert "active herd" in result["reply"]


def test_explicit_lang_overrides_user_language(app, owner):
    owner.language = "ar"
    result = nlu_service.answer(owner, "كم عدد الحيوانات", lang="en")
    assert "active herd" in result["reply"]


def test_arabic_still_works_unaffected(app, owner):
    owner.language = "ar"
    result = nlu_service.answer(owner, "كم عدد الحيوانات")
    assert "القطيع النشط" in result["reply"]


def test_amharic_greeting(app, owner):
    result = nlu_service.answer(owner, "ሰላም", lang="am")
    assert result["intent_code"] == "greeting"
    assert "ሙረቢ" in result["reply"]


def test_hindi_finance_keyword_matches(app, owner):
    result = nlu_service.answer(owner, "मुझे लाभ बताओ", lang="hi")
    assert result["intent_code"] == "finance"


def test_unsupported_lang_falls_back_to_arabic():
    from app.assistant.translations import tr, lang_for

    class FakeUser:
        language = "fr"

    assert lang_for(FakeUser()) == "ar"
    assert tr("greeting", "zz") == tr("greeting", "ar")


def test_kb_entry_without_translation_falls_back_to_arabic():
    entry = knowledge_base.ENTRIES[0]
    title, body = knowledge_base.localized_entry(entry, "en")
    assert title == entry.title
    assert body == entry.body
