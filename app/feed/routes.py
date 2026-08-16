from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.feed import feed_bp
from app.feed import feed_service as svc
from app.auth.decorators import require_permission
from app.extensions import db
from app.models import Feed, FeedRation, FeedRationItem, FeedBarnPlan, FeedMovement, Barn, Animal, AuditLog

RATION_INGREDIENT_SLOTS = 6


# ---------- مكوّنات العلف ----------

@feed_bp.route("/items")
@login_required
@require_permission("feed.view")
def items_list():
    items = Feed.query.order_by(Feed.name).all()
    stockout = {f.id: svc.days_until_stockout(f) for f in items}
    return render_template(
        "feed/items_list.html", items=items, stockout=stockout,
        feed_class_labels=Feed.FEED_CLASS_LABELS_AR,
    )


@feed_bp.route("/items/new", methods=["GET", "POST"])
@login_required
@require_permission("feed.manage")
def items_new():
    if request.method == "POST":
        item = Feed(
            name=request.form["name"], category=request.form.get("category"),
            feed_class=request.form.get("feed_class") or None,
            contains_high_copper=bool(request.form.get("contains_high_copper")),
            protein_percent=float(request.form["protein_percent"]) if request.form.get("protein_percent") else None,
            energy_kcal_per_kg=float(request.form["energy_kcal_per_kg"]) if request.form.get("energy_kcal_per_kg") else None,
            fiber_percent=float(request.form["fiber_percent"]) if request.form.get("fiber_percent") else None,
            calcium_percent=float(request.form["calcium_percent"]) if request.form.get("calcium_percent") else None,
            phosphorus_percent=float(request.form["phosphorus_percent"]) if request.form.get("phosphorus_percent") else None,
            unit=request.form.get("unit") if request.form.get("unit") in Feed.UNITS else "كجم",
            unit_weight_kg=float(request.form["unit_weight_kg"]) if request.form.get("unit_weight_kg") else None,
            unit_price=float(request.form["unit_price"]) if request.form.get("unit_price") else None,
            available_qty=float(request.form.get("available_qty") or 0),
            min_stock_qty=float(request.form.get("min_stock_qty") or 0),
            notes=request.form.get("notes"),
        )
        db.session.add(item)
        db.session.commit()
        flash("تمت إضافة مكوّن العلف", "success")
        return redirect(url_for("feed.items_list"))
    return render_template(
        "feed/item_form.html",
        feed_classes=Feed.FEED_CLASSES, feed_class_labels=Feed.FEED_CLASS_LABELS_AR, units=Feed.UNITS,
    )


@feed_bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("feed.manage")
def items_edit(item_id):
    item = Feed.query.get_or_404(item_id)
    if request.method == "POST":
        item.name = request.form["name"]
        item.category = request.form.get("category")
        item.feed_class = request.form.get("feed_class") or None
        item.contains_high_copper = bool(request.form.get("contains_high_copper"))
        item.protein_percent = float(request.form["protein_percent"]) if request.form.get("protein_percent") else None
        item.energy_kcal_per_kg = float(request.form["energy_kcal_per_kg"]) if request.form.get("energy_kcal_per_kg") else None
        item.fiber_percent = float(request.form["fiber_percent"]) if request.form.get("fiber_percent") else None
        item.calcium_percent = float(request.form["calcium_percent"]) if request.form.get("calcium_percent") else None
        item.phosphorus_percent = float(request.form["phosphorus_percent"]) if request.form.get("phosphorus_percent") else None
        item.unit = request.form.get("unit") if request.form.get("unit") in Feed.UNITS else "كجم"
        item.unit_weight_kg = float(request.form["unit_weight_kg"]) if request.form.get("unit_weight_kg") else None
        item.unit_price = float(request.form["unit_price"]) if request.form.get("unit_price") else None
        item.available_qty = float(request.form.get("available_qty") or 0)
        item.min_stock_qty = float(request.form.get("min_stock_qty") or 0)
        item.notes = request.form.get("notes")
        db.session.commit()
        flash("تم تحديث مكوّن العلف", "success")
        return redirect(url_for("feed.items_list"))
    return render_template(
        "feed/item_form.html", item=item,
        feed_classes=Feed.FEED_CLASSES, feed_class_labels=Feed.FEED_CLASS_LABELS_AR, units=Feed.UNITS,
    )


