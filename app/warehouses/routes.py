from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.warehouses import warehouses_bp
from app.core import warehouse_service as wsvc
from app.models import Warehouse, Feed, Pharmacy


def _require_feed_or_pharmacy_manage():
    if not (current_user.has_permission("feed.manage") or current_user.has_permission("pharmacy.manage")):
        abort(403)


def _require_kind_manage(kind):
    code = "feed.manage" if kind == "feed" else "pharmacy.manage"
    if not current_user.has_permission(code):
        abort(403)


@warehouses_bp.route("/")
@login_required
def warehouses_list():
    _require_feed_or_pharmacy_manage()
    warehouses = Warehouse.query.filter_by(is_default=False).order_by(Warehouse.name).all()
    return render_template(
        "warehouses/warehouses_list.html", warehouses=warehouses,
        type_labels=Warehouse.WAREHOUSE_TYPE_LABELS_AR,
    )


@warehouses_bp.route("/new", methods=["GET", "POST"])
@login_required
def warehouses_new():
    _require_feed_or_pharmacy_manage()
    if request.method == "POST":
        warehouse = Warehouse(
            name=request.form["name"],
            warehouse_type=request.form["warehouse_type"],
            location_note=request.form.get("location_note") or None,
        )
        from app.extensions import db
        db.session.add(warehouse)
        db.session.commit()
        flash(f'تم إنشاء مستودع "{warehouse.name}"', "success")
        return redirect(url_for("warehouses.warehouses_list"))
    return render_template(
        "warehouses/warehouse_form.html", types=Warehouse.WAREHOUSE_TYPES,
        type_labels=Warehouse.WAREHOUSE_TYPE_LABELS_AR,
    )


@warehouses_bp.route("/item/<kind>/<int:item_id>")
@login_required
def item_breakdown(kind, item_id):
    _require_kind_manage(kind)
    Model = Feed if kind == "feed" else Pharmacy
    item = Model.query.get_or_404(item_id)
    breakdown = wsvc.warehouse_breakdown(item, kind)
    all_warehouses = Warehouse.query.filter(
        (Warehouse.warehouse_type == kind) | (Warehouse.warehouse_type == "mixed")
    ).order_by(Warehouse.is_default.desc(), Warehouse.name).all()
    return render_template(
        "warehouses/item_breakdown.html", item=item, kind=kind,
        breakdown=breakdown, all_warehouses=all_warehouses,
    )


@warehouses_bp.route("/item/<kind>/<int:item_id>/transfer", methods=["POST"])
@login_required
def item_transfer(kind, item_id):
    _require_kind_manage(kind)
    try:
        wsvc.transfer_stock(
            kind=kind, item_id=item_id,
            from_warehouse_id=int(request.form["from_warehouse_id"]),
            to_warehouse_id=int(request.form["to_warehouse_id"]),
            qty=float(request.form["qty"]),
            actor_user_id=current_user.id,
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("warehouses.item_breakdown", kind=kind, item_id=item_id))
    flash("تم التحويل بين المستودعين.", "success")
    return redirect(url_for("warehouses.item_breakdown", kind=kind, item_id=item_id))
