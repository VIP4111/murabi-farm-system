"""رسم رقعة الأذن (بند إضافي 211) — شكل ملوّن بنفس لون الحيوان، بحرفه
(عربي/إنجليزي) لو موجود، عشان يتعرّف عليها المربّي بالنظر زي رقعتها
الفعلية بالأذن. SVG مباشر بدون صور ولا ملفات، فيشتغل أوفلاين ويتكيّف مع
أي حجم.

خريطة الألوان نسخة من `COLOR_HEX` بملف `static/color_chips.js` (مصدرها
الأصلي) — لو أضفت لوناً جديداً هناك أضفه هنا بنفس القيمة. أي لون مخصَّص
غير موجود بالخريطة يُرسم رمادي بحدّ متقطّع، نفس سلوك فقاعات اختيار اللون."""
from flask_babel import lazy_gettext as _l
from markupsafe import Markup, escape

COLOR_HEX = {
    "أبيض": "#ffffff", "أسود": "#1a1a1a", "أحمر": "#b3402a",
    "بني": "#8b5e34", "رمادي": "#9ca3af", "أصفر": "#e8c545",
}
SHAPE_LABELS = {
    "circle": _l("دائرة"), "square": _l("مربع"), "rectangle": _l("مستطيل"), "triangle": _l("مثلث"),
    "diamond": _l("معيّن"), "oval": _l("بيضاوي"), "star": _l("نجمة"),
}
UNKNOWN_HEX = "#d1d5db"
DARK_FILLS = {"#1a1a1a", "#b3402a", "#8b5e34"}  # نص أبيض فوقها، غيرها نص غامق

_SHAPES = {
    "circle": '<circle cx="20" cy="20" r="17"{a}/>',
    "square": '<rect x="5" y="5" width="30" height="30" rx="3"{a}/>',
    "rectangle": '<rect x="2" y="10" width="36" height="20" rx="3"{a}/>',
    "triangle": '<polygon points="20,4 37,35 3,35" stroke-linejoin="round"{a}/>',
    "diamond": '<polygon points="20,2 38,20 20,38 2,20" stroke-linejoin="round"{a}/>',
    "oval": '<ellipse cx="20" cy="20" rx="18" ry="12"{a}/>',
    "star": ('<polygon points="20,2 25.5,14.5 39,15.5 28.8,24.5 32,38 20,30.8 8,38 '
             '11.2,24.5 1,15.5 14.5,14.5" stroke-linejoin="round"{a}/>'),
}
# مركز النص الأنسب لكل شكل (المثلث ثقله بالأسفل)
_TEXT_Y = {"triangle": 29, "star": 25}


def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def tag_badge(animal, size=34):
    """SVG الرقعة، أو نص فاضي لو الحيوان ما له شكل رقعة مسجَّل."""
    shape = _get(animal, "tag_shape")
    if shape not in _SHAPES:
        return Markup("")
    color = _get(animal, "color")
    fill = COLOR_HEX.get(color, UNKNOWN_HEX)
    dash = "" if color in COLOR_HEX else ' stroke-dasharray="3 2"'
    attrs = f' fill="{fill}" stroke="#555" stroke-width="2"{dash}'
    body = _SHAPES[shape].format(a=attrs)
    letter = _get(animal, "tag_letter")
    if letter:
        txt = "#fff" if fill in DARK_FILLS else "#1a1a1a"
        body += (f'<text x="20" y="{_TEXT_Y.get(shape, 25)}" text-anchor="middle" font-size="16" '
                 f'font-weight="800" fill="{txt}" font-family="sans-serif">{escape(letter)}</text>')
    label = escape(str(SHAPE_LABELS[shape]) + (f" {letter}" if letter else ""))
    return Markup(f'<svg class="tag-badge" role="img" aria-label="{label}" viewBox="0 0 40 40" '
                  f'width="{int(size)}" height="{int(size)}" style="flex:0 0 auto; vertical-align:middle;">'
                  f'<title>{label}</title>{body}</svg>')

