"""بلّغ المستخدم بصورة شاشة حقيقية: شاشة المساعد الذكي ما تقبل الكتابة
إطلاقاً — السبب الفعلي كان مغلّف "Choose File" العام (بند إضافي
2026-08-31) يغلّف *أي* input[type=file] بالصفحة بدون استثناء، بما فيها
`chatImageInput` المخفي عمداً (style="display:none"، له زر 📷 مخصَّص
بديل). التغليف يحقن صندوق "اختر ملف" ظاهر وسط صف الفورم (flex)، يكسر
التخطيط ويخفي حقل الكتابة الفعلي (`chatInput`) تماماً — نفس المشكلة
تنطبق على مسجّل الملاحظة الصوتية بالبلاغات (`voiceNoteInput`، مخفي
بنفس الطريقة).

الإصلاح: أي حقل file مخفي عمداً (display:none) يُستثنى كلياً من
التغليف — يبقى شغّالاً برمجياً بالضبط زي قبل. الفحص الكامل الفعلي
(jsdom) موثَّق بسجل الكوميت — هذا الاختبار يتأكد من ثبات الحماية
بالمصدر نفسه (نص الحماية موجود، بالترتيب الصحيح قبل أي تغليف)."""
import re


def test_base_html_skips_hidden_file_inputs_before_wrapping():
    with open("app/templates/base.html", encoding="utf-8") as f:
        content = f.read()

    guard = "if (input.style.display === 'none' || window.getComputedStyle(input).display === 'none') return;"
    assert guard in content

    # الترتيب مهم: الحماية لازم تسبق أي سطر يُنشئ .file-input-wrap فعلياً
    wrap_creation = "wrap.className = 'file-input-wrap';"
    guard_pos = content.index(guard)
    wrap_pos = content.index(wrap_creation)
    assert guard_pos < wrap_pos


def test_chat_image_input_stays_hidden_in_source():
    with open("app/templates/assistant/chat.html", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'<input type="file" id="chatImageInput"[^>]*>', content)
    assert m is not None
    assert 'style="display:none;"' in m.group(0)


def test_report_voice_note_input_stays_hidden_in_source():
    """بند إضافي (2026-09-02) — voice_note_widget() صارت تقبل field_name
    اختياري (لإعادة استخدامها بشاشة المساعد الذكي باسم حقل "audio")،
    فاسم الحقل نفسه صار متغيّراً {{ field_name }} بدل نص ثابت — نتأكد
    من "id=" الثابت بدل "name=" المتغيّر."""
    with open("app/templates/team/_report_widgets.html", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'<input type="file" name="\{\{ field_name \}\}" id="voiceNoteInput"[^>]*>', content)
    assert m is not None
    assert 'display:none' in m.group(0)
