from datetime import datetime, timezone
from flask import render_template, request, redirect, url_for, flash, session, abort
from flask_babel import gettext as _
from flask_login import login_required, current_user

from app.onboarding import onboarding_bp
from app.core import checklist_service, setup_checklist_service
from app.extensions import db


@onboarding_bp.route("/welcome", methods=["GET", "POST"])
@login_required
def welcome():
    """مسار الترحيب أول دخول (بند إضافي 168) — يظهر تلقائياً لأي
    مستخدم ما أنهى الترحيب بعد (`onboarding_completed_at` فاضي)،
    ويسأله صراحة "أنت مبتدئ؟" بدل ما ينتظر يفعّلها من الإعدادات."""
    if request.method == "POST":
        current_user.is_beginner = request.form.get("is_beginner") == "1"
        current_user.onboarding_completed_at = datetime.now(timezone.utc)
        db.session.commit()
        flash(_("تم — دليلك اليومي جاهز بالصفحة الرئيسية"), "success")
        return redirect(url_for("core.home"))
    steps = checklist_service.onboarding_steps_for(current_user)
    tour_groups = checklist_service.permission_tour_grouped(current_user)
    return render_template("onboarding/welcome.html", steps=steps, tour_groups=tour_groups)


@onboarding_bp.route("/skip", methods=["POST"])
@login_required
def skip():
    current_user.onboarding_completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return redirect(url_for("core.home"))


@onboarding_bp.route("/checklist")
@login_required
def checklist():
    rows = checklist_service.daily_checklist_for(current_user)
    return render_template("onboarding/checklist.html", rows=rows)


@onboarding_bp.route("/checklist/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle(item_id):
    checklist_service.toggle_completion(current_user, item_id)
    next_url = request.form.get("next") or url_for("onboarding.checklist")
    return redirect(next_url)


@onboarding_bp.route("/setup-checklist")
@login_required
def setup_checklist_page():
    """شاشة "أساسيات بداية إنشاء المزرعة" (بند إضافي 2026-09-01، طلبك
    المباشر) — قائمة نواقص مرتبة، كل بند له زر إجراء مباشر يوديك لنفس
    الشاشة اللي تكمّل فيها الناقص. لما تكتمل كلها، تظهر رسالة "مزرعتك
    جاهزة" بدل القائمة."""
    session.pop(SETUP_RETURN_KEY, None)
    items = setup_checklist_service.get_setup_checklist_items_with_urls(current_user)
    for item in items:
        item["go_url"] = url_for("onboarding.setup_checklist_go", code=item["code"])
    return render_template("onboarding/setup_checklist.html", items=items,
                            all_done=setup_checklist_service.all_done(items))


# بند إضافي 213 — اختبار تسلسل المستخدم الجديد: بعد ما يحفظ بند من القائمة
# كان يبقى بشاشة الإعدادات/الحظيرة وما يرجع للقائمة، ويضطر يفتحها من جديد
# لكل بند. الحل: ضغطة "سوّها الآن" تمرّ من هنا وتتذكّر البند، وإذا
# انحفظ بنجاح (رسالة نجاح) نرجّعه للقائمة. فشل الحفظ ما يرجّع — يبقى
# بالنموذج يصحّح.
SETUP_RETURN_KEY = "setup_checklist_return"
SETUP_RETURN_ENDPOINTS = {
    "password": {"team.members_edit"},
    "farm_identity": {"core.farm_identity_save"},
    "first_barn": {"core.barns_new"},
    "first_animal": {"core.animals_new"},
    "team_member": {"team.members_new"},
    "first_medicine": {"health.pharmacy_new"},
    "first_feed": {"feed.purchase_new"},
    "first_backup": {"core.backup_create"},
}


@onboarding_bp.route("/setup-checklist/go/<code>")
@login_required
def setup_checklist_go(code):
    items = {i["code"]: i for i in setup_checklist_service.get_setup_checklist_items_with_urls(current_user)}
    item = items.get(code)
    if item is None:
        abort(404)
    session[SETUP_RETURN_KEY] = code
    return redirect(item["url"])


@onboarding_bp.after_app_request
def _return_to_setup_checklist_after_save(response):
    code = session.get(SETUP_RETURN_KEY)
    if not code or request.method != "POST" or response.status_code not in (301, 302, 303):
        return response
    if request.endpoint not in SETUP_RETURN_ENDPOINTS.get(code, set()):
        return response
    flashes = session.get("_flashes") or []
    if not flashes or flashes[-1][0] != "success":
        return response
    session.pop(SETUP_RETURN_KEY, None)
    response.headers["Location"] = url_for("onboarding.setup_checklist_page")
    return response