# ---------- الوصفات ----------

@feed_bp.route("/rations")
@login_required
@require_permission("feed.view")
def rations_list():
    rations = FeedRation.query.order_by(FeedRation.name).all()
    profiles = {r.id: svc.ration_profile(r) for r in rations if r.items}
    return render_template("feed/rations_list.html", rations=rations, profiles=profiles)


@feed_bp.route("/rations/new", methods=["GET", "POST"])
@login_required
@require_permission("feed.manage")
def rations_new():
    if request.method == "POST":
        from app.models import FarmSettings

        ration = FeedRation(
            name=request.form["name"], purpose=request.form.get("purpose") or None,
            notes=request.form.get("notes"),
        )
        db.session.add(ration)
        db.session.flush()
        for i in range(RATION_INGREDIENT_SLOTS):
            feed_id = request.form.get(f"feed_id_{i}")
            percent = request.form.get(f"percent_{i}")
            if feed_id and percent:
                db.session.add(FeedRationItem(ration_id=ration.id, feed_id=int(feed_id), percent=float(percent)))
        db.session.flush()
        db.session.expire(ration, ["items"])

        override_reason = request.form.get("ratio_override_reason") or None
        ratio_warning = svc.ca_phosphorus_warning(svc.ration_profile(ration), FarmSettings.get()) if ration.items else None
        if ratio_warning and not override_reason:
            db.session.rollback()
            flash(ratio_warning["message"] + " اكتب سبب التجاوز بالحقل المخصص لو متأكد.", "warning")
            return redirect(url_for("feed.rations_new"))
        if ratio_warning and override_reason:
            db.session.add(AuditLog(
                actor_user_id=current_user.id, action="feed.ca_phosphorus_override",
                entity_type="FeedRation", entity_id=ration.id,
                details=f"نسبة {ratio_warning['ratio']}:1 — {override_reason}",
            ))

        db.session.add(AuditLog(actor_user_id=current_user.id, action="feed_ration.create",
                                 entity_type="FeedRation", entity_id=ration.id))
        db.session.commit()
        flash("تمت إضافة الوصفة", "success")
        return redirect(url_for("feed.ration_detail", ration_id=ration.id))
    return render_template(
        "feed/ration_form.html",
        feeds=Feed.query.filter_by(status="active").order_by(Feed.name).all(),
        slots=range(RATION_INGREDIENT_SLOTS),
    )


@feed_bp.route("/rations/<int:ration_id>")
@login_required
@require_permission("feed.view")
def ration_detail(ration_id):
    ration = FeedRation.query.get_or_404(ration_id)
    profile = svc.ration_profile(ration) if ration.items else None
    return render_template("feed/ration_detail.html", ration=ration, profile=profile)


# ---------- خطط تغذية الحظائر ----------

@feed_bp.route("/barn-plans")
@login_required
@require_permission("feed.view")
def barn_plans_list():
    plans = FeedBarnPlan.query.order_by(FeedBarnPlan.start_date.desc()).all()
    return render_template("feed/barn_plans_list.html", plans=plans)


