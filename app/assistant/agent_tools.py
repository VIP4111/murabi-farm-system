"""
أدوات القراءة الذكية (بند إضافي 297 — المرحلة ٢ من خطة "عقل المزرعة").

مو استعلام SQL حر — قائمة دوال قراءة محدَّدة ومُراجَعة، كل وحدة منها
تلف دالة خدمة حقيقية موجودة أصلاً بالمشروع (`context_service.py`،
`Finance`، `Disease`...). Gemini يقرر بنفسه أي أداة يحتاجها من سؤال
المستخدم الحر، ينفّذها، ويصيغ الجواب من نتيجتها الحقيقية — بدل نص ثابت
مجمَّع مسبقاً (`nlu_service._build_llm_context`، الطريقة القديمة).

**قاعدة صارمة**: كل أداة هنا "قراءة" بس (Read-only) — صفر كتابة بقاعدة
البيانات من هذا الملف. أي تنفيذ فعلي (تسجيل ولادة، تحديث حالة...) يبقى
خارج نطاق هذي المرحلة تماماً (مرحلة ٤ بالخطة المعتمدة: مسار مسودة ←
اعتماد بشري صريح، منفصل كلياً عن هذا الملف).

**فحص الصلاحيات هنا، مو بالطرف الآخر** — كل دالة `build_tools_for_user`
تبنيها تُدرَج بالقائمة النهائية *بس* لو المستخدم يملك صلاحيتها، فـGemini
حرفياً ما يشوف وجود الأداة أصلاً لمستخدم ما يملك صلاحيتها — نفس فلسفة
`context_service.py`'s فحص الصلاحيات بـ`nlu_service.py` قبل الاستدعاء.

**أداة التوضيح (`search_animal_or_barn`)** — تحسينك الأول المعتمد على
الخطة: `animal_no` فريد بقاعدة البيانات (unique constraint)، لكن
المزارع نادراً يعرف الرقم الكامل الدقيق — يقول "الشاة رقم 405" وقد
يطابق هذا أكثر من رأس (مطابقة جزئية) أو أكثر من حظيرة (اسم حظيرة مو
فريد). لو تعددت النتائج، الأداة ترجع `status: ambiguous` بدل تخمين أول
نتيجة — Gemini مُوجَّه بالتعليمات النظامية (`llm_bridge.py`) إنه لازم
يسأل المستخدم يحدد قبل ما يكمل، بدل ما يخمّن بنفسه.
"""
from datetime import date, datetime

from app.models import Animal, Barn, Disease, AnimalWeight, Pregnancy, Vaccination, Finance
from app.assistant import context_service

MAX_SEARCH_CANDIDATES = 6


def search_animal_or_barn(query: str) -> dict:
    """يبحث عن حيوان أو حظيرة برقم أو اسم جزئي. يرجع نتيجة واحدة مؤكدة،
    أو قائمة مرشَّحين لو تعددت المطابقات (يجب عرضها على المستخدم وسؤاله
    التحديد بدل التخمين)، أو "غير موجود".

    Args:
        query: الرقم أو الاسم أو جزء منه كما ذكره المستخدم (مثال: "405"
            أو "حظيرة الحوامل").
    """
    q = (query or "").strip()
    if not q:
        return {"status": "not_found", "message": "لم يُذكر رقم أو اسم للبحث عنه."}

    animals = (Animal.query.filter(Animal.animal_no.ilike(f"%{q}%"))
               .limit(MAX_SEARCH_CANDIDATES + 1).all())
    barns = (Barn.query.filter((Barn.barn_name.ilike(f"%{q}%")) | (Barn.barn_no.ilike(f"%{q}%")))
             .limit(MAX_SEARCH_CANDIDATES + 1).all())

    total = len(animals) + len(barns)
    if total == 0:
        return {"status": "not_found", "message": f"ما فيه حيوان أو حظيرة تطابق \"{q}\"."}

    if total == 1:
        if animals:
            a = animals[0]
            return {"status": "found", "type": "animal", "animal_no": a.animal_no,
                    "barn_name": a.barn.barn_name if a.barn else None}
        b = barns[0]
        return {"status": "found", "type": "barn", "barn_no": b.barn_no, "barn_name": b.barn_name}

    candidates = (
        [{"type": "animal", "animal_no": a.animal_no, "barn_name": a.barn.barn_name if a.barn else None}
         for a in animals[:MAX_SEARCH_CANDIDATES]]
        + [{"type": "barn", "barn_no": b.barn_no, "barn_name": b.barn_name} for b in barns[:MAX_SEARCH_CANDIDATES]]
    )
    return {
        "status": "ambiguous",
        "message": "تعددت النتائج — لازم تسأل المستخدم يحدد قبل ما تكمل، لا تخمّن.",
        "candidates": candidates,
    }


