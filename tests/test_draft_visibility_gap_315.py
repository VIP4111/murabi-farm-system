"""بند إضافي 315 — طلبك "اكمل" (جولة تدقيق تاسعة). فجوة إفشاء معلومات
حقيقية: شاشة "الإدخال الذكي" كانت تعرض مسودات كل المزرعة (أرقام/تفاصيل
رؤوس بكل مسودة) لأي حامل assistant.draft_actions.confirm — صلاحية
"تقدر تستخدم الشاشة"، مو "تقدر تشوف بيانات كل الحيوانات" (animals.view).
عامل بدون animals.view (منح افتراضي فعلي، بند 299) كان يشوف مسودات كل
حيوان بالمزرعة، متجاوزاً نفس تقييد شاشة الحيوانات العادية."""
from app.extensions import db
from app.models import Role, User, AssistantDraftAction
from factories import make_animal


def _make_worker(phone="0599999250"):
    role = Role.query.filter_by(name="worker").first()
    user = User(name="عامل اختبار", phone=phone, role_id=role.id)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    assert not user.has_permission("animals.view")
    return user


def _make_draft(created_by, animal_no="960"):
    animal = make_animal(animal_no=animal_no)
    draft = AssistantDraftAction(
        raw_text=f"سجلت وزن اليوم للرأس {animal.animal_no}: 20 كجم",
        parsed_action_type="record_weight",
        parsed_payload_json=AssistantDraftAction.encode_payload({"target_animal_no": animal.animal_no, "weight": 20}),
        status="pending", created_by_id=created_by.id,
    )
    db.session.add(draft)
    db.session.commit()
    return draft


def test_worker_without_animals_view_only_sees_own_drafts(app, client, owner):
    worker = _make_worker()
    owner_draft = _make_draft(owner, animal_no="961")
    worker_draft = _make_draft(worker, animal_no="962")

    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/assistant/drafts")
    body = resp.data.decode()

    assert worker_draft.raw_text in body
    assert owner_draft.raw_text not in body


def test_owner_with_animals_view_sees_all_drafts(app, client, owner):
    worker = _make_worker(phone="0599999251")
    owner_draft = _make_draft(owner, animal_no="963")
    worker_draft = _make_draft(worker, animal_no="964")

    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/assistant/drafts")
    body = resp.data.decode()

    assert owner_draft.raw_text in body
    assert worker_draft.raw_text in body