@feed_bp.route("/barn-plans/new", methods=["GET", "POST"])
@login_required
@require_permission("feed.manage")
def barn_plans_new():
    if request.method == "POST":
        from app.models import FarmSettings

        barn_id = int(request.form["barn_id"])
        ration = FeedRation.query.get_or_404(int(request.form["ration_id"]))
        start_date_ = date.fromisoformat(request.form["start_date"])
        override_reason = request.form.get("increase_override_reason") or None

        warning = svc.concentrate_increase_warning(
            barn_id=barn_id, new_ration=ration, new_start_date=start_date_, fs=FarmSettings.get(),
        )
        if warning and not override_reason:
            flash(warning["message"] + " اكتب سبب التجاوز بالحقل المخصص لو متأكد.", "warning")
            return redirect(url_for("feed.barn_plans_new"))
        if warning and override_reason:
            db.session.add(AuditLog(
                actor_user_id=current_user.id, action="feed.concentrate_increase_override",
                entity_type="FeedBarnPlan", details=f"{warning['prior_percent']}% → {warning['new_percent']}% — {override_reason}",
            ))

        plan = FeedBarnPlan(
            barn_id=barn_id,
            ration_id=ration.id,
            daily_qty_per_animal_kg=float(request.form["daily_qty_per_animal_kg"]),
            start_date=start_date_,
            end_date=date.fromisoformat(request.form["end_date"]) if request.form.get("end_date") else None,
            notes=request.form.get("notes"),
        )
        db.session.add(plan)
        db.session.commit()
        flash("تمت إضافة خطة التغذية", "success")
        return redirect(url_for("feed.barn_plans_list"))
    return render_template(
        "feed/barn_plan_form.html",
        barns=Barn.query.order_by(Barn.barn_name).all(),
        rations=FeedRation.query.order_by(FeedRation.name).all(),
    )


# ---------- حركة المخزون ----------

@feed_bp.route("/purchase", methods=["GET", "POST"])
@login_required
@require_permission("feed.manage")
def purchase_new():
    """شراء علف موحّد (بند إضافي 203) — يزيد المخزون ويسجّل العملية
    المالية بضغطة وحدة، بدل ما تدخل من "حركة المخزون" و"المالية" كل
    مرة لحالها. يحتاج صلاحية إدارة العلف **و** المالية معاً — أي زيادة
    مخزون مربوطة هنا بمبلغ فعلي يخرج من حساب المزرعة."""
    if not current_user.has_permission("finance.full.manage"):
        flash("تحتاج صلاحية إدارة المالية كمان عشان تسجّل شراء (يُنشئ عملية مالية).", "error")
        return redirect(url_for("feed.items_list"))
    if request.method == "POST":
        feed = Feed.query.get_or_404(int(request.form["feed_id"]))
        try:
            from app.core.stock_purchase_service import record_purchase
            record_purchase(
                kind="feed", item=feed,
                quantity=float(request.form["quantity"]),
                unit_price=float(request.form["unit_price"]),
                purchase_date=date.fromisoformat(request.form["date"]),
                invoice_file=request.files.get("invoice_file"),
                note=request.form.get("note"), created_by_id=current_user.id,
            )
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("feed.purchase_new"))
        flash("تم تسجيل الشراء — زاد المخزون وانسجلت العملية المالية معاً", "success")
        return redirect(url_for("feed.items_list"))
    return render_template(
        "feed/purchase_form.html",
        feeds=Feed.query.filter_by(status="active").order_by(Feed.name).all(),
    )


@feed_bp.route("/movements")
@login_required
@require_permission("feed.view")
def movements_list():
    rows = FeedMovement.query.order_by(FeedMovement.created_at.desc()).limit(200).all()
    return render_template("feed/movements_list.html", rows=rows)


@feed_bp.route("/movements/new", methods=["GET", "POST"])
@login_required
@require_permission("feed.manage")
def movements_new():
    if request.method == "POST":
        feed = Feed.query.get_or_404(int(request.form["feed_id"]))
        try:
            svc.record_movement(
                feed=feed, movement_type=request.form["movement_type"],
                quantity=float(request.form["quantity"]),
                barn_id=request.form.get("barn_id") or None,
                animal_id=request.form.get("animal_id") or None,
                note=request.form.get("note"), created_by_id=current_user.id,
            )
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("feed.movements_new"))
        flash("تم تسجيل حركة المخزون", "success")
        return redirect(url_for("feed.movements_list"))
    return render_template(
        "feed/movement_form.html",
        feeds=Feed.query.filter_by(status="active").order_by(Feed.name).all(),
        barns=Barn.query.order_by(Barn.barn_name).all(),
        animals=Animal.query.order_by(Animal.animal_no).all(),
    )


