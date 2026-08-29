"""بند إضافي 316 — طلبك: "هل استطيع ارسال مهمة عن طريق المساعد الذكي
لدكتور" ثم "احتاج منه يترجم للغة العضو بالفريق" ثم توضيحك الحاسم: "اذا
ما خترت بنفسي اخاف يحول او يتخذ اتجاه غير مرغوب فيه" — النص الحر يوصف
المهمة بس، أبداً ما يحدد المكلَّف؛ الاختيار يجي حصراً من قائمة منسدلة
حقيقية بواجهة الاعتماد، وبعدها يُترجَم نص المهمة تلقائياً للغة الشخص
المختار."""
from unittest.mock import patch

from app.extensions import db
from app.assistant import draft_action_service, llm_bridge
from app.models import Role, User, AssistantDraftAction, Task, AuditLog
from factories import make_animal


def _make_role_user(role_name, phone, language="ar"):
    role = Role.query.filter_by(name=role_name).first()
    user = User(name=f"مستخدم {role_name}", phone=phone, role_id=role.id, language=language)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def _pending_assign_task_draft(owner, task_title="فحص حمل للشاة 405", animal_no=None):
    payload = {"task_title": task_title}
    if animal_no:
        payload["target_animal_no"] = animal_no
    draft = AssistantDraftAction(
        raw_text="وزّع مهمة على الدكتور", parsed_action_type="assign_task",
        parsed_payload_json=AssistantDraftAction.encode_payload(payload),
        summary_ar=task_title, status="pending", created_by_id=owner.id,
    )
    db.session.add(draft)
    db.session.commit()
    return draft


# ---- الحاجز الأهم: بدون اختيار صريح، ما ينفَّذ شي ----

def test_confirm_without_assignee_id_raises_and_writes_nothing(app, owner):
    draft = _pending_assign_task_draft(owner)
    try:
        draft_action_service.confirm_draft(draft, actor=owner)
        assert False, "لازم يرفع ValueError بدون اختيار صريح للمكلَّف"
    except ValueError as e:
        assert "تختار" in str(e)
    db.session.refresh(draft)
    assert draft.status == "pending"
    assert Task.query.count() == 0


def test_llm_never_receives_a_named_assignee_in_allowed_types():
    """تأكيد وثائقي: نوع الإجراء موجود بقائمة الأنواع المسموحة، بس
    التنفيذ نفسه يرفض العمل بدون assignee_id صريح — الحاجز الحقيقي."""
    assert "assign_task" in llm_bridge.ALLOWED_DRAFT_ACTION_TYPES
    assert "assign_task" in draft_action_service.ALLOWED_ACTION_TYPES


# ---- التنفيذ الفعلي مع اختيار صريح ----

def test_confirm_assign_task_with_explicit_assignee_creates_task(app, owner):
    doctor = _make_role_user("doctor", "0599999260", language="ar")
    draft = _pending_assign_task_draft(owner, task_title="فحص حمل")

    draft_action_service.confirm_draft(draft, actor=owner, assignee_id=doctor.id)

    db.session.refresh(draft)
    assert draft.status == "confirmed"
    task = Task.query.filter_by(assignee_id=doctor.id).first()
    assert task is not None
    assert task.title == "فحص حمل"  # عربي، ما تُرجم (الدكتور لغته عربي أصلاً)


def test_confirm_assign_task_resolves_animal_when_given(app, owner):
    doctor = _make_role_user("doctor", "0599999261")
    animal = make_animal(animal_no="970")
    draft = _pending_assign_task_draft(owner, task_title="فحص", animal_no="970")

    draft_action_service.confirm_draft(draft, actor=owner, assignee_id=doctor.id)

    task = Task.query.filter_by(assignee_id=doctor.id).first()
    assert task.animal_id == animal.id


