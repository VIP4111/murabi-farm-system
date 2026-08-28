"""
دفتر ملاحظات المزرعة (بند إضافي 298 — المرحلة ٣ من خطة "عقل المزرعة").

مصدر معرفة تراكمي حقيقي (`FarmNote`، مكتوب بالكامل من إنسان — راجع
docstring النموذج) + استرجاع بتشابه جيب التمام وقت السؤال، بتصفية
مسبقة بحسب الحظيرة/الرأس/الوسم (تحسينك الثاني المعتمد) قبل أي حساب
تشابه — أسرع (نطاق أضيق) وأدق (نتائج من نفس السياق المطلوب فقط).

**حد فاصل صارم**: هذا الملف يضيف "سياق إضافي" لسؤال المساعد، ولا يمس
قاعدة المعرفة الثابتة (`knowledge_base.py`) ولا أي قاعدة طبية بالكود
إطلاقاً — ملاحظة مسترجَعة تُعرَض كخلفية نقاش بس، أبداً كحقيقة مؤكدة
تُبنى عليها إجابة طبية نهائية."""
from app.extensions import db
from app.models import FarmNote, FarmNoteEmbedding, Barn, Animal
from app.assistant import llm_bridge

SEARCH_TOP_K = 5


def create_note(*, body: str, created_by, title: str | None = None, tag: str | None = None,
                 barn_id: int | None = None, animal_id: int | None = None) -> FarmNote:
    """يحفظ الملاحظة أولاً (دايماً تنجح حتى لو Gemini غير مفعَّل)، ثم
    يحاول حساب تمثيلها الرقمي كخطوة إضافية best-effort — ملاحظة بدون
    تمثيل رقمي تبقى محفوظة، بس ما تظهر بنتائج البحث الدلالي لين يتوفر
    مفتاح Gemini ويُعاد حسابها (`embed_note`)."""
    note = FarmNote(title=title, body=body, tag=tag, barn_id=barn_id, animal_id=animal_id,
                     created_by_id=created_by.id if created_by else None)
    db.session.add(note)
    db.session.commit()
    embed_note(note)
    return note


def embed_note(note: FarmNote) -> bool:
    """يحسب/يحدّث التمثيل الرقمي لملاحظة واحدة. يرجع False بصمت (بدون
    رفع استثناء) لو Gemini غير مفعَّل أو فشل الاتصال — النظام يستمر
    يشتغل طبيعياً، بس بدون بحث دلالي لهذي الملاحظة لحد ما تُعاد المحاولة."""
    text = f"{note.title or ''}\n{note.body}".strip()
    vector = llm_bridge.embed_text(text)
    if vector is None:
        return False
    existing = FarmNoteEmbedding.query.filter_by(note_id=note.id).first()
    if existing:
        existing.vector_json = FarmNoteEmbedding.encode_vector(vector)
        existing.model_version = llm_bridge.DEFAULT_EMBEDDING_MODEL
    else:
        db.session.add(FarmNoteEmbedding(
            note_id=note.id, vector_json=FarmNoteEmbedding.encode_vector(vector),
            model_version=llm_bridge.DEFAULT_EMBEDDING_MODEL,
        ))
    db.session.commit()
    return True


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search_notes(query: str, *, barn_id: int | None = None, animal_id: int | None = None,
                  tag: str | None = None, top_k: int = SEARCH_TOP_K) -> list[dict]:
    """تصفية مسبقة (حظيرة/رأس/وسم) ثم تشابه جيب التمام على الملاحظات
    المتبقية بس — نطاق بيانات مزرعة وحدة، حساب بايثون مباشر كافٍ، بدون
    أي قاعدة بيانات متجهية خارجية. ترجع قائمة فاضية بصمت (بدون خطأ) لو
    Gemini غير مفعَّل أو ما فيه ملاحظات لها تمثيل رقمي محسوب أصلاً."""
    q = FarmNote.query
    if barn_id is not None:
        q = q.filter(FarmNote.barn_id == barn_id)
    if animal_id is not None:
        q = q.filter(FarmNote.animal_id == animal_id)
    if tag:
        q = q.filter(FarmNote.tag == tag)
    candidates = q.all()
    if not candidates:
        return []

    query_vector = llm_bridge.embed_text(query)
    if query_vector is None:
        return []

    scored = []
    for note in candidates:
        if not note.embedding:
            continue
        score = _cosine_similarity(query_vector, note.embedding.get_vector())
        scored.append((score, note))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    return [
        {
            "title": note.title, "body": note.body, "tag": note.tag,
            "barn_name": note.barn.barn_name if note.barn else None,
            "animal_no": note.animal.animal_no if note.animal else None,
            "created_at": note.created_at.date().isoformat() if note.created_at else None,
            "similarity": round(score, 3),
        }
        for score, note in scored[:top_k]
    ]
