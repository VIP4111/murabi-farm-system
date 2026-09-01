"""بند إضافي (2026-09-01، طلبك المباشر: "احتاج صفحة خاصة فيه اساسيات
بداية انشاء المزرعه مابي ابتدي بنواقص تعطيني اياها بترتيب... زر قدام
كل امر... وفي الاخير تجيني رساله تقول مزرعتك جاهزه تبتدي فيها الان")
— شاشة مخصَّصة (`/onboarding/setup-checklist`) تعيد استخدام
`setup_checklist_service` (كان مبنياً من قبل لكن يتيماً بالكود، غير
مستخدم بأي شاشة) — وسّعناه بأيقونة/وصف/بندين إضافيين (كلمة المرور،
بيانات المزرعة) وبنينا له شاشة فعلية."""
from app.extensions import db
from app.core import setup_checklist_service


def test_setup_checklist_items_start_all_undone_for_fresh_owner(app, owner):
    items = setup_checklist_service.get_setup_checklist_items(owner)
    assert not setup_checklist_service.all_done(items)
    codes = {i["code"] for i in items}
    assert {"password", "farm_identity", "first_barn", "first_animal",
            "team_member", "first_medicine", "first_feed", "first_backup"} <= codes


def test_first_feed_item_not_done_just_from_seeded_reference_library(app, owner):
    """بند إضافي (2026-09-01) — بلّغ المستخدم بصورة شاشة حقيقية: "أضف أول
    صنف علف" كان معلَّماً ✅ بحساب جديد تماماً بدون ما يسجّل أي شي بنفسه.
    السبب: `flask seed` يعبّي مكتبة أعلاف مرجعية افتراضية (DEFAULT_FEED_LIBRARY،
    بند 189) تلقائياً بكل تركيب جديد — Feed.query.count() > 0 صار
    صحيحاً دايماً بغض النظر عن أي فعل حقيقي من المستخدم. الإصلاح:
    التحقق من FeedMovement حقيقية (حركة شراء/صرف فعلية) بدل وجود صف
    بجدول Feed المرجعي."""
    from app.models import Feed

    db.session.add(Feed(name="علف مرجعي بس", category="مركّز"))
    db.session.commit()

    items = setup_checklist_service.get_setup_checklist_items(owner)
    feed_item = next(i for i in items if i["code"] == "first_feed")
    assert feed_item["done"] is False


def test_first_feed_item_done_after_real_feed_movement_recorded(app, owner):
    from app.models import Feed, FeedMovement

    feed = Feed(name="علف اختبار حركة", category="مركّز")
    db.session.add(feed)
    db.session.commit()
    db.session.add(FeedMovement(feed_id=feed.id, movement_type="in", quantity=50))
    db.session.commit()

    items = setup_checklist_service.get_setup_checklist_items(owner)
    feed_item = next(i for i in items if i["code"] == "first_feed")
    assert feed_item["done"] is True


def test_password_item_done_after_owner_changes_password(app, owner):
    owner.set_password("a-real-new-password-999")
    db.session.commit()
    items = setup_checklist_service.get_setup_checklist_items(owner)
    password_item = next(i for i in items if i["code"] == "password")
    assert password_item["done"] is True


def test_farm_identity_item_done_after_farm_name_set(app, owner):
    from app.models import FarmSettings
    fs = FarmSettings.get()
    fs.farm_name = "مزرعة الاختبار"
    db.session.commit()
    items = setup_checklist_service.get_setup_checklist_items(owner)
    identity_item = next(i for i in items if i["code"] == "farm_identity")
    assert identity_item["done"] is True


def test_first_barn_item_done_after_creating_a_barn(app, owner):
    from tests.factories import make_barn
    make_barn(barn_no="SETUP-01")
    items = setup_checklist_service.get_setup_checklist_items(owner)
    barn_item = next(i for i in items if i["code"] == "first_barn")
    assert barn_item["done"] is True


def test_all_items_done_reports_all_done_true(app, owner):
    from tests.factories import make_barn, make_animal
    from app.models import FarmSettings, Role, User, Pharmacy, Feed, FeedMovement, AuditLog

    owner.set_password("a-real-new-password-999")
    fs = FarmSettings.get()
    fs.farm_name = "مزرعة كاملة"
    make_barn(barn_no="SETUP-02")
    make_animal(animal_no="SETUP-ANIMAL")
    role = Role.query.filter_by(name="worker").first()
    extra = User(name="عامل اختبار", phone="0599999295", role_id=role.id)
    extra.set_password("pass1234")
    db.session.add(extra)
    db.session.add(Pharmacy(name="دواء اختبار", available_qty=10, unit="مل"))
    feed = Feed(name="علف اختبار", category="مركّز")
    db.session.add(feed)
    db.session.commit()
    db.session.add(FeedMovement(feed_id=feed.id, movement_type="in", quantity=20))
    db.session.add(AuditLog(actor_user_id=owner.id, action="backup.export_json", entity_type="Backup"))
    db.session.commit()

    items = setup_checklist_service.get_setup_checklist_items(owner)
    assert setup_checklist_service.all_done(items) is True


def test_setup_checklist_page_renders_with_action_links(app, logged_in_client):
    resp = logged_in_client.get("/onboarding/setup-checklist")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "أساسيات بداية إنشاء المزرعة" in body
    assert "سوّها الآن" in body
    assert "مزرعتك جاهزة" not in body  # لسا فيه نواقص بحساب اختبار جديد


def test_home_page_shows_setup_checklist_banner_for_owner_when_pending(app, logged_in_client):
    resp = logged_in_client.get("/")
    body = resp.data.decode()
    assert "أساسيات بداية إنشاء المزرعة" in body
    assert "/onboarding/setup-checklist" in body


def test_dismiss_hides_banner_from_home_page(app, logged_in_client):
    logged_in_client.post("/setup-checklist/dismiss")
    resp = logged_in_client.get("/")
    body = resp.data.decode()
    assert "أساسيات بداية إنشاء المزرعة" not in body


def test_worker_does_not_see_setup_checklist_banner(app, client, worker):
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/")
    assert "أساسيات بداية إنشاء المزرعة" not in resp.data.decode()
