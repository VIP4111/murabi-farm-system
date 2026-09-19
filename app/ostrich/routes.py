from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_babel import gettext as _
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from app.ostrich import ostrich_bp
from app.core import ostrich_service as svc
from app.core import validation_service
from app.auth.decorators import require_permission
from app.extensions import db, farm_today
from app.models import Animal, FarmSettings
from app.models.ostrich import Incubator, OstrichEgg


# ---------- البيض ----------

@ostrich_bp.route("/eggs")
@login_required
@require_permission("repro.view")
def eggs_list():
    status = request.args.get("status", "all")
    # بند إصلاح (فحص شامل سطر بسطر — ميزة النعام) — mother/incubator/
    # hatched_animal تُعرض لكل صف بالقالب بدون تحميل مسبق.
    query = (OstrichEgg.query
             .options(joinedload(OstrichEgg.mother), joinedload(OstrichEgg.incubator),
                      joinedload(OstrichEgg.hatched_animal))
             .order_by(OstrichEgg.lay_date.desc()))
    if status != "all":
        query = query.filter_by(hatch_result=status)
    eggs = query.all()
    fs = FarmSettings.get()
    expected = {e.id: svc.expected_hatch_date(e, fs.ostrich_incubation_days) for e in eggs}
    incubators = Incubator.query.filter_by(status="active").order_by(Incubator.code).all()
    return render_template("ostrich/eggs_list.html", eggs=eggs, status=status, expected=expected, incubators=incubators)


@ostrich_bp.route("/eggs/new", methods=["GET", "POST"])
@login_required
@require_permission("repro.manage")
def eggs_new():
    if request.method == "POST":
        # بند إصلاح (فحص شامل سطر بسطر — ميزة النعام) — وزن البيضة كان
        # يُحفَظ بلا أي فحص (سالب أو رقم غير منطقي)، ورقم الأم ما كان
        # يُتحقَّق إنه فعلاً أنثى نعام نشطة موجودة (القائمة المنسدلة
        # تفلتر بالواجهة بس — طلب POST مباشر يقدر يمرّر أي رقم رأس).
        try:
            mother_id = int(request.form["mother_id"])
            mother = Animal.query.filter_by(id=mother_id, species="ostrich", gender="أنثى",
                                             status="active").first()
            if not mother:
                raise ValueError(_("الأم المحدَّدة غير صالحة — لازم تكون أنثى نعام نشطة."))
            weight_grams = float(request.form["weight_grams"]) if request.form.get("weight_grams") else None
            if weight_grams is not None:
                validation_service.validate_price(weight_grams, field_label=_("وزن البيضة"))
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("ostrich.eggs_new"))
        svc.register_egg(
            mother_id=mother_id,
            lay_date=date.fromisoformat(request.form["lay_date"]),
            quality=request.form.get("quality") or None,
            weight_grams=weight_grams,
            notes=request.form.get("notes") or None,
        )
        flash(_("تم تسجيل البيضة"), "success")
        return redirect(url_for("ostrich.eggs_list"))
    mothers = Animal.query.filter_by(species="ostrich", gender="أنثى", status="active").order_by(Animal.animal_no).all()
    return render_template("ostrich/egg_form.html", mothers=mothers, today=farm_today().isoformat())


@ostrich_bp.route("/eggs/<int:egg_id>/place", methods=["POST"])
@login_required
@require_permission("repro.manage")
def eggs_place(egg_id):
    egg = OstrichEgg.query.get_or_404(egg_id)
    try:
        svc.place_in_incubator(
            egg, incubator_id=int(request.form["incubator_id"]),
            incubation_start_date=date.fromisoformat(request.form["incubation_start_date"]),
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("ostrich.eggs_list"))
    flash(_("تم إدخال البيضة للحاضنة"), "success")
    return redirect(url_for("ostrich.eggs_list"))


@ostrich_bp.route("/eggs/<int:egg_id>/hatch", methods=["GET", "POST"])
@login_required
@require_permission("repro.manage")
def eggs_hatch(egg_id):
    egg = OstrichEgg.query.get_or_404(egg_id)
    if request.method == "POST":
        result = request.form["hatch_result"]
        if result == "hatched":
            try:
                svc.record_hatch_success(
                    egg,
                    actual_hatch_date=date.fromisoformat(request.form["actual_hatch_date"]),
                    animal_no=request.form["animal_no"].strip(),
                    gender=request.form.get("gender") or None,
                    weight=float(request.form["weight"]) if request.form.get("weight") else None,
                    actor_user_id=current_user.id,
                )
                flash(_("تم تسجيل الفقس وإضافة الفرخ كرأس جديد"), "success")
            except Exception as e:
                db.session.rollback()
                flash(_("تعذّر تسجيل الفقس: %(err)s", err=e), "error")
                return redirect(url_for("ostrich.eggs_hatch", egg_id=egg.id))
        else:
            try:
                svc.record_hatch_failure(egg, fail_reason=request.form.get("fail_reason") or "-", actor_user_id=current_user.id)
                flash(_("تم تسجيل فشل الفقس"), "success")
            except svc.OstrichEggAlreadyProcessedError as e:
                flash(str(e), "error")
                return redirect(url_for("ostrich.eggs_list"))
        return redirect(url_for("ostrich.eggs_list"))
    fs = FarmSettings.get()
    return render_template(
        "ostrich/egg_hatch_form.html", egg=egg, today=farm_today().isoformat(),
        expected=svc.expected_hatch_date(egg, fs.ostrich_incubation_days),
    )


# ---------- الحاضنات ----------

@ostrich_bp.route("/incubators")
@login_required
@require_permission("repro.view")
def incubators_list():
    incubators = Incubator.query.order_by(Incubator.code).all()
    return render_template("ostrich/incubators_list.html", incubators=incubators)


@ostrich_bp.route("/incubators/new", methods=["GET", "POST"])
@login_required
@require_permission("repro.manage")
def incubators_new():
    if request.method == "POST":
        # بند إصلاح (فحص شامل سطر بسطر — ميزة النعام) — السعة ما كانت
        # تُفحَص (صفر أو رقم سالب كان يُحفَظ بصمت).
        capacity = int(request.form["capacity"]) if request.form.get("capacity") else None
        if capacity is not None and capacity <= 0:
            flash(_("سعة الحاضنة لازم تكون رقماً موجباً أكبر من صفر."), "error")
            return redirect(url_for("ostrich.incubators_new"))
        svc.create_incubator(
            code=request.form["code"].strip(),
            name=request.form.get("name") or None,
            capacity=capacity,
            notes=request.form.get("notes") or None,
        )
        flash(_("تمت إضافة الحاضنة"), "success")
        return redirect(url_for("ostrich.incubators_list"))
    return render_template("ostrich/incubator_form.html")
