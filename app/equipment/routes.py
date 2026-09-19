from flask import render_template, request, redirect, url_for, flash
from flask_babel import gettext as _
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
    # بند إضافي 276 — طلبك الصريح "ما بين عندي مين اخذ المعدة": نعرض
    # "آخر من أخذها" مباشرة بالقائمة، بدون ما تدخل حركة كل صنف لحاله.
    # بند إصلاح (فحص شامل سطر بسطر) — استعلام واحد مجمَّع بدل استعلام
    # منفصل لكل صنف.
    holders = svc.outstanding_borrows_bulk(items)
    return render_template("equipment/items_list.html", items=items, holders=holders)


@equipment_bp.route("/items/new", methods=["GET", "POST"])
@login_required
@require_permission("equipment.manage")
def items_new():
    if request.method == "POST":
        # بند إصلاح (فحص عميق مقسَّم — تدقيق شامل للنماذج) — نفس نمط
        # ثغرات deduct_stock/add_stock المُصلَحة، بس هنا الرصيد الافتتاحي
        # يُدخَل مباشرة بدون المرور بأي دالة محمية.
        from app.core import validation_service
        try:
            validation_service.validate_price(float(request.form.get("available_qty") or 0), field_label=_("الكمية المتوفرة"))
            validation_service.validate_price(float(request.form.get("min_stock_qty") or 0), field_label=_("الحد الأدنى للمخزون"))
            # بند إصلاح (فحص شامل سطر بسطر — ميزة المعدات) — سعر الوحدة
            # كان يُحفَظ بلا أي فحص، نفس الفجوة المُصلَحة بمكوّنات العلف.
            if request.form.get("unit_price"):
                validation_service.validate_price(float(request.form["unit_price"]), field_label=_("سعر الوحدة"))
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("equipment.items_new"))
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
        flash(_("تمت إضافة الصنف"), "success")
        return redirect(url_for("equipment.items_list"))
    return render_template("equipment/item_form.html")


@equipment_bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("equipment.manage")
def items_edit(item_id):
    item = Equipment.query.get_or_404(item_id)
    if request.method == "POST":
        from app.core import validation_service
        try:
            validation_service.validate_price(float(request.form.get("available_qty") or 0), field_label=_("الكمية المتوفرة"))
            validation_service.validate_price(float(request.form.get("min_stock_qty") or 0), field_label=_("الحد الأدنى للمخزون"))
            if request.form.get("unit_price"):
                validation_service.validate_price(float(request.form["unit_price"]), field_label=_("سعر الوحدة"))
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("equipment.items_edit", item_id=item.id))
        item.name = request.form["name"]
        item.category = request.form.get("category")
        item.unit = request.form.get("unit") or "قطعة"
        item.unit_price = float(request.form["unit_price"]) if request.form.get("unit_price") else None
        item.available_qty = float(request.form.get("available_qty") or 0)
        item.min_stock_qty = float(request.form.get("min_stock_qty") or 0)
        item.notes = request.form.get("notes")
        # بند إضافي 276 — علم "تحتاج صيانة" ما يظهر بالفورم إلا لو مرفوع
        # أصلاً؛ لو مو ظاهر، ما نلمسه (يبقى False كأي صنف سليم عادي).
        if item.needs_maintenance:
            item.needs_maintenance = request.form.get("needs_maintenance") == "1"
        new_photo = svc.save_equipment_photo(request.files.get("photo"))
        if new_photo:
            item.photo_url = new_photo
        db.session.commit()
        flash(_("تم تحديث الصنف"), "success")
        return redirect(url_for("equipment.items_list"))
    return render_template("equipment/item_form.html", item=item)


@equipment_bp.route("/purchase", methods=["GET", "POST"])
@login_required
@require_permission("equipment.manage")
def purchase_new():
    """شراء معدات موحّد (بند إضافي 203) — نفس فكرة `feed.purchase_new`
    بالضبط: يزيد المخزون ويسجّل العملية المالية بضغطة وحدة."""
    if not current_user.has_permission("finance.full.manage"):
        flash(_("تحتاج صلاحية إدارة المالية كمان عشان تسجّل شراء (يُنشئ عملية مالية)."), "error")
        return redirect(url_for("equipment.items_list"))
    if request.method == "POST":
        item = Equipment.query.get_or_404(int(request.form["equipment_id"]))
        try:
            from app.core import validation_service
            from app.core.stock_purchase_service import record_purchase
            # بند إصلاح (فحص شامل سطر بسطر — ميزة المعدات) — الكمية
            # والسعر كانا يُمرَّران مباشرة بلا أي فحص قبل record_purchase.
            validation_service.validate_price(float(request.form["quantity"]), field_label=_("الكمية"))
            validation_service.validate_price(float(request.form["unit_price"]), field_label=_("سعر الوحدة"))
            record_purchase(
                kind="equipment", item=item,
                quantity=float(request.form["quantity"]),
                unit_price=float(request.form["unit_price"]),
                purchase_date=date.fromisoformat(request.form["date"]),
                invoice_file=request.files.get("invoice_file"),
                note=request.form.get("note"), created_by_id=current_user.id,
            )
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("equipment.purchase_new"))
        flash(_("تم تسجيل الشراء — زاد المخزون وانسجلت العملية المالية معاً"), "success")
        return redirect(url_for("equipment.items_list"))
    return render_template(
        "equipment/purchase_form.html",
        items=Equipment.query.filter_by(status="active").order_by(Equipment.name).all(),
    )


