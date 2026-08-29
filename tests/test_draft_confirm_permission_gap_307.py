"""بند إضافي 307 — طلبك "ابحث عن فجوات، دقّق زين". فجوة أمان حقيقية:
راوت اعتماد المسودات (/assistant/drafts/<id>/confirm) كان يفحص بس
assistant.draft_actions.confirm — صلاحية "تقدر تستخدم شاشة الإدخال
الذكي"، مو "تقدر تعدّل حيوانات فعلياً". دور "العامل" الافتراضي (بند
299) يملك الأولى بدون الثانية (animals.manage) — يعني كان يقدر يسجّل
ولادة/وزن حقيقي عبر مسار المسودات، متجاوزاً نفس فحص animals.manage
اللي يحمي كل مسار كتابة حيوان ثاني بالنظام."""
from app.extensions import db
from app.assistant import draft_action_service
from app.models import Role, User, AssistantDraftAction, AnimalWeight
from factories import make_animal


def _make_worker():
    """نفس دور 'العامل' الافتراضي بالضبط — عنده assistant.draft_actions.
    confirm بس ما عنده animals.manage (تأكيد الفجوة الحقيقية)."""
    role = Role.query.filter_by(name="worker").first()
    user = User(name="عامل اختبار", phone="0599999230", role_id=role.id)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    assert user.has_permission("assistant.draft_actions.confirm")
    assert not user.has_permission("animals.manage")
    return user


def _pending_weight_draft(animal, owner):
    draft = AssistantDraftAction(
        raw_text="سجلت وزن اليوم: 30 كجم", parsed_action_type="record_weight",
        parsed_payload_json=AssistantDraftAction.encode_payload({"target_animal_no": animal.animal_no, "weight": 30}),
        status="pending", created_by_id=owner.id,
    )
    db.session.add(draft)
    db.session.commit()
    return draft


def test_worker_without_animals_manage_cannot_confirm_draft(app, owner):
    """الاختبار الحاسم — قبل الإصلاح، هذا كان ينجح بالغلط."""
    worker = _make_worker()
    animal = make_animal(animal_no="920")
    draft = _pending_weight_draft(animal, owner)

    try:
        draft_action_service.confirm_draft(draft, actor=worker)
        assert False, "لازم يرفع PermissionError — عامل بدون animals.manage ما يفترض يقدر ينفّذ"
    except PermissionError:
        pass

    db.session.refresh(draft)
    assert draft.status == "pending"  # ما تغيّرت
    assert AnimalWeight.query.filter_by(animal_id=animal.id).count() == 0  # صفر كتابة فعلية


def test_worker_without_animals_manage_cannot_confirm_via_route(app, client, owner):
    worker = _make_worker()
    animal = make_animal(animal_no="921")
    draft = _pending_weight_draft(animal, owner)

    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.post(f"/assistant/drafts/{draft.id}/confirm", follow_redirects=True)
    assert resp.status_code == 200
    assert "صلاحية".encode() in resp.data

    db.session.refresh(draft)
    assert draft.status == "pending"
    assert AnimalWeight.query.filter_by(animal_id=animal.id).count() == 0


def test_doctor_with_animals_manage_can_confirm(app, owner):
    """فحص عكسي — دور فعلاً يملك animals.manage (الدكتور) يستمر يشتغل
    طبيعياً، الإصلاح ما يمنع الاستخدام الصحيح."""
    role = Role.query.filter_by(name="doctor").first()
    assert role.has_permission("animals.manage") is False  # الدكتور الافتراضي ما يملكها أصلاً كمان!

    # نبني دوراً مخصَّصاً فعلياً يملك الصلاحيتين معاً — سيناريو "عامل موثوق"
    from app.models import Permission
    perms = Permission.query.filter(Permission.code.in_(
        ["assistant.draft_actions.confirm", "animals.manage"])).all()
    trusted_role = Role(name="عامل موثوق", display_name="عامل موثوق", is_system=False)
    trusted_role.permissions = perms
    db.session.add(trusted_role)
    db.session.commit()

    trusted_worker = User(name="عامل موثوق فعلاً", phone="0599999231", role_id=trusted_role.id)
    trusted_worker.set_password("pass1234")
    db.session.add(trusted_worker)
    db.session.commit()

    animal = make_animal(animal_no="922")
    draft = _pending_weight_draft(animal, owner)

    draft_action_service.confirm_draft(draft, actor=trusted_worker)

    db.session.refresh(draft)
    assert draft.status == "confirmed"
    assert AnimalWeight.query.filter_by(animal_id=animal.id, weight=30).first() is not None
