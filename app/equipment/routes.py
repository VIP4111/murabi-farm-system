from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.equipment import equipment_bp
from app.equipment import equipment_service as svc
from app.auth.decorators import require_permission
from app.extensions import db
from app.models import Equipment, EquipmentMovement, Barn


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
            )
            flash("تم تسجيل الحركة", "success")
        except ValueError as e:
            flash(str(e), "error")
        return redirect(url_for("equipment.items_movement", item_id=item.id))
    movements = (EquipmentMovement.query.filter_by(equipment_id=item.id)
                 .order_by(EquipmentMovement.created_at.desc()).limit(50).all())
    return render_template("equipment/item_movement.html", item=item, movements=movements,
                            barns=Barn.query.order_by(Barn.barn_name).all())
