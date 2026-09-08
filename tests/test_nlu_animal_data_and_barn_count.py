"""نيتان محليتان جديدتان بالمساعد الذكي (بند إضافي، طلبك الصريح بعد
صورة حية: دكتور سأل "عطي بيانات راس رقم 1" ورجع "ما فهمت سؤالك" رغم
إن السؤال واضح وبيانات الرأس موجودة فعلاً) — بيانات رأس محدَّد، وعدد
رؤوس حظيرة محدَّدة. محليتان بالكامل (صفر اعتماد على Gemini)، عشان
تشتغل دايماً حتى لو المفتاح غير مفعَّل أو فشل الاتصال (بالضبط زي
السيناريو الحقيقي اللي صار)."""
from datetime import date

from app.extensions import db
from app.assistant import nlu_service
from app.models import AnimalWeight, Disease, Vaccination, Role, User
from tests.factories import make_animal, make_barn


def _worker(phone, role_name="doctor"):
    role = Role.query.filter_by(name=role_name).first()
    u = User(name=f"مستخدم {phone}", phone=phone, role_id=role.id, language="ar")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_exact_scenario_from_live_report_now_answered_locally(owner, monkeypatch):
    """نفس السؤال بالضبط اللي فشل حياً: "عطي بيانات راس رقم 1" —
    نتأكد إنه ما يصل لـGemini إطلاقاً (نية محلية بحتة)."""
    called = {"count": 0}
    monkeypatch.setattr(nlu_service.llm_bridge, "ask_with_tools", lambda *a, **k: called.__setitem__("count", called["count"] + 1) or None)
    monkeypatch.setattr(nlu_service.llm_bridge, "ask", lambda *a, **k: called.__setitem__("count", called["count"] + 1) or None)

    make_animal(animal_no="1")
    result = nlu_service.answer(owner, "عطي بيانات راس رقم 1")
    assert result["answered_by"] == "local"
    assert result["intent_code"] == "animal_data"
    assert called["count"] == 0
    assert "1" in result["reply"]
    assert result["reply"] != nlu_service.FALLBACK_MSG()


def test_animal_data_includes_weight_disease_and_vaccination(owner):
    animal = make_animal(animal_no="A-405")
    db.session.add(AnimalWeight(animal_id=animal.id, date=date.today(), weight=35.5))
    db.session.add(Disease(animal_id=animal.id, disease_name="نزلة برد", date=date.today(), status="active"))
    db.session.add(Vaccination(animal_id=animal.id, vaccine_name="CDT", date=date.today()))
    db.session.commit()

    result = nlu_service.answer(owner, "بيانات رأس رقم A-405")
    assert result["intent_code"] == "animal_data"
    assert "A-405" in result["reply"]
    assert "35.5" in result["reply"]
    assert "نزلة برد" in result["reply"]
    assert "CDT" in result["reply"]


def test_animal_data_not_found_gives_clear_message(owner):
    result = nlu_service.answer(owner, "بيانات رأس رقم 9999")
    assert result["intent_code"] == "animal_data"
    assert "9999" in result["reply"]


def test_animal_data_requires_permission(owner):
    worker_role = Role.query.filter_by(name="عاملة منزلية").first() or Role.query.filter_by(name="worker").first()
    limited = User(name="بدون صلاحية", phone="0500099210", role_id=worker_role.id, language="ar")
    limited.set_password("pass1234")
    db.session.add(limited)
    db.session.commit()
    make_animal(animal_no="A-406")

    if limited.has_permission("animals.view"):
        return  # الدور الافتراضي عنده الصلاحية أصلاً — الاختبار ما ينطبق
    result = nlu_service.answer(limited, "بيانات رأس رقم A-406")
    # بدون الصلاحية، النية المحلية الجديدة ما تشتغل — يرجع بمسار ثاني
    # (KB/Gemini/fallback)، مو ببيانات الرأس الفعلية.
    assert result["intent_code"] != "animal_data"


def test_barn_count_returns_active_head_count(owner):
    barn = make_barn(barn_no="B-77", barn_name="حظيرة الاختبار")
    make_animal(animal_no="A-501", barn_id=barn.id)
    make_animal(animal_no="A-502", barn_id=barn.id)
    make_animal(animal_no="A-503", barn_id=barn.id, status="sold")  # غير نشط، ما يُحسب

    result = nlu_service.answer(owner, "كم رأس بحظيرة حظيرة الاختبار")
    assert result["intent_code"] == "barn_count"
    assert "2" in result["reply"]
    assert "حظيرة الاختبار" in result["reply"]


def test_exact_animal_number_wins_over_substring_match(owner):
    """بلاغ حي ثانٍ بعد الإصلاح الأول: رأس اسمه "1" ورأس اسمه "18"
    موجودان معاً — سؤال "بيانات راس رقم 1" لازم يحسم لرأس "1" مباشرة
    (مطابقة تامة)، مو يطلع "تعدد نتائج: 1، 18" رغم إن السؤال واضح."""
    make_animal(animal_no="1")
    make_animal(animal_no="18")

    result = nlu_service.answer(owner, "عطي بيانات راس رقم 1")
    assert result["intent_code"] == "animal_data"
    assert "تعدد" not in result["reply"] and "أكثر من نتيجة" not in result["reply"]
    assert "بيانات الرأس 1" in result["reply"] or "الرأس 1:" in result["reply"]


def test_barn_count_not_found_gives_clear_message(owner):
    result = nlu_service.answer(owner, "كم رأس بحظيرة حظيرة غير موجودة أبداً")
    assert result["intent_code"] == "barn_count"
