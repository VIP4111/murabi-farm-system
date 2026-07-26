from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required

from app.climate import climate_bp
from app.climate import climate_service as svc
from app.auth.decorators import require_permission
from app.extensions import db
from app.models import Barn, FarmSettings
from app.feed import feed_service


@climate_bp.route("/")
@login_required
@require_permission("climate.view")
def dashboard():
    forecast = svc.get_forecast()
    created_tasks = []
    if forecast["configured"] and forecast["readings"]:
        created_tasks = svc.generate_heat_checklists(forecast["readings"])
        if created_tasks:
            flash(
                f"⚠️ توقّع إجهاد حراري — تولّدت {len(created_tasks)} مهمة تفقّد مقترحة "
                f"بانتظار مراجعة الدكتور.",
                "warning",
            )

    heat_signals = []
    if forecast["readings"]:
        for barn in Barn.query.order_by(Barn.barn_no).all():
            signal = feed_service.heat_fcr_signal(barn_id=barn.id)
            if signal:
                heat_signals.append({"barn": barn, **signal})

    return render_template(
        "climate/dashboard.html",
        forecast=forecast,
        stress_labels=svc.STRESS_LABELS_AR,
        heat_signals=heat_signals,
    )


@climate_bp.route("/settings", methods=["GET", "POST"])
@login_required
@require_permission("climate.manage")
def settings():
    fs = FarmSettings.get()
    if request.method == "POST":
        try:
            lat = float(request.form["farm_latitude"])
            lon = float(request.form["farm_longitude"])
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                raise ValueError
        except (KeyError, ValueError):
            flash("إحداثيات غير صالحة.", "error")
            return redirect(url_for("climate.settings"))

        fs.farm_latitude = lat
        fs.farm_longitude = lon
        fs.thi_mild = float(request.form.get("thi_mild") or fs.thi_mild)
        fs.thi_moderate = float(request.form.get("thi_moderate") or fs.thi_moderate)
        fs.thi_severe = float(request.form.get("thi_severe") or fs.thi_severe)
        fs.thi_emergency = float(request.form.get("thi_emergency") or fs.thi_emergency)
        db.session.commit()
        flash("تم حفظ إعدادات رادار المناخ.", "success")
        return redirect(url_for("climate.dashboard"))

    return render_template("climate/settings.html", fs=fs)


@climate_bp.route("/refresh", methods=["POST"])
@login_required
@require_permission("climate.view")
def refresh():
    forecast = svc.get_forecast(force_refresh=True)
    if forecast["error"]:
        flash(f"تعذّر تحديث الطقس: {forecast['error']}", "error")
    else:
        flash("تم تحديث توقعات الطقس.", "success")
    return redirect(url_for("climate.dashboard"))
