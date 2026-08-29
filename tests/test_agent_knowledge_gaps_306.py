"""بند إضافي 306 — طلبك "ابحث عن فجوات". فجوة حقيقية مؤكَّدة: خطة "عقل
المزرعة" كاملة (بند 296-305) ما أضافت ولا بند معرفة يشرح ميزاتها
الجديدة (نفس نمط الفجوة اللي بند 281 عالجها)، وفجوة ثانية: رسالة عدم
توفر تحليل الصور (بند 305) كانت تحسب `lang` بدون تستخدمه فعلياً —
عربية دائماً بدل تحترم لغة المستخدم (عكس مبدأ بند 275)."""
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize
from app.assistant.translations import tr
from app.assistant import nlu_service


def test_farm_notes_question_matches_entry():
    results = search(normalize("وش هو دفتر ملاحظات المزرعة"))
    assert results
    assert results[0].code == "howto_farm_notes"


def test_smart_draft_entry_question_matches_entry():
    results = search(normalize("كيف أسجل بالصوت سجلت ولادة"))
    assert results
    assert results[0].code == "howto_smart_draft_entry"


def test_animal_checkup_request_question_matches_entry():
    results = search(normalize("كيف أطلب من الدكتور فحص شامل لرأس"))
    assert results
    assert results[0].code == "howto_animal_checkup_request"


def test_image_analysis_question_matches_entry():
    results = search(normalize("أقدر أرسل صورة للمساعد الذكي"))
    assert results
    assert results[0].code == "howto_assistant_image_analysis"


def test_vision_unavailable_message_respects_language():
    ar = tr("vision_unavailable", "ar")
    en = tr("vision_unavailable", "en")
    assert "GEMINI_API_KEY" in ar and "GEMINI_API_KEY" in en
    assert ar != en


def test_answer_with_image_fallback_uses_user_language(app, owner, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    owner.language = "en"
    result = nlu_service.answer_with_image(owner, "what is this?", b"bytes", "image/jpeg")
    assert result["reply"] == tr("vision_unavailable", "en")
    assert "GEMINI_API_KEY" in result["reply"]
