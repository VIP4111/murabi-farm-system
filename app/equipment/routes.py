from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.equipment import equipment_bp
from app.equipment import equipment_service as svc
from app.auth.decorators import require_permission
from app.extensions import db
from app.models import Equipment, EquipmentMovement, Barn, User, Asset, AssetMaintenanceLog, UtilityReading
from datetime import date


@equipment_bp.route("/items")
@login_required
@require_permission("equipment.view")
def items_list():
    items = Equipment.query.order_by(Equipment.name).all()
    return render_template("equipment/items_list.html", items=items)


@equipment_bp.route("/items/new", methods=["GET", "POST"])
@login_required
@require_permission("equipment.manage")
def items_new():
    if request.method == "POST":
        item = Equipment(
            name=request.form["name"], category=request.form.get("category"),
            unit=request.form.get("unit") or "قطعة",
            unit_price=float(request.form["unit_price"]) if request.form.get("unit_price") else None,
            available_qty=float(request.form.get("available_qty") or 0),
            min_stock_qty=float(request.form.get("min_stock_qty") or 0),
            notes=request.form.get("notes"),
            photo_url=svc.save_equipment_photo(request.files.get("photo")),
        )
        db.session.add(item)
        db.session.commit()
        flash("تمت إضافة الصنف", "success")
        return redirect(url_for("equipment.items_list"))
    return render_template("equipment/item_form.html")


@equipment_bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("equipment.manage")
def items_edit(item_id):
    item = Equipment.query.get_or_404(item_id)
    if request.method == "POST":
        item.name = request.form["name"]
        item.category = request.form.get("category")
        item.unit = request.form.get("unit") or "قطعة"
        item.unit_price = float(request.form["unit_price"]) if request.form.get("unit_price") else None
        item.available_qty = float(request.form.get("available_qty") or 0)
        item.min_stock_qty = float(request.form.get("min_stock_qty") or 0)
        item.notes = request.form.get("notes")
        new_photo = svc.save_equipment_photo(request.files.get("photo"))
        if new_photo:
            item.photo_url = new_photo
        db.session.commit()
        flash("تم تحديث الصنف", "success")
        return redirect(url_for("equipment.items_list"))
    return render_template("equipment/item_form.html", item=item)


@equipment_bp.route("/items/<int:item_id>/movement", methods=["GET", "POST"])
@login_required
@require_permission("equipment.manage")
def items_movement(item_id):
    item = Equipment.query.get_or_404(item_id)
    if request.method == "POST":
        try:
            svc.record_movement(
                item=item, movement_type=request.form["movement_type"],
                quantity=float(request.form["quantity"]),
                barn_id=request.form.get("barn_id") or None,
                note=request.form.get("note"), created_by_id=current_user.id,
                borrowed_by_id=request.form.get("borrowed_by_id") or None,
            )
            flash("تم تسجيل الحركة", "success")
        except ValueError as e:
            flash(str(e), "error")
        return redirect(url_for("equipment.items_movement", item_id=item.id))
    movements = (EquipmentMovement.query.filter_by(equipment_id=item.id)
                 .order_by(EquipmentMovement.created_at.desc()).limit(50).all())
    return render_template(
        "equipment/item_movement.html", item=item, movements=movements,
        barns=Barn.query.order_by(Barn.barn_name).all(),
        users=User.query.filter_by(is_active_account=True).order_by(User.name).all(),
    )


@equipment_bp.route("/items/mine")
@login_required
@require_permission("equipment.view")
def items_mine():
    """شاشة العامل المبسّطة (بند إضافي 199) — بطاقات صور، ضغطة وحدة
    للأخذ أو الاسترجاع، بدون أي فورم أو حقول. تعمد استخدام `svc.record_movement`/
    `svc.return_item` نفسها المستخدمة بشاشة الإدارة الكاملة — بدون منطق مخزون
    مكرَّر، فقط واجهة مبسَّطة فوقها."""
    items = Equipment.query.filter_by(status="active").order_by(Equipment.name).all()
    rows = []
    for item in items:
        mine = svc.my_borrow(item, current_user.id)
        held_by_other = None
        if not mine:
            other = (EquipmentMovement.query
                     .filter_by(equipment_id=item.id, returned_at=None)
                     .filter(EquipmentMovement.borrowed_by_id.isnot(None))
                     .order_by(EquipmentMovement.created_at.desc()).first())
            if other and other.borrowed_by_id != current_user.id:
                held_by_other = other.borrowed_by
        rows.append({"item": item, "mine": mine, "held_by_other": held_by_other})
    return render_template("equipment/items_mine.html", rows=rows)


@equipment_bp.route("/items/<int:item_id>/take", methods=["POST"])
@login_required
@require_permission("equipment.view")
def items_take(item_id):
    """أخذ قطعة (بند إضافي 199) — استعارة كمية 1 باسم المستخدم الحالي
    فقط، بدون أي حقول تُملأ يدوياً. لا يحتاج صلاحية equipment.manage
    عمداً — العامل يسجّل استعارته لنفسه بس، ما يقدر يعدّل مخزون صنف
    ثاني أو باسم حد ثاني."""
    item = Equipment.query.get_or_404(item_id)
    try:
        svc.record_movement(
            item=item, movement_type="out", quantity=1,
            created_by_id=current_user.id, borrowed_by_id=current_user.id,
        )
        flash("تم تسجيل أخذك للقطعة", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("equipment.items_mine"))


