import json
from datetime import datetime, timezone
from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


class FarmNote(db.Model):
    """ملاحظة ميدانية حرة من المربي أو الدكتور (بند إضافي 298 — المرحلة ٣
    من خطة "عقل المزرعة") — الأساس الحقيقي الوحيد لذاكرة المساعد
    التراكمية (RAG). **مختلفة عمداً عن `AnimalNote` الموجودة أصلاً**:
    `AnimalNote` سجل زمني مرتبط إلزامياً برأس واحد (يظهر بجدول زمني
    بصفحة تفاصيل الرأس)، بينما `FarmNote` معرفة عامة اختيارية الربط
    (حظيرة، رأس، أو ولا شي — ملاحظة عن المزرعة كلها) هدفها الوحيد إثراء
    سياق المساعد الذكي مستقبلاً، مو التوثيق الزمني لرأس معيّن — مفهومان
    حقيقيان مختلفان، مو تكراراً لنفس الشي (نفس الفحص اللي طُبِّق على
    فجوات السلالة/الأدوار ببند 291-295 قبل هالبند، بس بالعكس: هنا فعلاً
    جدولان مختلفان لغرضين مختلفين).

    **مصدر بشري فقط** — أبداً ما يُنشئ المساعد سطراً هنا بنفسه؛ هذا الخط
    الفاصل الصريح بين "المعرفة المتراكمة" (تُغذّى من ملاحظات حقيقية
    كتبها إنسان) و"استنتاج آلي غير مراجَع"، تماشياً مع مبدأ المشروع
    الأقدم والأكثر تكراراً: "المساعد قرار مو طبيب"."""
    __tablename__ = "farm_notes"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160))
    body = db.Column(db.Text, nullable=False)
    # وسم تصنيفي حر بسيط (نص واحد، مو قائمة) — تصفية مسبقة قبل تشابه
    # النصوص (تحسينك الثاني المعتمد: barn_id/animal_id/tag أولاً).
    tag = db.Column(db.String(80))

    barn_id = db.Column(db.Integer, db.ForeignKey("barns.id"), nullable=True)
    barn = db.relationship("Barn")
    animal_id = db.Column(db.Integer, db.ForeignKey("animals.id"), nullable=True)
    animal = db.relationship("Animal")

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by = db.relationship("User")
    created_at = db.Column(db.DateTime, default=_now)


class FarmNoteEmbedding(db.Model):
    """تمثيل رقمي (embedding) لملاحظة واحدة — عمود منفصل عن `FarmNote`
    نفسها عمداً (بدل عمود JSON على نفس الصف) عشان تحديث/إعادة حساب
    التمثيل (مثلاً بعد ترقية نموذج Gemini) ما يلمس صف الملاحظة الأصلية
    إطلاقاً. `vector` نص JSON (قائمة أرقام عشرية) — بحجم بيانات مزرعة
    وحدة، تشابه جيب التمام بحساب بايثون مباشر كافٍ تماماً، بدون حاجة
    لقاعدة بيانات متجهية خارجية منفصلة (قرار معماري موثَّق بخطة "عقل
    المزرعة" المعتمدة)."""
    __tablename__ = "farm_note_embeddings"

    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey("farm_notes.id"), nullable=False, unique=True)
    note = db.relationship("FarmNote", backref=db.backref("embedding", uselist=False))

    vector_json = db.Column(db.Text, nullable=False)
    model_version = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    def get_vector(self) -> list[float]:
        return json.loads(self.vector_json)

    @staticmethod
    def encode_vector(values: list[float]) -> str:
        return json.dumps(list(values))
