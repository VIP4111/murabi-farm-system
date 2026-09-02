"""بند إصلاح — استمرار لنفس فجوة `vaccinations_due` المُصلَحة (المستخدم
طلب صراحة "ابحث عن فجوات من هاذا النوع"): كذا نية محلية ثانية عندها
كلمة مفتاحية عامة قصيرة (تنبيه/حامل) تخطف سؤال إجراء/إعداد واضح
("كيف أسوي/أضيف/أسجل...؟") وتجاوب بحالة حية غير ذات صلة بدل توجيهه
لبند قاعدة المعرفة الصحيح. الحارس الجديد `_looks_like_howto_action_question`
يفضّل قاعدة المعرفة على النيات المحلية لهذي الحالة تحديداً، وبس لو
فيه تطابق KB فعلي — صفر تأثير على أي سؤال حالة حقيقي."""
from app.assistant import nlu_service


def test_alerts_intent_no_longer_shadows_howto_alerts_screen(app, owner):
    with app.app_context():
        result = nlu_service.answer(owner, "هل اقدر اعدل تنبيهات النظام")
        assert result["intent_code"] == "kb:howto_alerts_screen"


def test_pregnant_intent_no_longer_shadows_howto_mating_pregnancy(app, owner):
    with app.app_context():
        result = nlu_service.answer(owner, "كيف اقدر اسجل تشخيص حمل لانثى حامل")
        assert result["intent_code"] == "kb:howto_mating_pregnancy"


def test_real_alerts_status_question_still_uses_alerts_intent(app, owner):
    """سؤال حالة حقيقي (بدون فعل إجراء) لازم يبقى يشتغل زي ما كان —
    الحارس ما يفعّل إلا لو فيه فعل إجراء واضح بالجملة."""
    with app.app_context():
        result = nlu_service.answer(owner, "وش التنبيهات الحالية")
        assert result["intent_code"] == "alerts"


def test_real_pregnant_count_question_still_uses_pregnant_intent(app, owner):
    with app.app_context():
        result = nlu_service.answer(owner, "كم حوامل لدينا")
        assert result["intent_code"] == "pregnant"


def test_vaccination_capability_question_still_prefers_kb(app, owner):
    """نفس السؤال الأصلي اللي المستخدم أبلغ عنه — يتأكد الحارس العام
    الجديد يغطيه بعد إزالة الكلمة المفتاحية الزايدة بالإصلاح السابق."""
    with app.app_context():
        result = nlu_service.answer(owner, "طيب هل اقدر اسوي تحصين جماعي وحط موعد تحصين القادم")
        assert result["intent_code"] == "kb:howto_vaccination_schedule"


def test_ostrich_intent_no_longer_shadows_howto_incubator_management(app, owner):
    """نفس النمط — نية `ostrich` عندها كلمة عامة "النعام" تخطف سؤال
    إجراء واضح عن إضافة حاضنة جديدة."""
    with app.app_context():
        result = nlu_service.answer(owner, "كيف اضيف حاضنة جديدة للنعام")
        assert result["intent_code"] == "kb:howto_incubator_management"


def test_howto_action_question_with_no_matching_local_intent_still_reaches_kb(app, owner):
    with app.app_context():
        result = nlu_service.answer(owner, "كيف اقدر اسوي مهمة جديدة لعامل")
        assert result["intent_code"] == "kb:howto_assign_task"
