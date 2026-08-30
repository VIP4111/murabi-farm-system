from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_babel import gettext as _
from flask_login import login_required, current_user

from app.finance import finance_bp
from app.auth.decorators import require_permission
from app.extensions import db
from app.models import Finance, Animal, AuditLog, VetVisit, Disease


@finance_bp.route("/health")
@login_required
@require_permission("finance.health.view")
def finance_health_view():
    """
    مالية الدكتور المحدودة: تعرض فقط تكاليف الزيارات البيطرية وعلاج الأمراض،
    بدون أي وصول لمبيعات/مشتريات/مصاريف الحلال العامة (finance.full.manage).
    """
    visits = VetVisit.query.order_by(VetVisit.date.desc()).all()
    diseases = Disease.query.order_by(Disease.date.desc()).all()
    total = sum(v.cost or 0 for v in visits) + sum(d.treatment_cost or 0 for d in diseases)
    return render_template("finance/health_view.html", visits=visits, diseases=diseases, total=total)


@finance_bp.route("/")
@login_required
@require_permission("finance.full.manage")
def finance_list():
    rows = Finance.query.order_by(Finance.date.desc()).all()
    total_in = sum(r.amount for r in rows if r.operation_type == "sale" and not r.is_cancelled)
    total_out = sum(r.amount for r in rows if r.operation_type in ("purchase", "expense") and not r.is_cancelled)
    # الديون منفصلة تماماً عن الداخل/الخارج التشغيلي — "دعم خارجي" مو دخل
    # حقيقي، هو التزام لازم يُرد، فما يُحسب مع صافي الدخل (بند 18).
    total_debt_in = sum(r.amount for r in rows if r.operation_type == "debt_in" and not r.is_cancelled)
    total_debt_repaid = sum(r.amount for r in rows if r.operation_type == "debt_repayment" and not r.is_cancelled)

    # صافي الربح ونسبته % (بند إضافي 256، طلبك الصريح: "كم نسبة أرباحي")
    # — الديون مستثناة عمداً (نفس منطق الداخل/الخارج أعلاه)، الديون
    # التزام مو دخل/مصروف تشغيلي حقيقي.
    net_profit = total_in - total_out
    profit_percent = round((net_profit / total_out) * 100, 1) if total_out else None

    from app.core.loss_diagnosis_service import diagnose_recent_loss
    loss_diagnosis = diagnose_recent_loss()

    return render_template(
        "finance/list.html", rows=rows, total_in=total_in, total_out=total_out,
        total_debt_in=total_debt_in, total_debt_repaid=total_debt_repaid,
        debt_outstanding=total_debt_in - total_debt_repaid,
        net_profit=net_profit, profit_percent=profit_percent,
        loss_diagnosis=loss_diagnosis,
    )