# ---------- معدل التحويل الغذائي FCR (بند إضافي، 2026-07-24) ----------

@feed_bp.route("/fcr", methods=["GET", "POST"])
@login_required
@require_permission("feed.view")
def fcr_report():
    result = None
    animal_breakdown = None
    barn_id = None
    start_date = None
    end_date = None
    if request.method == "POST":
        barn_id = int(request.form["barn_id"])
        start_date = date.fromisoformat(request.form["start_date"])
        end_date = date.fromisoformat(request.form["end_date"])
        result = svc.calculate_fcr(barn_id=barn_id, start_date=start_date, end_date=end_date)
        animal_breakdown = svc.calculate_fcr_by_animal(barn_id=barn_id, start_date=start_date, end_date=end_date)

    return render_template(
        "feed/fcr_report.html",
        barns=Barn.query.order_by(Barn.barn_name).all(),
        result=result, animal_breakdown=animal_breakdown,
        barn_id=barn_id, start_date=start_date, end_date=end_date,
        today=date.today().isoformat(),
    )


# ---------- موازِن العليقة التلقائي (بند إضافي، 2026-07-24) ----------

@feed_bp.route("/optimizer", methods=["GET", "POST"])
@login_required
@require_permission("feed.view")
def optimizer():
    result = None
    requirement = None
    selected_animal = None
    current_daily_cost = None
    daily_savings = None
    if request.method == "POST":
        animal_id = request.form.get("animal_id")
        state = request.form.get("state")
        if animal_id:
            selected_animal = Animal.query.get(int(animal_id))
            weight = selected_animal.weight
            if not state:
                state = svc.infer_physiological_state(selected_animal)
        else:
            weight = float(request.form["weight"])
            state = state or "maintenance"

        if weight:
            requirement = svc.daily_requirement(weight_kg=weight, state=state)
            usable_feeds = Feed.query.filter_by(status="active").all()
            result = svc.optimize_blend(requirement=requirement, feeds=usable_feeds)
            barn_id = selected_animal.barn_id if selected_animal else None
            current_daily_cost = svc.current_barn_daily_cost_per_head(barn_id)
            if current_daily_cost is not None and result and result.get("feasible"):
                daily_savings = round(current_daily_cost - result["total_daily_cost"], 3)
        else:
            flash("الحيوان المختار ما له وزن مسجّل — أدخل وزن يدوي", "error")

    return render_template(
        "feed/optimizer.html",
        animals=Animal.query.filter_by(status="active").order_by(Animal.animal_no).all(),
        states=svc.PHYSIOLOGICAL_TARGETS.keys(),
        requirement=requirement, result=result, selected_animal=selected_animal,
        current_daily_cost=current_daily_cost, daily_savings=daily_savings,
    )


# ---------- حاسبة الاحتياج اليومي ----------

@feed_bp.route("/calculator", methods=["GET", "POST"])
@login_required
@require_permission("feed.view")
def calculator():
    result = None
    recommendations = None
    selected_animal = None
    if request.method == "POST":
        animal_id = request.form.get("animal_id")
        state = request.form.get("state")
        if animal_id:
            selected_animal = Animal.query.get(int(animal_id))
            weight = selected_animal.weight
            if not state:
                state = svc.infer_physiological_state(selected_animal)
        else:
            weight = float(request.form["weight"])
            state = state or "maintenance"

        if weight:
            result = svc.daily_requirement(weight_kg=weight, state=state)
            recommendations = svc.recommend_rations(requirement=result)
        else:
            flash("الحيوان المختار ما له وزن مسجّل — أدخل وزن يدوي", "error")

    return render_template(
        "feed/calculator.html",
        animals=Animal.query.filter_by(status="active").order_by(Animal.animal_no).all(),
        states=svc.PHYSIOLOGICAL_TARGETS.keys(),
        result=result, recommendations=recommendations, selected_animal=selected_animal,
    )
