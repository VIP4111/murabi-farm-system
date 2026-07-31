from datetime import date
from flask import render_template, request, redirect, url_for, flash
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
    return render_template(
        "finance/list.html", rows=rows, total_in=total_in, total_out=total_out,
        total_debt_in=total_debt_in, total_debt_repaid=total_debt_repaid,
        debt_outstanding=total_debt_in - total_debt_repaid,
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


@finance_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_permission("finance.full.manage")
def finance_new():
    if request.method == "POST":
        from app.finance.finance_service import save_invoice_file
        row = Finance(
            date=date.fromisoformat(request.form["date"]),
            operation_type=request.form["operation_type"],
            category=request.form.get("category"),
            item=request.form.get("item"),
            description=request.form.get("description"),
            amount=float(request.form["amount"]),
            payment_method=request.form.get("payment_method"),
            related_animal_id=request.form.get("related_animal_id") or None,
            is_indirect=bool(request.form.get("is_indirect")),
            invoice_file_url=save_invoice_file(request.files.get("invoice_file")),
        )
        db.session.add(row)
        db.session.commit()
        flash("تمت إضافة العملية المالية", "success")
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

    flash("تم إلغاء العملية (السجل باقٍ للتدقيق)", "success")
    return redirect(url_for("finance.finance_list"))
