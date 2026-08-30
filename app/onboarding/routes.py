from datetime import datetime, timezone
from flask import render_template, request, redirect, url_for, flash
from flask_babel import gettext as _
from flask_login import login_required, current_user

from app.onboarding import onboarding_bp
from app.core import checklist_service
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
    return render_template("onboarding/welcome.html", steps=steps)


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
