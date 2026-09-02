"""بند إصلاح: المستخدم سأل المساعد "طيب هل اقدر اسوي تحصين جماعي وحط
موعد تحصين القادم" (سؤال قدرة/طريقة) ورجعه المساعد "ما فيه تحصينات
مستحقة أو متأخرة حالياً" — لأن الكلمة المفتاحية العامة "موعد تحصين"
بنية `vaccinations_due` كانت تطابق أي جملة فيها هذي العبارة الفرعية،
حتى لو السؤال أصلاً عن "كيف أسوي" مو "وش المستحق الآن". هذا يقفل
الطريق تماماً أمام `knowledge_base` اللي فيها إجابة صحيحة جاهزة
(`howto_vaccination_schedule`) لأن نية `INTENTS` المحلية تُفحص أولاً.

الإصلاح: (1) إزالة الكلمة المفتاحية العامة الزائدة "موعد تحصين" من
نية `vaccinations_due` (الكلمات الباقية "تحصين مستحق"/"تحصينات
مستحقة"/"تحصين متاخر" كافية وأدق). (2) ترقية تسجيل `knowledge_base.search`
من عدّ الكلمات المطابقة لجمع أطوالها — عبارة أدق وأطول ("تحصين جماعي")
تفوز تلقائياً على كلمة عامة قصيرة ("تحصين") عند التعادل بالعدد."""
from app.assistant.nlu_service import INTENTS
from app.assistant.knowledge_base import search
from app.assistant.text_utils import normalize

CAPABILITY_QUESTION = "طيب هل اقدر اسوي تحصين جماعي وحط موعد تحصين القادم"


def test_capability_question_does_not_trigger_vaccinations_due_intent():
    normalized = normalize(CAPABILITY_QUESTION)
    matched = [i.code for i in INTENTS if i.matches(normalized)]
    assert "vaccinations_due" not in matched


def test_capability_question_matches_correct_howto_entry():
    hits = search(normalize(CAPABILITY_QUESTION), limit=1)
    assert hits
    assert hits[0].code == "howto_vaccination_schedule"


def test_howto_entry_body_answers_with_yes_and_steps():
    hits = search(normalize(CAPABILITY_QUESTION), limit=1)
    body = hits[0].body
    assert body.startswith("نعم")
    assert "تحصين جماعي" in body
    assert "تقويم التحصينات" in body


def test_actual_due_vaccination_question_still_works():
    """تأكيد عدم كسر النية الأصلية — سؤال حقيقي عن المستحق/المتأخر
    لازم يبقى يطابق نية `vaccinations_due` زي ما كان."""
    for question in ["فيه تحصين مستحق؟", "فيه تحصين متأخر؟"]:
        normalized = normalize(question)
        matched = [i.code for i in INTENTS if i.matches(normalized)]
        assert "vaccinations_due" in matched, question
