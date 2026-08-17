from datetime import date
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.warehouses import warehouses_bp
from app.core import warehouse_service as wsvc
from app.core import inventory_count_service as csvc
from app.models import Warehouse, Feed, Pharmacy, Equipment, InventoryCount


def _require_feed_or_pharmacy_manage():
    if not (current_user.has_permission("feed.manage") or current_user.has_permission("pharmacy.manage")):
        abort(403)


_KIND_PERMISSION = {"feed": "feed.manage", "pharmacy": "pharmacy.manage", "equipment": "equipment.manage"}


def _require_kind_manage(kind):
    code = _KIND_PERMISSION.get(kind, "feed.manage")
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


@warehouses_bp.route("/item/<kind>/<int:item_id>/count", methods=["GET", "POST"])
@login_required
def item_count(kind, item_id):
    """جرد فعلي لصنف واحد (بند إضافي 208) — يقارن الرصيد المحسوب
    بالنظام بالكمية الفعلية بالميزان، ويصحح المخزون تلقائياً؛ النقص
    يُسجَّل هالك (مصروف غير مباشر) والزيادة تصحيح مخزون بس."""
    if kind not in csvc.KIND_MODELS:
        abort(404)
    _require_kind_manage(kind)
    item = csvc.KIND_MODELS[kind].query.get_or_404(item_id)
    if request.method == "POST":
        try:
            rec = csvc.record_count(
                kind=kind, item=item,
                actual_qty=float(request.form["actual_qty"]),
                count_date=date.fromisoformat(request.form["count_date"]) if request.form.get("count_date") else None,
                note=request.form.get("note"), created_by_id=current_user.id,
            )
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("warehouses.item_count", kind=kind, item_id=item_id))
        if rec.diff_qty < 0:
            flash(f"تم تسجيل الجرد — نقص {abs(rec.diff_qty)} احتُسب هالك بقيمة {rec.diff_value} ريال.", "error")
        elif rec.diff_qty > 0:
            flash(f"تم تسجيل الجرد — زيادة {rec.diff_qty} أُضيفت للمخزون.", "success")
        else:
            flash("تم تسجيل الجرد — الرصيد مطابق تماماً.", "success")
        return redirect(url_for("warehouses.inventory_counts_list"))
    return render_template(
        "warehouses/item_count_form.html", item=item, kind=kind,
        kind_label=csvc.KIND_LABELS_AR[kind], today=date.today().isoformat(),
    )


@warehouses_bp.route("/inventory-counts")
@login_required
def inventory_counts_list():
    if not (current_user.has_permission("feed.manage") or current_user.has_permission("pharmacy.manage")
            or current_user.has_permission("equipment.manage")):
        abort(403)
    rows = InventoryCount.query.order_by(InventoryCount.count_date.desc(), InventoryCount.id.desc()).limit(200).all()
    return render_template(
        "warehouses/inventory_counts_list.html", rows=rows, kind_labels=csvc.KIND_LABELS_AR,
    )