@equipment_bp.route("/items/<int:item_id>/return-mine", methods=["POST"])
@login_required
@require_permission("equipment.view")
def items_return_mine(item_id):
    """استرجاع قطعة (بند إضافي 199) — يبحث عن استعارة المستخدم الحالي
    القائمة لهذي القطعة بنفسه، ما يقدر يرجّع استعارة حد ثاني."""
    item = Equipment.query.get_or_404(item_id)
    mine = svc.my_borrow(item, current_user.id)
    if not mine:
        flash("ما فيه استعارة قائمة لك بهذي القطعة", "error")
        return redirect(url_for("equipment.items_mine"))
    try:
        svc.return_item(mine)
        flash("تم تسجيل استرجاع القطعة", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("equipment.items_mine"))


@equipment_bp.route("/movements/<int:movement_id>/return", methods=["POST"])
@login_required
@require_permission("equipment.manage")
def movement_return(movement_id):
    """تسجيل استرجاع قطعة مستعارة (بند إضافي 110)."""
    movement = EquipmentMovement.query.get_or_404(movement_id)
    try:
        svc.return_item(movement)
        flash("تم تسجيل استرجاع القطعة", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("equipment.items_movement", item_id=movement.equipment_id))


# ---------- إدارة الأصول والصيانة الدورية (بند إضافي 186) ----------

@equipment_bp.route("/assets")
@login_required
@require_permission("equipment.view")
def assets_list():
    assets = Asset.query.filter_by(status="active").order_by(Asset.name).all()
    today = date.today()
    for a in assets:
        if a.maintenance_interval_days:
            reference = a.last_maintenance_date or a.created_at.date()
            from datetime import timedelta
            a.next_due = reference + timedelta(days=a.maintenance_interval_days)
            a.is_due = a.next_due <= today
        else:
            a.next_due = None
            a.is_due = False
    return render_template("equipment/assets_list.html", assets=assets)


@equipment_bp.route("/assets/new", methods=["GET", "POST"])
@login_required
@require_permission("equipment.manage")
def assets_new():
    if request.method == "POST":
        asset = Asset(
            name=request.form["name"], category=request.form.get("category") or "other",
            barn_id=request.form.get("barn_id") or None,
            maintenance_interval_days=int(request.form["maintenance_interval_days"]) if request.form.get("maintenance_interval_days") else None,
            notes=request.form.get("notes"),
        )
        db.session.add(asset)
        db.session.commit()
        flash("تمت إضافة الأصل", "success")
        return redirect(url_for("equipment.assets_list"))
    return render_template("equipment/asset_form.html", barns=Barn.query.order_by(Barn.barn_name).all())


@equipment_bp.route("/assets/<int:asset_id>/maintenance", methods=["GET", "POST"])
@login_required
@require_permission("equipment.manage")
def asset_maintenance(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    if request.method == "POST":
        maintenance_date = date.fromisoformat(request.form["date"])
        db.session.add(AssetMaintenanceLog(
            asset_id=asset.id, date=maintenance_date, notes=request.form.get("notes"),
            cost=float(request.form["cost"]) if request.form.get("cost") else None,
            performed_by_id=current_user.id,
        ))
        asset.last_maintenance_date = maintenance_date
        db.session.commit()
        flash("تم تسجيل الصيانة", "success")
        return redirect(url_for("equipment.asset_maintenance", asset_id=asset.id))
    logs = AssetMaintenanceLog.query.filter_by(asset_id=asset.id).order_by(AssetMaintenanceLog.date.desc()).all()
    return render_template("equipment/asset_maintenance.html", asset=asset, logs=logs, today=date.today().isoformat())


# ---------- استهلاك الطاقة والماء (بند إضافي 186) ----------

@equipment_bp.route("/utilities")
@login_required
@require_permission("equipment.view")
def utilities_list():
    readings = UtilityReading.query.order_by(UtilityReading.date.desc()).limit(60).all()
    return render_template("equipment/utilities_list.html", readings=readings)


@equipment_bp.route("/utilities/new", methods=["GET", "POST"])
@login_required
@require_permission("equipment.manage")
def utilities_new():
    if request.method == "POST":
        db.session.add(UtilityReading(
            utility_type=request.form["utility_type"], date=date.fromisoformat(request.form["date"]),
            quantity=float(request.form["quantity"]), unit=request.form.get("unit"),
            cost=float(request.form["cost"]) if request.form.get("cost") else None,
            notes=request.form.get("notes"),
        ))
        db.session.commit()
        flash("تم تسجيل القراءة", "success")
        return redirect(url_for("equipment.utilities_list"))
    return render_template("equipment/utility_form.html", today=date.today().isoformat())
