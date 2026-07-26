"""تطبيع نص عربي بسيط لمطابقة الكلمات المفتاحية بمحرك المساعد المحلي —
يوحّد أشكال الألف/الهمزة والتاء المربوطة ويشيل التشكيل وعلامات الترقيم،
عشان "الأزولة"/"الازولة"/"ازولة" تتطابق كلها بدون ما نكتب كل الاحتمالات
بقائمة الكلمات المفتاحية."""
import re

# تشكيل عربي: فتحة/ضمة/كسرة/سكون/تنوين/شدة/الألف الخنجرية (U+064B-U+0652, U+0670)
_DIACRITICS = re.compile(r"[ً-ْٰ]")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)

_CHAR_MAP = str.maketrans({
    "أ": "ا",  # أ -> ا
    "إ": "ا",  # إ -> ا
    "آ": "ا",  # آ -> ا
    "ٱ": "ا",  # ٱ -> ا
    "ى": "ي",  # ى -> ي
    "ة": "ه",  # ة -> ه
    "ؤ": "و",  # ؤ -> و
    "ئ": "ي",  # ئ -> ي
})


def normalize(text: str) -> str:
    if not text:
        return ""
    text = _DIACRITICS.sub("", text)
    text = text.translate(_CHAR_MAP)
    text = _PUNCT.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text
