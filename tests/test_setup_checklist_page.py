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


def test_first_feed_item_points_to_purchase_screen_not_consumption_form(app, owner):
    """بند إضافي 213 — اختبار تسلسل المستخدم الجديد: بند "أول حركة علف" كان
    يودّي لنموذج "حركة مخزون" اللي افتراضيه "صادر" (توزيع) ومخزون 0 — مستخدم
    جديد يعلق. الشراء (وارد) له شاشة مخصصة، فالبند يودّي لها مباشرة."""
    items = setup_checklist_service.get_setup_checklist_items(owner)
    feed_item = next(i for i in items if i["code"] == "first_feed")
    assert feed_item["endpoint"] == "feed.purchase_new"
    assert "شراء" in feed_item["label"]


def test_saving_a_checklist_item_returns_to_the_checklist(logged_in_client, app):
    """بند إضافي 213 — بعد الحفظ بنجاح من ضغطة "سوّها الآن" يرجع للقائمة
    (كان يبقى بشاشة الحظيرة ويضطر يفتح القائمة من جديد لكل بند)."""
    go = logged_in_client.get("/onboarding/setup-checklist/go/first_barn")
    assert go.status_code == 302 and go.headers["Location"].endswith("/barns/new")

    resp = logged_in_client.post("/barns/new", data={
        "barn_no": "SC-01", "barn_name": "حظيرة القائمة", "meal_time": ["07:00"],
    })
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/onboarding/setup-checklist")


def test_failed_save_does_not_return_to_the_checklist(logged_in_client, app):
    """لو الحفظ فشل (رقم حظيرة مكرر) يبقى بالنموذج يصحّح — ما نرجّعه للقائمة."""
    logged_in_client.post("/barns/new", data={"barn_no": "SC-02", "barn_name": "أولى", "meal_time": ["07:00"]})
    logged_in_client.get("/onboarding/setup-checklist/go/first_barn")
    resp = logged_in_client.post("/barns/new", data={"barn_no": "SC-02", "barn_name": "مكررة", "meal_time": ["07:00"]})
    assert not resp.headers.get("Location", "").endswith("/onboarding/setup-checklist")


def test_normal_save_without_checklist_click_is_unchanged(logged_in_client, app):
    """من خارج القائمة (دخول عادي لشاشة الحظائر) الحفظ يسلك مساره المعتاد."""
    resp = logged_in_client.post("/barns/new", data={"barn_no": "SC-03", "barn_name": "عادية", "meal_time": ["07:00"]})
    assert resp.status_code == 302
    assert not resp.headers["Location"].endswith("/onboarding/setup-checklist")


def test_checklist_go_unknown_code_is_404(logged_in_client):
    assert logged_in_client.get("/onboarding/setup-checklist/go/nope").status_code == 404


def test_home_merges_tour_and_setup_banners_into_one_card_with_progress(logged_in_client, app):
    """بند إضافي 213 — كان بنرين منفصلين (جولة + أساسيات الإنشاء) فوق بعض.
    الحين كرت واحد فيه الاثنين، مع عدّاد التقدّم (X من Y مكتمل)."""
    import re
    html = logged_in_client.get("/").data.decode()
    assert html.count("أول مرة تستخدم النظام") == 1
    assert html.count("أساسيات بداية إنشاء المزرعة") == 1
    assert re.search(r"\d+ من \d+ مكتمل", html)
    # الاثنين داخل نفس الكرت: ما فيه </div> كرت منفصل بينهم (فاصل hr بدلاً منه)
    assert 'border-top:1px solid var(--line)' in html


def test_farm_identity_item_jumps_straight_to_its_form(logged_in_client, app):
    """بند إضافي 213 — بند بيانات المزرعة يفتح الإعدادات على نموذجه مباشرة
    (anchor) بدل الصفحة الطويلة من أولها."""
    go = logged_in_client.get("/onboarding/setup-checklist/go/farm_identity")
    assert go.status_code == 302 and go.headers["Location"].endswith("/settings#farm-identity")
    assert 'id="farm-identity"' in logged_in_client.get("/settings").data.decode()