def herd_summary() -> dict:
    """ملخص القطيع الحالي: عدد الرؤوس النشطة الكلي، توزيع الذكور/الإناث
    للمجترات (أغنام/ماعز) والنعام، وعدد الحوامل والقريبات من الولادة."""
    h = context_service.herd_summary()
    p = context_service.pregnant_summary()
    return {**h, "pregnant_count": p["count"], "near_birth_count": p["near_birth_count"],
            "near_birth_animal_numbers": p["near_birth_numbers"]}


def animal_history(animal_no: str) -> dict:
    """يرجع السجل الكامل لرأس واحد محدَّد برقمه الدقيق: الحظيرة، آخر 5
    أوزان مسجَّلة، الأمراض المفتوحة، آخر تحصين، وحالة الحمل لو أنثى.
    استخدم `search_animal_or_barn` أولاً لو الرقم غير مؤكد أو جزئي —
    هذي الأداة تبحث بمطابقة تامة فقط.

    Args:
        animal_no: الرقم الدقيق والكامل للحيوان.
    """
    animal = Animal.query.filter_by(animal_no=animal_no).first()
    if not animal:
        return {"status": "not_found", "message": f"ما فيه حيوان برقم \"{animal_no}\" بالضبط."}

    weights = (AnimalWeight.query.filter_by(animal_id=animal.id)
               .order_by(AnimalWeight.date.desc()).limit(5).all())
    diseases = (Disease.query.filter_by(animal_id=animal.id, status="active")
                .order_by(Disease.date.desc()).all())
    last_vaccination = (Vaccination.query.filter_by(animal_id=animal.id)
                         .order_by(Vaccination.date.desc()).first())

    result = {
        "status": "found",
        "animal_no": animal.animal_no,
        "species": animal.species,
        "gender": animal.gender,
        "barn_name": animal.barn.barn_name if animal.barn else None,
        "status_field": animal.status,
        "recent_weights": [{"date": w.date.isoformat(), "weight_kg": w.weight} for w in weights],
        "open_diseases": [{"disease_name": d.disease_name, "since": d.date.isoformat()} for d in diseases],
        "last_vaccination": (
            {"vaccine_name": last_vaccination.vaccine_name, "date": last_vaccination.date.isoformat()}
            if last_vaccination else None
        ),
    }
    if animal.gender == "أنثى":
        last_pregnancy = (Pregnancy.query.filter_by(female_id=animal.id)
                           .order_by(Pregnancy.date.desc()).first())
        result["last_pregnancy"] = (
            {"date": last_pregnancy.date.isoformat(), "confirmed": last_pregnancy.confirmed}
            if last_pregnancy else None
        )
    return result


def finance_summary(from_date: str, to_date: str) -> dict:
    """ملخص مالي (مبيعات، مشتريات، مصاريف، صافي) لفترة محدَّدة.

    Args:
        from_date: تاريخ البداية بصيغة YYYY-MM-DD.
        to_date: تاريخ النهاية بصيغة YYYY-MM-DD.
    """
    try:
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end = datetime.strptime(to_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return {"status": "error", "message": "صيغة التاريخ يجب أن تكون YYYY-MM-DD."}

    rows = Finance.query.filter(Finance.date >= start, Finance.date <= end,
                                 Finance.is_cancelled.is_(False)).all()
    sales = sum(r.amount for r in rows if r.operation_type == "sale")
    purchases = sum(r.amount for r in rows if r.operation_type == "purchase")
    expenses = sum(r.amount for r in rows if r.operation_type == "expense")
    total_out = purchases + expenses
    net = sales - total_out
    return {
        "status": "found", "from_date": from_date, "to_date": to_date,
        "sales": sales, "purchases": purchases, "expenses": expenses,
        "net": net, "net_percent": round((net / total_out) * 100, 1) if total_out else None,
    }


# خريطة كل أداة لصلاحية الوصول المطلوبة — نفس فلسفة `nlu_service.INTENTS`
# (فحص الصلاحية قبل الاستدعاء، مو بعده). الأداة ما تُعرَض على Gemini
# أصلاً لمستخدم ما يملك صلاحيتها.
_TOOL_PERMISSIONS = {
    search_animal_or_barn: "animals.view",
    herd_summary: "animals.view",
    animal_history: "animals.view",
    finance_summary: "finance.full.manage",
}


def build_tools_for_user(user) -> list:
    """قائمة الأدوات المسموح بها لهذا المستخدم تحديداً — تُمرَّر مباشرة
    لـ Gemini كدوال بايثون (استدعاء تلقائي عبر SDK)."""
    return [fn for fn, permission in _TOOL_PERMISSIONS.items() if user.has_permission(permission)]