@equipment_bp.route("/items/<int:item_id>/movement", methods=["GET", "POST"])
@login_required
@require_permission("equipment.manage")
def items_movement(item_id):
    item = Equipment.query.get_or_404(item_id)
    if request.method == "POST":
        movement_type = request.form["movement_type"]
        # بند إضافي 276 — طلبك الصريح: كل صرف لازم يُسجَّل مين استلمه.
        if movement_type == "out" and not request.form.get("borrowed_by_id"):
            flash(_("لازم تحدد مين يستلم القطعة قبل تسجيل الصرف."), "error")
            return redirect(url_for("equipment.items_movement", item_id=item.id))
        try:
            # بند إصلاح (فحص شامل سطر بسطر — ميزة المعدات) — الكمية ما
            # كانت تُفحَص قبل الوصول لـrecord_movement — كمية سالبة
            # بحركة "صادر" كانت تزيد الرصيد فعلياً بدل ما تنقصه
            # (deduct_stock بكمية سالبة = إضافة).
            from app.core import validation_service
            quantity_val = float(request.form["quantity"])
            validation_service.validate_price(quantity_val, field_label=_("الكمية"))
            if quantity_val <= 0:
                raise ValueError(_("الكمية لازم تكون أكبر من صفر."))
            svc.record_movement(
                item=item, movement_type=movement_type,
                quantity=quantity_val,
                barn_id=request.form.get("barn_id") or None,
                note=request.form.get("note"), created_by_id=current_user.id,
                borrowed_by_id=request.form.get("borrowed_by_id") or None,
                no_return_expected=request.form.get("no_return_expected") == "1",
                condition_at_handout=request.form.get("condition_at_handout") or None,
            )
            flash(_("تم تسجيل الحركة"), "success")
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
                     .filter_by(equipment_id=item.id, returned_at=None, no_return_expected=False)
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
    condition = request.form.get("condition_at_handout") or "good"
    try:
        svc.record_movement(
            item=item, movement_type="out", quantity=1,
            created_by_id=current_user.id, borrowed_by_id=current_user.id,
            condition_at_handout=condition,
        )
        flash(_("تم تسجيل أخذك للقطعة"), "success")
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
        flash(_("ما فيه استعارة قائمة لك بهذي القطعة"), "error")
        return redirect(url_for("equipment.items_mine"))
    condition = request.form.get("condition_at_return") or "good"
    try:
        svc.return_item(mine, condition_at_return=condition)
        flash(_("تم تسجيل استرجاع القطعة"), "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("equipment.items_mine"))


@equipment_bp.route("/movements/<int:movement_id>/return", methods=["POST"])
@login_required
@require_permission("equipment.manage")
def movement_return(movement_id):
    """تسجيل استرجاع قطعة مستعارة (بند إضافي 110)."""
    movement = EquipmentMovement.query.get_or_404(movement_id)
    condition = request.form.get("condition_at_return") or "good"
    try:
        svc.return_item(movement, condition_at_return=condition)
        flash(_("تم تسجيل استرجاع القطعة"), "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("equipment.items_movement", item_id=movement.equipment_id))


# ---------- إدارة الأصول والصيانة الدورية (بند إضافي 186) ----------

@equipment_bp.route("/assets")
@login_required
@require_permission("equipment.view")
def assets_list():
    from sqlalchemy.orm import joinedload
    from app.extensions import farm_today
    # بند إصلاح (فحص شامل سطر بسطر — ميزة المعدات) — joinedload(Asset.barn)
    # يمنع استعلام Barn منفصل لكل صف (القالب يعرض a.barn.barn_name).
    assets = (Asset.query.options(joinedload(Asset.barn))
              .filter_by(status="active").order_by(Asset.name).all())
    # بند إصلاح — كانت date.today() (UTC خام) بدل farm_today() المستخدَمة
    # بمولّد مهام الصيانة الخلفي (asset_maintenance_service.py) — قرب
    # منتصف الليل بتوقيت الرياض ممكن الشاشة تقول "مو مستحقة بعد" رغم إن
    # مهمة صيانة اتولّدت فعلاً خلف الكواليس لنفس الأصل.
    today = farm_today()
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
        # بند إصلاح (فحص شامل سطر بسطر — ميزة المعدات) — فترة الصيانة
        # ما كانت تُفحَص؛ صفر أو رقم سالب يخلي next_due يبقى "مستحقة"
        # دايماً (أو بتاريخ ماضٍ فوراً) بلا أي معنى منطقي.
        interval_raw = request.form.get("maintenance_interval_days")
        interval_val = None
        if interval_raw is not None and interval_raw != "":
            interval_val = int(interval_raw)
            # صفر قيمة صحيحة ومقصودة (تعني "بدون صيانة دورية مجدولة" —
            # راجع تعليق Asset.maintenance_interval_days بالنموذج)،
            # المرفوض هنا رقم سالب بس.
            if interval_val < 0:
                flash(_("فترة الصيانة ما يقدر تكون رقماً سالباً."), "error")
                return redirect(url_for("equipment.assets_new"))
        asset = Asset(
            name=request.form["name"], category=request.form.get("category") or "other",
            barn_id=request.form.get("barn_id") or None,
            maintenance_interval_days=interval_val,
            notes=request.form.get("notes"),
        )
        db.session.add(asset)
        db.session.commit()
        flash(_("تمت إضافة الأصل"), "success")
        return redirect(url_for("equipment.assets_list"))
    return render_template("equipment/asset_form.html", barns=Barn.query.order_by(Barn.barn_name).all())


@equipment_bp.route("/assets/<int:asset_id>/maintenance", methods=["GET", "POST"])
@login_required
@require_permission("equipment.manage")
def asset_maintenance(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    if request.method == "POST":
        maintenance_date = date.fromisoformat(request.form["date"])
        cost = float(request.form["cost"]) if request.form.get("cost") else None
        # بند إصلاح (فحص عميق — قسم المعدات) — نفس ثغرة تكلفة الزيارة
        # البيطرية اليدوية: `record_maintenance_cost` تتجاوز إنشاء عملية
        # مالية لو `cost <= 0`، لكن القيمة السالبة تبقى مخزَّنة مباشرة
        # على `AssetMaintenanceLog.cost` بصمت.
        if cost is not None and cost < 0:
            flash(_("التكلفة ما يقدر تكون رقماً سالباً."), "error")
            return redirect(url_for("equipment.asset_maintenance", asset_id=asset.id))
        finance_id = svc.record_maintenance_cost(asset=asset, cost=cost, date_=maintenance_date)
        db.session.add(AssetMaintenanceLog(
            asset_id=asset.id, date=maintenance_date, notes=request.form.get("notes"),
            cost=cost, performed_by_id=current_user.id, finance_id=finance_id,
        ))
        asset.last_maintenance_date = maintenance_date
        db.session.commit()
        flash(_("تم تسجيل الصيانة"), "success")
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
        reading_date = date.fromisoformat(request.form["date"])
        utility_type = request.form["utility_type"]
        cost = float(request.form["cost"]) if request.form.get("cost") else None
        # بند إصلاح (فحص عميق — قسم المعدات) — نفس ملاحظة الصيانة أعلاه.
        if cost is not None and cost < 0:
            flash(_("التكلفة ما يقدر تكون رقماً سالباً."), "error")
            return redirect(url_for("equipment.utilities_new"))
        # بند إصلاح (فحص شامل سطر بسطر — ميزة المعدات) — قراءة الكمية
        # (كيلوواط/متر مكعب) ما كانت تُفحَص إطلاقاً، عكس التكلفة المصلَحة
        # فوق — نفس النمط الناقص جزئياً بميزات ثانية.
        quantity_val = float(request.form["quantity"])
        if quantity_val < 0:
            flash(_("الكمية ما يقدر تكون رقماً سالباً."), "error")
            return redirect(url_for("equipment.utilities_new"))
        finance_id = svc.record_utility_cost(utility_type=utility_type, cost=cost, date_=reading_date)
        db.session.add(UtilityReading(
            utility_type=utility_type, date=reading_date,
            quantity=quantity_val, unit=request.form.get("unit"),
            cost=cost, notes=request.form.get("notes"), finance_id=finance_id,
        ))
        db.session.commit()
        flash(_("تم تسجيل القراءة"), "success")
        return redirect(url_for("equipment.utilities_list"))
    return render_template("equipment/utility_form.html", today=date.today().isoformat())
