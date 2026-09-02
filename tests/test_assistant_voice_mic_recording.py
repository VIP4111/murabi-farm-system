"""طلبك المباشر بعد إصلاح شاشة المساعد الذكي: "الان ابيك تضيف ميكريفون
او تفعل الميكريفون" — مودال "إرسال مقطع صوتي" (تبويب الإدخال الذكي)
كان يعرض بس حقل "اختر ملف" (رفع مقطع محفوظ مسبقاً)، بدون تسجيل مباشر
بالمايك. بدل بناء ودجت جديدة، وسّعنا `voice_note_widget()` الموجودة
أصلاً (نفس مسجّل الصوت المستخدم بالبلاغات، مجرَّب فعلياً بما فيها
توافق Safari/آيفون) — أضفنا معامل `field_name` اختياري (المساعد
الذكي يتوقع حقل "audio"، البلاغات تتوقع "voice_note" الافتراضي)."""
from app.extensions import db
from app.models import Role, User


def _owner_client(client, phone="0599999300"):
    role = Role.query.filter_by(name="owner").first()
    u = User(name="مالك اختبار الميكروفون", phone=phone, role_id=role.id)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    client.post("/login", data={"phone": u.phone, "password": "pass1234"})
    return u


def test_voice_note_widget_default_field_name_unchanged(app):
    """دفاع بعمق — الاستخدام الحالي بشاشات البلاغات (بدون تمرير
    field_name) لازم يستمر يشتغل بنفس اسم الحقل القديم بالضبط."""
    tmpl = app.jinja_env.get_template("team/_report_widgets.html")
    mod = tmpl.make_module({})
    html = str(mod.voice_note_widget())
    assert 'name="voice_note"' in html


def test_voice_note_widget_custom_field_name(app):
    tmpl = app.jinja_env.get_template("team/_report_widgets.html")
    mod = tmpl.make_module({})
    html = str(mod.voice_note_widget(field_name="audio"))
    assert 'name="audio"' in html
    assert 'name="voice_note"' not in html


def test_assistant_chat_voice_modal_uses_mic_recording_widget(app, client):
    _owner_client(client)
    resp = client.get("/assistant/")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'id="voiceRecordBtn"' in body
    assert 'name="audio"' in body
    assert "getUserMedia" in body


def test_assistant_drafts_new_voice_still_accepts_audio_field(app, client):
    """الفحص الحاسم — الودجت الجديدة تُرسل بنفس اسم الحقل "audio" اللي
    يتوقعه الراوت أصلاً، صفر تغيير على منطق الحفظ."""
    _owner_client(client)
    import io

    data = {"audio": (io.BytesIO(b"fake-audio-bytes"), "voice-note.webm")}
    resp = client.post("/assistant/drafts/new-voice", data=data,
                        content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    assert "لازم ترفع مقطع صوتي" not in resp.data.decode()