def test_confirm_assign_task_rejects_unknown_animal_number(app, owner):
    doctor = _make_role_user("doctor", "0599999262")
    draft = _pending_assign_task_draft(owner, task_title="فحص", animal_no="لا-يوجد-999")

    try:
        draft_action_service.confirm_draft(draft, actor=owner, assignee_id=doctor.id)
        assert False, "لازم يرفع ValueError"
    except ValueError:
        pass
    assert Task.query.count() == 0


def test_confirm_assign_task_records_audit_and_notification(app, owner):
    """نفس الفحص اللي طبّقناه ببند 308 — assign_task تمر عبر
    task_service.assign_task() الموحَّدة، فتحصل على AuditLog وإشعار
    تيليجرام تلقائياً بدون أي منطق إضافي هنا."""
    doctor = _make_role_user("doctor", "0599999263")
    doctor.telegram_chat_id = "777"
    db.session.commit()
    draft = _pending_assign_task_draft(owner, task_title="فحص حمل")

    with patch("app.core.telegram_service.notify_user") as mock_notify:
        draft_action_service.confirm_draft(draft, actor=owner, assignee_id=doctor.id)

    task = Task.query.filter_by(assignee_id=doctor.id).first()
    assert AuditLog.query.filter_by(action="task.assign", entity_type="Task", entity_id=task.id).count() == 1
    mock_notify.assert_called_once()


# ---- الترجمة الفعلية ----

def test_confirm_assign_task_translates_title_for_non_arabic_assignee(app, owner):
    worker = _make_role_user("worker", "0599999264", language="en")
    draft = _pending_assign_task_draft(owner, task_title="فحص حمل للشاة 405")

    with patch("app.assistant.llm_bridge.translate_text", return_value="Check pregnancy for ewe 405"):
        draft_action_service.confirm_draft(draft, actor=owner, assignee_id=worker.id)

    task = Task.query.filter_by(assignee_id=worker.id).first()
    assert task.title == "Check pregnancy for ewe 405"
    assert "فحص حمل للشاة 405" in task.notes  # النص الأصلي محفوظ بالملاحظة


def test_confirm_assign_task_falls_back_to_original_when_translation_unavailable(app, owner):
    worker = _make_role_user("worker", "0599999265", language="en")
    draft = _pending_assign_task_draft(owner, task_title="فحص حمل")

    with patch("app.assistant.llm_bridge.translate_text", return_value=None):
        draft_action_service.confirm_draft(draft, actor=owner, assignee_id=worker.id)

    task = Task.query.filter_by(assignee_id=worker.id).first()
    assert task.title == "فحص حمل"  # ما فشل التوزيع، بس بقي بالعربي


def test_translate_text_skips_call_for_arabic_target(app, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    assert llm_bridge.translate_text("نص", "ar") is None


def test_translate_text_returns_none_without_gemini_key(app, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm_bridge.translate_text("نص", "en") is None


# ---- الراوت: القائمة المنسدلة إلزامية ----

def test_drafts_confirm_route_requires_assignee_id_form_field(app, client, owner):
    draft = _pending_assign_task_draft(owner)
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.post(f"/assistant/drafts/{draft.id}/confirm", follow_redirects=True)
    assert resp.status_code == 200
    assert "تعذّر التنفيذ".encode() in resp.data
    db.session.refresh(draft)
    assert draft.status == "pending"


def test_drafts_confirm_route_with_assignee_id_succeeds(app, client, owner):
    doctor = _make_role_user("doctor", "0599999266")
    draft = _pending_assign_task_draft(owner, task_title="فحص")
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.post(f"/assistant/drafts/{draft.id}/confirm", data={"assignee_id": str(doctor.id)},
                        follow_redirects=True)
    assert resp.status_code == 200
    assert Task.query.filter_by(assignee_id=doctor.id).first() is not None


def test_drafts_list_shows_assignee_dropdown_for_assign_task_drafts(app, client, owner):
    _make_role_user("doctor", "0599999267")
    _pending_assign_task_draft(owner)
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/assistant/drafts", follow_redirects=True)
    assert b'name="assignee_id"' in resp.data
