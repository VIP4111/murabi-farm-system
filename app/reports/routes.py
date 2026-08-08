from flask import render_template, request, Response
from flask_login import login_required

from app.reports import reports_bp
from app.reports import report_service as svc
from app.reports import export_service as ex
from app.auth.decorators import require_permission


def _load(report_key):
    label, fn = svc.REPORTS[report_key]
    start, end, range_key = svc.parse_date_range(request.args)
    data = fn(start, end)
    return label, data, start, end, range_key


@reports_bp.route("/")
@login_required
@require_permission("analytics.view")
def overview():
    return _render("overview")


@reports_bp.route("/mortality")
@login_required
@require_permission("analytics.view")
def mortality():
    return _render("mortality")


@reports_bp.route("/births")
@login_required
@require_permission("analytics.view")
def births():
    return _render("births")


@reports_bp.route("/sales")
@login_required
@require_permission("analytics.view")
def sales():
    return _render("sales")


@reports_bp.route("/purchases")
@login_required
@require_permission("analytics.view")
def purchases():
    return _render("purchases")


@reports_bp.route("/activity")
@login_required
@require_permission("analytics.view")
def activity():
    return _render("activity")


@reports_bp.route("/purchase_request")
@login_required
@require_permission("analytics.view")
def purchase_request():
    return _render("purchase_request")


def _render(report_key):
    label, data, start, end, range_key = _load(report_key)
    return render_template(
        f"reports/{report_key}.html",
        label=label, data=data, start=start, end=end, range_key=range_key,
        range_labels=svc.RANGE_LABELS, reports=svc.REPORTS, active_key=report_key,
    )


@reports_bp.route("/<report_key>/export/<fmt>")
@login_required
@require_permission("analytics.view")
def export(report_key, fmt):
    if report_key not in svc.REPORTS:
        return Response("تقرير غير معروف", status=404)
    label, data, start, end, range_key = _load(report_key)
    table = data["table"]
    subtitle = f"الفترة: {start} إلى {end}"

    if fmt == "xlsx":
        buf = ex.build_excel(label, table["columns"], table["rows"])
        return Response(
            buf.read(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={report_key}_{start}_{end}.xlsx"},
        )
    if fmt == "pdf":
        buf = ex.build_pdf(label, table["columns"], table["rows"], subtitle=subtitle)
        return Response(
            buf.read(), mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={report_key}_{start}_{end}.pdf"},
        )
    return Response("صيغة غير مدعومة", status=400)
