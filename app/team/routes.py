from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from flask_babel import lazy_gettext as _l
from sqlalchemy.exc import IntegrityError

from datetime import date, timedelta

from app.team import team_bp
from app.team import report_service as svc
from app.team import task_service as tsvc
from app.auth.decorators import require_permission
from app.extensions import db
from app.models import User, Role, Animal, Barn, Report, Task, AuditLog


# ---------- واجهة العامل المبسّطة (بند 27) ----------
# أربعة أزرار من الخمسة تفتح نفس النمط: بلاغ سريع بنوع مقفل (العامل ما
# يختار من قائمة، الزر نفسه يحدد النوع) + قائمة مهامه المفتوحة من نفس
# الفئة (لو موجودة) — يعيد استخدام محرك البلاغات (بند 28) ومحرك المهام
# (بند 21) بالكامل، بدون أي صلاحية جديدة (`reports.submit` موجودة أصلاً
# بدور العامل). الزر الخامس ("مهامي اليوم") يرجّع مباشرة لشاشة `/team/tasks`
# الموجودة، بدون أي كود إضافي.
# **بند إضافي (لغات، 2026-07-23)**: `label` تُترجَم للعرض بس (lazy_gettext
# — يتقيّم حسب لغة الطلب الحالي، مو وقت استيراد الملف). `report_type`
# **يبقى عربي ثابت بدون ترجمة عمداً** — هذا اللي يُخزَّن فعلياً بجدول
# Report ويشوفه الدكتور بشاشة `/team/reports`، فلازم يبقى قيمة واحدة
# ثابتة بغض النظر عن لغة العامل اللي رفع البلاغ (تجنّباً لتضارب قيم
# بلغات مختلفة بنفس الحقل).
WORKER_REPORT_CATEGORIES = {
    "health": {
        "label": _l("فحص / حالة صحية"), "icon": "🩺", "report_type": "حالة صحية",
        "task_types": ["isolation_check", "doctor_review"], "species_filter": None,
    },
    "isolation": {
        "label": _l("نقل إلى العزل"), "icon": "🚧", "report_type": "نقل للعزل",
        "task_types": [], "species_filter": None,
    },
    "feed": {
        "label": _l("تغذية / عليقة"), "icon": "🌾", "report_type": "تغذية / عليقة",
        "task_types": ["feed_switch"], "species_filter": None,
    },
    "ostrich": {
        "label": _l("بيض / حضانة (نعام)"), "icon": "🥚", "report_type": "بيض / حضانة نعام",
        "task_types": [], "species_filter": "ostrich",
    },
}


# ---------- أعضاء الفريق ----------

@team_bp.route("/members")
@login_required
@require_permission("users.manage")
def members_list():
    members = User.query.order_by(User.created_at.desc()).all()
    return render_template("team/members_list.html", members=members)


@team_bp.route("/members/new", methods=["GET", "POST"])
@login_required
@require_permission("users.manage")
def members_new():
    if request.method == "POST":
        user = User(
            name=request.form["name"],
            phone=request.form["phone"].strip(),
            role_id=int(request.form["role_id"]),
            language=request.form.get("language") or "ar",
        )
        user.set_password(request.form["password"])
        db.session.add(user)
        db.session.flush()
        db.session.add(AuditLog(actor_user_id=current_user.id, action="user.create",
                                 entity_type="User", entity_id=user.id))
        db.session.commit()
        flash("تمت إضافة العضو", "success")
        return redirect(url_for("team.members_list"))
    return render_template("team/member_form.html", roles=Role.query.order_by(Role.id).all())