@finance_bp.route("/export")
@login_required
@require_permission("finance.full.manage")
def finance_export():
    """تصدير كل السجلات المالية Excel بضغطة زر واحدة (بند إضافي 179) —
    نفس محرك التصدير العام الموجود أصلاً بوحدة التقارير التحليلية
    (`export_service.build_excel`)، بدون بناء آلية موازية."""
    from flask import Response
    from app.reports import export_service as ex
    rows = Finance.query.order_by(Finance.date.desc()).all()
    columns = ["التاريخ", "النوع", "الفئة", "الصنف", "الوصف", "المبلغ", "طريقة الدفع", "الرأس المرتبط", "ملغاة"]
    table_rows = [
        [
            str(r.date), r.operation_type, r.category or "-", r.item or "-", r.description or "-",
            r.amount, r.payment_method or "-",
            r.related_animal.animal_no if r.related_animal else "-",
            "نعم" if r.is_cancelled else "لا",
        ]
        for r in rows
    ]
    buf = ex.build_excel("السجل المالي الكامل", columns, table_rows)
    return Response(
        buf.read(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=finance_export.xlsx"},
    )


@finance_bp.route("/break-even-report/export")
@login_required
@require_permission("finance.full.manage")
def break_even_export():
    from flask import Response
    from app.reports import export_service as ex
    from app.core.animal_profile_service import break_even_summary
    rows = break_even_summary()
    columns = ["رقم الرأس", "سعر التعادل", "القيمة التقديرية", "مصدر التقدير", "الهامش"]
    _source_label = {"auto": "مبيعات مشابهة", "manual": "تقدير يدوي"}
    table_rows = [
        [
            r["animal"].animal_no, r["break_even_price"],
            r["estimated_value"] if r["estimated_value"] is not None else "-",
            _source_label.get(r["estimate_source"], "-"),
            r["margin"] if r["margin"] is not None else "-",
        ]
        for r in rows
    ]
    buf = ex.build_excel("التحليل المالي ونقطة التعادل", columns, table_rows)
    return Response(
        buf.read(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=break_even_report.xlsx"},
    )


@finance_bp.route("/monthly-cost-report")
@login_required
@require_permission("finance.full.manage")
def monthly_cost_report():
    from app.core.finance_report_service import monthly_cost_per_head, annual_cost_per_head
    months = int(request.args.get("months", 12))
    rows = monthly_cost_per_head(months=months)
    annual = annual_cost_per_head(rows)
    return render_template("finance/monthly_cost_report.html", rows=rows, months=months, annual=annual)


@finance_bp.route("/break-even-report")
@login_required
@require_permission("finance.full.manage")
def break_even_report():
    from app.core.animal_profile_service import break_even_summary
    rows = break_even_summary()
    at_risk_count = sum(1 for r in rows if r["at_risk"])
    missing_estimate_count = sum(1 for r in rows if r["estimated_value"] is None)
    return render_template(
        "finance/break_even_report.html", rows=rows,
        at_risk_count=at_risk_count, missing_estimate_count=missing_estimate_count,
    )


@finance_bp.route("/seasonal-price-analysis")
@login_required
@require_permission("finance.full.manage")
def seasonal_price_analysis():
    """شارت موسمية أسعار البيع بالتقويم الهجري (بند إضافي 255)."""
    from app.core.seasonal_price_service import seasonal_price_analysis as analyze
    data = analyze()
    max_price = max(
        [m["current_year_avg"] or 0 for m in data["months"]]
        + [m["historical_avg"] or 0 for m in data["months"]],
        default=0,
    )
    return render_template("finance/seasonal_price_analysis.html", data=data, max_price=max_price)


@finance_bp.route("/lots")
@login_required
@require_permission("finance.full.manage")
def lots_list():
    from app.models import SalesLot
    lots = SalesLot.query.order_by(SalesLot.created_at.desc()).all()
    return render_template("finance/lots_list.html", lots=lots)


@finance_bp.route("/lots/new", methods=["GET", "POST"])
@login_required
@require_permission("finance.full.manage")
def lots_new():
    from app.models import SalesLot, SalesLotItem
    from app.core import sales_lot_service as svc

    candidates = [svc.animal_lot_row(a) for a in svc.sellable_animals()]

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash(_("اسم الدفعة مطلوب"), "error")
            return redirect(url_for("finance.lots_new"))
        animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
        if not animal_ids:
            flash(_("لازم تختار رأساً واحداً على الأقل"), "error")
            return redirect(url_for("finance.lots_new"))

        lot = SalesLot(
            name=name, notes=request.form.get("notes") or None,
            target_amount=float(request.form["target_amount"]) if request.form.get("target_amount") else None,
            created_by_id=current_user.id,
        )
        db.session.add(lot)
        db.session.flush()
        for animal_id in animal_ids:
            db.session.add(SalesLotItem(lot_id=lot.id, animal_id=animal_id))
        db.session.add(AuditLog(actor_user_id=current_user.id, action="sales_lot.create",
                                 entity_type="SalesLot", entity_id=lot.id, details=name))
        db.session.commit()
        flash(_("تم إنشاء دفعة البيع"), "success")
        return redirect(url_for("finance.lot_detail", lot_id=lot.id))

    target_amount = request.args.get("target_amount", type=float)
    suggested_ids = set(svc.suggest_lot_for_target(target_amount=target_amount, candidates=candidates)) if target_amount else set()

    return render_template(
        "finance/lot_form.html", candidates=candidates,
        target_amount=target_amount, suggested_ids=suggested_ids,
    )


@finance_bp.route("/lots/<int:lot_id>")
@login_required
@require_permission("finance.full.manage")
def lot_detail(lot_id):
    from app.models import SalesLot
    from app.core import sales_lot_service as svc
    lot = SalesLot.query.get_or_404(lot_id)
    rows = [svc.animal_lot_row(item.animal) for item in lot.items]
    stats = svc.lot_stats(rows)
    return render_template("finance/lot_detail.html", lot=lot, rows=rows, stats=stats)


@finance_bp.route("/lots/<int:lot_id>/export/pdf")
@login_required
@require_permission("finance.full.manage")
def lot_export_pdf(lot_id):
    from flask import Response
    from app.models import SalesLot, FarmSettings
    from app.core import sales_lot_service as svc
    from app.reports import export_service as ex
    lot = SalesLot.query.get_or_404(lot_id)
    rows = [svc.animal_lot_row(item.animal) for item in lot.items]
    stats = svc.lot_stats(rows)
    buf = ex.build_lot_profile_pdf(lot, rows, stats, FarmSettings.get())
    return Response(
        buf.read(), mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=lot_{lot.id}.pdf"},
    )


@finance_bp.route("/lots/<int:lot_id>/delete", methods=["POST"])
@login_required
@require_permission("finance.full.manage")
def lot_delete(lot_id):
    from app.models import SalesLot
    lot = SalesLot.query.get_or_404(lot_id)
    db.session.add(AuditLog(actor_user_id=current_user.id, action="sales_lot.delete",
                             entity_type="SalesLot", entity_id=lot.id, details=lot.name))
    db.session.delete(lot)
    db.session.commit()
    flash(_("تم حذف الدفعة"), "success")
    return redirect(url_for("finance.lots_list"))


@finance_bp.route("/culling-index")
@login_required
@require_permission("finance.full.manage")
def culling_index():
    from app.core.culling_index_service import culling_candidates
    rows = culling_candidates()
    total_potential_savings = round(sum(r["monthly_total_cost"] for r in rows), 2)
    return render_template(
        "finance/culling_index.html", rows=rows, total_potential_savings=total_potential_savings,
    )


@finance_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_permission("finance.full.manage")
def finance_new():
    if request.method == "POST":
        from app.finance.finance_service import save_invoice_file
        entry_date = date.fromisoformat(request.form["date"])
        amount = float(request.form["amount"])

        # فحوصات سلامة إدخال (بند إضافي 187) — قبل أي حفظ فعلي.
        from app.core import validation_service
        try:
            validation_service.validate_price(amount, field_label=_("المبلغ"))
            validation_service.validate_not_future_date(entry_date, field_label=_("تاريخ الحركة"))
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("finance.finance_new"))

        row = Finance(
            date=entry_date,
            operation_type=request.form["operation_type"],
            category=request.form.get("category"),
            item=request.form.get("item"),
            description=request.form.get("description"),
            amount=amount,
            payment_method=request.form.get("payment_method"),
            related_animal_id=request.form.get("related_animal_id") or None,
            is_indirect=bool(request.form.get("is_indirect")),
            invoice_file_url=save_invoice_file(request.files.get("invoice_file")),
        )
        db.session.add(row)
        db.session.commit()

        # كشف الشذوذ المالي (بند إضافي 161) — إشعار فوري لصاحب الحلال
        # لو المبلغ شاذ مقارنة بتاريخ نفس الفئة.
        from app.core.finance_anomaly_service import detect_anomaly
        anomaly = detect_anomaly(row)
        if anomaly:
            flash(
                f"⚠️ تنبيه: هذا المبلغ ({anomaly['amount']:.0f}) {anomaly['direction']} "
                f"بنسبة {abs(anomaly['deviation_pct'])}% من متوسط عمليات \"{row.category}\" "
                f"السابقة ({anomaly['average']:.0f}).", "error",
            )
            from app.core import telegram_service
            from app.models import User
            op_labels = {"sale": "بيع", "purchase": "شراء", "expense": "مصروف"}
            for user in User.query.filter(User.telegram_chat_id.isnot(None), User.is_active_account.is_(True)).all():
                if user.has_permission("finance.full.manage"):
                    telegram_service.notify_user(
                        user,
                        f"⚠️ عملية {op_labels.get(row.operation_type, row.operation_type)} غير معتادة\n"
                        f"{row.category} — {anomaly['amount']:.0f} ({anomaly['direction']} بـ{abs(anomaly['deviation_pct'])}% عن المعتاد {anomaly['average']:.0f})",
                    )

        flash(_("تمت إضافة العملية المالية"), "success")
        return redirect(url_for("finance.finance_list"))

    return render_template("finance/form.html", animals=Animal.query.order_by(Animal.animal_no).all())


@finance_bp.route("/<int:row_id>/cancel", methods=["POST"])
@login_required
@require_permission("finance.full.manage")
def finance_cancel(row_id):
    """لا حذف نهائي للسجلات المالية أبداً — بس إلغاء مع سبب، والسجل يضل موجود للتدقيق."""
    row = Finance.query.get_or_404(row_id)
    row.is_cancelled = True
    row.cancel_reason = request.form.get("reason", "")
    db.session.add(AuditLog(actor_user_id=current_user.id, action="finance.cancel",
                             entity_type="Finance", entity_id=row.id, details=row.cancel_reason))
    db.session.commit()

    if row.operation_type == "sale" and row.related_animal_id and row.related_animal.status == "sold":
        from app.core.cycle_engine import restore_animal_after_sale_cancel
        restore_animal_after_sale_cancel(row.related_animal, actor_user_id=current_user.id)

    flash(_("تم إلغاء العملية (السجل باقٍ للتدقيق)"), "success")
    return redirect(url_for("finance.finance_list"))