@team_bp.route("/members/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("users.manage")
def members_edit(user_id):
    """تعديل بيانات عضو فريق موجود + تغيير كلمة المرور (بند إضافي 58) —
    كلمة المرور الجديدة اختيارية: تتغيّر بس لو الحقل تعبّى، عن طريق
    `User.set_password()` مباشرة بدون حاجة لمعرفة كلمة المرور القديمة
    (المالك يدير حساب غيره، مو نفسه)."""
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        user.name = request.form["name"].strip()
        user.phone = request.form["phone"].strip()
        user.role_id = int(request.form["role_id"])
        user.language = request.form.get("language") or "ar"
        new_password = request.form.get("new_password", "").strip()
        if new_password:
            user.set_password(new_password)
        db.session.add(user)
        try:
            db.session.add(AuditLog(actor_user_id=current_user.id, action="user.edit",
                                     entity_type="User", entity_id=user.id,
                                     details="password_changed" if new_password else None))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(f'رقم الجوال "{request.form["phone"]}" مستخدم من قبل', "error")
            return redirect(url_for("team.members_edit", user_id=user.id))
        flash("تم تحديث بيانات العضو" + (" وكلمة المرور" if new_password else ""), "success")
        return redirect(url_for("team.members_list"))
    return render_template("team/member_edit_form.html", member=user,
                            roles=Role.query.order_by(Role.id).all())


@team_bp.route("/members/<int:user_id>/toggle", methods=["POST"])
@login_required
@require_permission("users.manage")
def members_toggle(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("ما تقدر تعطّل حسابك أنت", "error")
        return redirect(url_for("team.members_list"))
    user.is_active_account = not user.is_active_account
    db.session.add(AuditLog(actor_user_id=current_user.id, action="user.toggle",
                             entity_type="User", entity_id=user.id,
                             details="enabled" if user.is_active_account else "disabled"))
    db.session.commit()
    flash(f"تم {'تفعيل' if user.is_active_account else 'تعطيل'} الحساب", "success")
    return redirect(url_for("team.members_list"))


# ---------- البلاغات ----------

@team_bp.route("/reports")
@login_required
def reports_list():
    inbox = my_accepted = my_executor_tasks = my_reports = cancelled = []
    if current_user.has_permission("reports.manage"):
        inbox = Report.query.filter_by(status="new").order_by(Report.created_at).all()
        my_accepted = (Report.query
                       .filter(Report.manager_id == current_user.id,
                               Report.status.in_(["accepted", "executed_pending_review"]))
                       .order_by(Report.accepted_at).all())
    my_executor_tasks = (Report.query
                         .filter_by(executor_id=current_user.id, status="accepted")
                         .order_by(Report.transferred_at).all())
    if current_user.has_permission("reports.submit"):
        my_reports = Report.query.filter_by(reporter_id=current_user.id).order_by(Report.created_at.desc()).limit(30).all()
    if current_user.has_permission("reports.delete_final"):
        cancelled = Report.query.filter_by(status="cancelled").order_by(Report.created_at.desc()).all()

    return render_template(
        "team/reports_list.html",
        inbox=inbox, my_accepted=my_accepted, my_executor_tasks=my_executor_tasks,
        my_reports=my_reports, cancelled=cancelled,
    )


def _scoped_barn_ids():
    """تقييد العامل الميداني بحظيرته (بند إضافي، 2026-07-23) — أي مستخدم
    ما عنده `animals.view` (يعني ما يفترض يشوف كل القطيع أصلاً، نفس
    تعريف صلاحية `العامل` الافتراضية) يُقيَّد بالحظائر اللي هو مسؤولها
    (`Barn.responsible_worker_id`). ترجع `None` لو المستخدم مو مقيَّد
    أصلاً (يشوف كل شي بلا فلترة) — القرار مبني على الصلاحية نفسها، مو
    اسم الدور، عشان يبقى متّسق مع باقي النظام (الأدوار بيانات قابلة
    للتعديل من الإعدادات)."""
    if current_user.has_permission("animals.view"):
        return None
    return [b.id for b in Barn.query.filter_by(responsible_worker_id=current_user.id).all()]


def _validate_scoped_report(barn_ids, animal_id, barn_id):
    """فحص خادم حقيقي (بند إضافي، 2026-07-23) — لو العامل مقيَّد بحظيرته،
    ما يقدر يبلّغ عن حيوان/حظيرة خارج نطاقه حتى لو عدّل الطلب مباشرة
    (تجاوَز الفلترة بالواجهة). ترجع رسالة خطأ أو None لو الاختيار صحيح."""
    if barn_ids is None:
        return None
    if animal_id:
        animal = Animal.query.get(int(animal_id))
        if not animal or animal.barn_id not in barn_ids:
            return "الحيوان المحدد خارج نطاق حظائرك — راجع المالك لو محتاج تبلّغ عنه."
    if barn_id and int(barn_id) not in barn_ids:
        return "الحظيرة المحددة خارج نطاق مسؤوليتك."
    return None


@team_bp.route("/reports/new", methods=["GET", "POST"])
@login_required
@require_permission("reports.submit")
def reports_new():
    barn_ids = _scoped_barn_ids()
    if request.method == "POST":
        # سلامة البيانات (بند إضافي، 2026-07-23): بلاغ بدون حيوان ولا حظيرة
        # يفقد تتبّعه — لازم واحد منهم على الأقل، حتى لو الفحص بالواجهة
        # (JS) تجاوَزه المستخدم أو أُرسل الطلب مباشرة للسيرفر.
        if not request.form.get("animal_id") and not request.form.get("barn_id"):
            flash("لازم تحدد الحيوان أو الحظيرة على الأقل قبل رفع البلاغ", "error")
            return redirect(url_for("team.reports_new"))
        scope_error = _validate_scoped_report(barn_ids, request.form.get("animal_id"), request.form.get("barn_id"))
        if scope_error:
            flash(scope_error, "error")
            return redirect(url_for("team.reports_new"))
        report = svc.submit_report(
            reporter=current_user,
            description=request.form["description"],
            report_type=request.form.get("report_type") or None,
            animal_id=request.form.get("animal_id") or None,
            barn_id=request.form.get("barn_id") or None,
            evidence_image_url=svc.save_evidence_image(request.files.get("evidence_image")),
            evidence_audio_url=svc.save_voice_note(request.files.get("voice_note")),
        )
        flash("تم رفع البلاغ", "success")
        return redirect(url_for("team.report_detail", report_id=report.id))

    animals_query = Animal.query
    barns_query = Barn.query
    if barn_ids is not None:
        animals_query = animals_query.filter(Animal.barn_id.in_(barn_ids))
        barns_query = barns_query.filter(Barn.id.in_(barn_ids))
    return render_template(
        "team/report_form.html",
        animals=animals_query.order_by(Animal.animal_no).all(),
        barns=barns_query.order_by(Barn.barn_name).all(),
        scoped=barn_ids is not None,
    )


@team_bp.route("/reports/<int:report_id>")
@login_required
def report_detail(report_id):
    report = Report.query.get_or_404(report_id)
    can_manage = current_user.has_permission("reports.manage")
    # إصلاح أمني (بند 29): كانت هذي الشاشة تعرض تفاصيل أي بلاغ لأي مستخدم
    # مسجّل دخول بمجرد تخمين الرقم بالرابط، بغض النظر عن علاقته بالبلاغ —
    # وصف البلاغ ممكن يكون حساس (مشكلة صحية، ملاحظة عن زميل...). صار
    # مقصوراً على: رافع البلاغ نفسه، الدكتور المستلم، المنفّذ المحوَّل له،
    # أو أي حامل صلاحية `reports.manage` عامة (لمراجعة صندوق الوارد قبل
    # القبول، لمّا manager_id لسا فاضي).
    involved = current_user.id in (report.reporter_id, report.manager_id, report.executor_id)
    if not (can_manage or involved):
        abort(403)
    is_my_report = report.manager_id == current_user.id
    executors = (User.query.join(Role)
                 .filter(User.is_active_account.is_(True), User.id != current_user.id)
                 .order_by(Role.id, User.name).all())
    executors_by_role = {}
    for e in executors:
        executors_by_role.setdefault(e.role.display_name, []).append(e)
    return render_template(
        "team/report_detail.html",
        r=report, can_manage=can_manage, is_my_report=is_my_report,
        is_reporter=report.reporter_id == current_user.id,
        is_executor=report.executor_id == current_user.id,
        can_delete=current_user.has_permission("reports.delete_final"),
        executors_by_role=executors_by_role,
    )


def _redirect_back(report_id):
    return redirect(url_for("team.report_detail", report_id=report_id))


@team_bp.route("/reports/<int:report_id>/accept", methods=["POST"])
@login_required
def report_accept(report_id):
    report = Report.query.get_or_404(report_id)
    try:
        svc.accept_report(report, actor=current_user)
        flash("تم قبول البلاغ — بدأ عدّاد الوقت", "success")
    except (svc.ReportPermissionError, svc.ReportStateError) as e:
        flash(str(e), "error")
    return _redirect_back(report_id)


@team_bp.route("/reports/<int:report_id>/postpone", methods=["POST"])
@login_required
def report_postpone(report_id):
    report = Report.query.get_or_404(report_id)
    try:
        svc.postpone_report(report, actor=current_user, reason=request.form.get("reason", ""))
        flash("تم تأجيل البلاغ", "success")
    except (svc.ReportPermissionError, svc.ReportStateError) as e:
        flash(str(e), "error")
    return _redirect_back(report_id)


@team_bp.route("/reports/<int:report_id>/resume", methods=["POST"])
@login_required
def report_resume(report_id):
    report = Report.query.get_or_404(report_id)
    try:
        svc.resume_postponed_report(report, actor=current_user)
        flash("رجع البلاغ لصندوق الوارد", "success")
    except (svc.ReportPermissionError, svc.ReportStateError) as e:
        flash(str(e), "error")
    return _redirect_back(report_id)


@team_bp.route("/reports/<int:report_id>/cancel", methods=["POST"])
@login_required
def report_cancel(report_id):
    report = Report.query.get_or_404(report_id)
    try:
        svc.cancel_report(report, actor=current_user, reason=request.form.get("reason", ""))
        flash("تم إلغاء البلاغ — انتقل لصاحب الحلال", "success")
    except (svc.ReportPermissionError, svc.ReportStateError) as e:
        flash(str(e), "error")
    return _redirect_back(report_id)


@team_bp.route("/reports/<int:report_id>/transfer", methods=["POST"])
@login_required
def report_transfer(report_id):
    report = Report.query.get_or_404(report_id)
    executor = User.query.get_or_404(int(request.form["executor_id"]))
    try:
        svc.transfer_report(report, actor=current_user, executor=executor, note=request.form.get("note", ""))
        flash(f"تم تحويل البلاغ لـ {executor.name}", "success")
    except (svc.ReportPermissionError, svc.ReportStateError) as e:
        flash(str(e), "error")
    return _redirect_back(report_id)


@team_bp.route("/reports/<int:report_id>/execute", methods=["POST"])
@login_required
def report_execute(report_id):
    report = Report.query.get_or_404(report_id)
    try:
        svc.executor_mark_done(report, actor=current_user, note=request.form.get("note"),
                                evidence_image_url=request.form.get("evidence_image_url") or None)
        flash("تم تسجيل الإنجاز — رجع البلاغ للدكتور للمراجعة والإغلاق", "success")
    except (svc.ReportPermissionError, svc.ReportStateError) as e:
        flash(str(e), "error")
    return _redirect_back(report_id)


@team_bp.route("/reports/<int:report_id>/self-execute", methods=["POST"])
@login_required
def report_self_execute(report_id):
    report = Report.query.get_or_404(report_id)
    try:
        svc.self_execute_and_close(report, actor=current_user, note=request.form.get("note"))
        flash("تم تنفيذ البلاغ وإغلاقه", "success")
    except (svc.ReportPermissionError, svc.ReportStateError) as e:
        flash(str(e), "error")
    return _redirect_back(report_id)


@team_bp.route("/reports/<int:report_id>/close", methods=["POST"])
@login_required
def report_close(report_id):
    report = Report.query.get_or_404(report_id)
    try:
        svc.close_report(report, actor=current_user, note=request.form.get("note"))
        flash("تم إغلاق البلاغ", "success")
    except (svc.ReportPermissionError, svc.ReportStateError) as e:
        flash(str(e), "error")
    return _redirect_back(report_id)


ROLE_FILTER_TABS = [
    ("all", "الكل"),
    ("worker", "العامل"),
    ("doctor", "الطبيب البيطري"),
    ("accountant", "المحاسب"),
]

# قائمة مختارة لفورم "توزيع مهمة" اليدوي (بند إضافي 69) — مو كل 26 قيمة
# فعلية لـ`task_type` (أغلبها تتولّد آلياً من محركات النظام نفسها، مو
# شي يختاره المستخدم يدوياً) — بس الأنواع المعقولة لمهمة يوزّعها إنسان
# مباشرة. "shearing" أُزيلت (كانت خياراً ميتاً — تأكّدت بفحص الكود إن
# ما فيه أي مكان يُنشئ مهمة بهذا النوع فعلياً).
MANUAL_TASK_TYPE_OPTIONS = [
    ("custom", "مهمة عامة"),
    ("isolation_check", "فحص عزل"),
    ("weighing", "وزن"),
    ("vaccination_due", "تحصين مستحق"),
    ("feed_switch", "تبديل علف"),
    ("doctor_review", "مراجعة الدكتور"),
]


@team_bp.route("/tasks")
@login_required
def tasks_list():
    # ترتيب ثانوي بـsort_order (بند إضافي 67) — يفرض تسلسل العمل الميداني
    # المنطقي (تنظيف ← ماء/علف ← فحص قطيع) لما أكثر من مهمة يتشاركون
    # نفس due_date، بدل الاعتماد على ترتيب إدراج قاعدة البيانات غير المضمون.
    my_tasks = (Task.query
                .filter(Task.assignee_id == current_user.id, Task.status.in_(["pending", "in_progress"]))
                .order_by(Task.due_date, Task.sort_order).all())
    suggested = []
    review_box = []
    assigned_by_me = []
    role_filter = request.args.get("role", "all")
    if role_filter not in dict(ROLE_FILTER_TABS):
        role_filter = "all"
    if current_user.has_permission("tasks.review_daily"):
        suggested = Task.query.filter_by(status="suggested").order_by(Task.due_date, Task.sort_order).all()
        # فلترة حسب الدور المستهدف (بند إضافي 68) — تطابق target_role
        # الصريح، أو دور الشخص المعيّن فعلاً لو ما فيه target_role
        # مسجَّل (مهام قديمة أو مُنشأة قبل هذا البند).
        if role_filter != "all":
            suggested = [
                t for t in suggested
                if t.target_role == role_filter
                or (not t.target_role and t.assignee and t.assignee.role and t.assignee.role.name == role_filter)
            ]
    if current_user.has_permission("tasks.delete_final"):
        review_box = Task.query.filter_by(status="deleted_pending_review").order_by(Task.updated_at.desc()).all()
    if current_user.has_permission("tasks.assign_any"):
        assigned_by_me = (Task.query
                          .filter(Task.created_by_id == current_user.id, Task.status.in_(["pending", "in_progress"]))
                          .order_by(Task.due_date, Task.sort_order).all())
    # "جدول المهام المعتمدة" (بند إضافي 70) — نظرة عامة على كل المهام
    # المعتمدة (المولَّدة تلقائياً بعد اعتمادها، أو المعيَّنة يدوياً)
    # عبر المزرعة كلها، بغض النظر عن مين المكلَّف بها — يختلف عن "مهامي"
    # (خاصة بالمستخدم الحالي بس) و"مهام وزّعتها" (خاصة بمن أنشأها يدوياً
    # بس). مرئية لمن يملك صلاحية مراجعة/توزيع المهام (نفس مجموعة صلاحيات
    # "مهام مقترحة").
    approved_tasks = []
    if current_user.has_permission("tasks.review_daily") or current_user.has_permission("tasks.assign_any"):
        approved_tasks = (Task.query
                           .filter(Task.status.in_(["pending", "in_progress"]))
                           .order_by(Task.due_date, Task.sort_order).all())
    modal_context = {}
    if current_user.has_permission("tasks.assign_any"):
        # نفس بيانات فورم "توزيع مهمة" (بند إضافي 69) — تُحمَّل هنا
        # عشان النافذة المنبثقة الجديدة تفتح فوراً بدون طلب شبكة إضافي.
        modal_context = dict(
            workers=User.query.filter_by(is_active_account=True).order_by(User.name).all(),
            barns=Barn.query.order_by(Barn.barn_name).all(),
            animals=Animal.query.order_by(Animal.animal_no).all(),
            open_tasks=Task.query.filter(Task.status.in_(["pending", "in_progress", "suggested"])).order_by(Task.due_date).all(),
            task_type_options=MANUAL_TASK_TYPE_OPTIONS,
        )
    return render_template(
        "team/tasks_list.html",
        my_tasks=my_tasks, suggested=suggested, review_box=review_box, assigned_by_me=assigned_by_me,
        approved_tasks=approved_tasks,
        today=date.today(), role_tabs=ROLE_FILTER_TABS, active_role=role_filter,
        **modal_context,
    )


@team_bp.route("/tasks/<int:task_id>")
@login_required
def task_detail(task_id):
    """التفصيل الشامل للمهمة (بند إضافي 50) — سبب المهمة، الدفعة/
    الحظيرة/عدد الرؤوس، الدواء والجرعة الإجمالية، حالة المخزون الحالي
    والمتوقع بعد التنفيذ، والمهمة التالية بسلسلة الأتمتة. مسموحة
    لصاحبها أو لمن يملك صلاحية مراجعة/توزيع المهام."""
    task = Task.query.get_or_404(task_id)
    if not (
        task.assignee_id == current_user.id
        or current_user.has_permission("tasks.review_daily")
        or current_user.has_permission("tasks.assign_any")
    ):
        abort(403)
    ctx = tsvc.task_rich_context(task)
    return render_template("team/task_detail.html", task=task, ctx=ctx, today=date.today(),
                            failure_reasons=tsvc.FAILURE_REASONS)


@team_bp.route("/tasks/new", methods=["GET", "POST"])
@login_required
@require_permission("tasks.assign_any")
def tasks_new():
    if request.method == "POST":
        try:
            tsvc.assign_task(
                actor=current_user,
                title=request.form["title"],
                task_type=request.form.get("task_type") or "custom",
                assignee_id=request.form.get("assignee_id") or None,
                barn_id=request.form.get("barn_id") or None,
                animal_id=request.form.get("animal_id") or None,
                due_date=date.fromisoformat(request.form["due_date"]) if request.form.get("due_date") else None,
                requires_photo=bool(request.form.get("requires_photo")),
                notes=request.form.get("notes"),
                depends_on_task_id=request.form.get("depends_on_task_id") or None,
                target_role=request.form.get("target_role") or None,
            )
            flash("تم توزيع المهمة", "success")
            return redirect(url_for("team.tasks_list"))
        except tsvc.TaskPermissionError as e:
            flash(str(e), "error")
    open_tasks = Task.query.filter(Task.status.in_(["pending", "in_progress", "suggested"])).order_by(Task.due_date).all()
    return render_template(
        "team/task_form.html",
        workers=User.query.filter_by(is_active_account=True).order_by(User.name).all(),
        barns=Barn.query.order_by(Barn.barn_name).all(),
        animals=Animal.query.order_by(Animal.animal_no).all(),
        open_tasks=open_tasks,
        task_type_options=MANUAL_TASK_TYPE_OPTIONS,
        role_tabs=ROLE_FILTER_TABS,
    )


@team_bp.route("/tasks/<int:task_id>/start", methods=["POST"])
@login_required
def task_start(task_id):
    task = Task.query.get_or_404(task_id)
    try:
        tsvc.start_task(task, actor=current_user)
        flash("بدأت المهمة", "success")
    except (tsvc.TaskPermissionError, tsvc.TaskStateError) as e:
        flash(str(e), "error")
    return redirect(url_for("team.tasks_list"))


@team_bp.route("/tasks/<int:task_id>/complete", methods=["POST"])
@login_required
def task_complete(task_id):
    task = Task.query.get_or_404(task_id)
    try:
        tsvc.complete_task(
            task, actor=current_user, note=request.form.get("note"),
            evidence_image_url=svc.save_evidence_image(request.files.get("evidence_image")),
            voice_note_url=svc.save_voice_note(request.files.get("voice_note")),
        )
        flash("تم إنجاز المهمة", "success")
    except (tsvc.TaskPermissionError, tsvc.TaskStateError) as e:
        flash(str(e), "error")
    return redirect(request.referrer or url_for("team.tasks_list"))


@team_bp.route("/tasks/<int:task_id>/fail", methods=["POST"])
@login_required
def task_fail(task_id):
    """تعذّر تنفيذ المهمة (بند إضافي 54) — العامل يسجّل صراحة سبب عدم
    الإنجاز بدل ما يبقى صامتاً، مع ملاحظة وصورة/صوت اختياريين."""
    task = Task.query.get_or_404(task_id)
    try:
        tsvc.fail_task(
            task, actor=current_user, reason=request.form.get("reason"),
            note=request.form.get("note"),
            evidence_image_url=svc.save_evidence_image(request.files.get("evidence_image")),
            voice_note_url=svc.save_voice_note(request.files.get("voice_note")),
        )
        flash("تم تسجيل تعذّر المهمة", "success")
    except (tsvc.TaskPermissionError, tsvc.TaskStateError) as e:
        flash(str(e), "error")
    return redirect(request.referrer or url_for("team.tasks_list"))


@team_bp.route("/tasks/<int:task_id>/approve", methods=["POST"])
@login_required
def task_approve(task_id):
    task = Task.query.get_or_404(task_id)
    try:
        tsvc.approve_suggested_task(task, actor=current_user)
        flash("تم اعتماد المهمة — نزلت للعامل", "success")
    except (tsvc.TaskPermissionError, tsvc.TaskStateError) as e:
        flash(str(e), "error")
    return redirect(url_for("team.tasks_list"))


@team_bp.route("/tasks/<int:task_id>/postpone", methods=["POST"])
@login_required
def task_postpone(task_id):
    task = Task.query.get_or_404(task_id)
    # بند إضافي 72 — زر تأجيل بضغطة وحدة بلا خانة تاريخ يدوية: يؤجّل
    # ليوم واحد من موعدها الحالي (أو من اليوم لو ما فيها موعد أصلاً).
    # لسا نقبل due_date صريح لو انبعث (توافق خلفي)، بس الفورم الجديد
    # ما يرسله.
    due_date_raw = request.form.get("due_date")
    if due_date_raw:
        new_due_date = date.fromisoformat(due_date_raw)
    else:
        new_due_date = (task.due_date or date.today()) + timedelta(days=1)
    try:
        tsvc.postpone_suggested_task(task, actor=current_user, new_due_date=new_due_date)
        flash("تم تأجيل المهمة ليوم واحد", "success")
    except (tsvc.TaskPermissionError, tsvc.TaskStateError) as e:
        flash(str(e), "error")
    return redirect(url_for("team.tasks_list"))


@team_bp.route("/tasks/<int:task_id>/soft-delete", methods=["POST"])
@login_required
def task_soft_delete(task_id):
    task = Task.query.get_or_404(task_id)
    try:
        tsvc.soft_delete_suggested_task(task, actor=current_user, reason=request.form.get("reason"))
        flash("تم حذف المهمة — انتقلت لصندوق مراجعة صاحب الحلال", "success")
    except (tsvc.TaskPermissionError, tsvc.TaskStateError) as e:
        flash(str(e), "error")
    return redirect(url_for("team.tasks_list"))


@team_bp.route("/tasks/<int:task_id>/restore", methods=["POST"])
@login_required
def task_restore(task_id):
    task = Task.query.get_or_404(task_id)
    try:
        tsvc.owner_restore_task(task, actor=current_user)
        flash("تم استرجاع المهمة", "success")
    except (tsvc.TaskPermissionError, tsvc.TaskStateError) as e:
        flash(str(e), "error")
    return redirect(url_for("team.tasks_list"))


@team_bp.route("/tasks/<int:task_id>/delete-final", methods=["POST"])
@login_required
def task_delete_final(task_id):
    task = Task.query.get_or_404(task_id)
    try:
        tsvc.owner_delete_task_final(task, actor=current_user)
        flash("تم حذف المهمة نهائياً", "success")
    except (tsvc.TaskPermissionError, tsvc.TaskStateError) as e:
        flash(str(e), "error")
    return redirect(url_for("team.tasks_list"))


@team_bp.route("/worker/report/<category>", methods=["GET", "POST"])
@login_required
@require_permission("reports.submit")
def worker_quick_report(category):
    cfg = WORKER_REPORT_CATEGORIES.get(category)
    if not cfg:
        abort(404)

    barn_ids = _scoped_barn_ids()
    if request.method == "POST":
        # سلامة البيانات (بند إضافي، 2026-07-23) — نفس قاعدة `reports_new`،
        # موثّقة هناك.
        if not request.form.get("animal_id") and not request.form.get("barn_id"):
            flash("لازم تحدد الحيوان أو الحظيرة على الأقل قبل الإرسال", "error")
            return redirect(url_for("team.worker_quick_report", category=category))
        scope_error = _validate_scoped_report(barn_ids, request.form.get("animal_id"), request.form.get("barn_id"))
        if scope_error:
            flash(scope_error, "error")
            return redirect(url_for("team.worker_quick_report", category=category))
        svc.submit_report(
            reporter=current_user,
            description=request.form["description"],
            report_type=cfg["report_type"],
            animal_id=request.form.get("animal_id") or None,
            barn_id=request.form.get("barn_id") or None,
            evidence_image_url=svc.save_evidence_image(request.files.get("evidence_image")),
            evidence_audio_url=svc.save_voice_note(request.files.get("voice_note")),
        )
        flash("تم رفع البلاغ — راح يوصل للدكتور", "success")
        return redirect(url_for("core.home"))

    animals_query = Animal.query.filter_by(status="active")
    if cfg["species_filter"]:
        animals_query = animals_query.filter_by(species=cfg["species_filter"])
    barns_query = Barn.query
    if barn_ids is not None:
        animals_query = animals_query.filter(Animal.barn_id.in_(barn_ids))
        barns_query = barns_query.filter(Barn.id.in_(barn_ids))
    my_tasks = []
    if cfg["task_types"]:
        my_tasks = (Task.query
                    .filter(Task.assignee_id == current_user.id,
                            Task.status.in_(["pending", "in_progress"]),
                            Task.task_type.in_(cfg["task_types"]))
                    .order_by(Task.due_date).all())

    return render_template(
        "team/worker_report_form.html",
        category=category, cfg=cfg, my_tasks=my_tasks,
        animals=animals_query.order_by(Animal.animal_no).all(),
        barns=barns_query.order_by(Barn.barn_name).all(),
        scoped=barn_ids is not None,
    )


@team_bp.route("/reports/<int:report_id>/delete", methods=["POST"])
@login_required
def report_delete(report_id):
    report = Report.query.get_or_404(report_id)
    try:
        svc.delete_cancelled_report(report, actor=current_user)
        flash("تم حذف البلاغ نهائياً", "success")
        return redirect(url_for("team.reports_list"))
    except (svc.ReportPermissionError, svc.ReportStateError) as e:
        flash(str(e), "error")
        return _redirect_back(report_id)
