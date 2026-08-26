from datetime import date, time
from flask import render_template, request, redirect, url_for, flash, jsonify, abort, send_file, current_app
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.core import core_bp
from app.core.animal_service import create_animal, add_weight_record, add_note, add_milk_record
from app.core import cycle_engine
from app.core import animal_profile_service
from app.core import animal_filters_service
from app.core import bulk_service
from app.core import smart_sale_service
from app.core import alerts_service
from app.core import backup_service
from app.core import readiness_service
from app.core import isolation_service
from app.auth.decorators import require_permission
from app.extensions import db
from app.models import Animal, Barn, BarnFeedingSchedule, ServiceToggle, Role, Permission, AuditLog, CycleEvent, FarmSettings, Finance
from app.models import SpeciesType, Breed, AnimalColor, Task, Report
from app.models.animal import AnimalSource
from app.permissions_registry import PERMISSIONS


@core_bp.route("/settings/language", methods=["POST"])
@login_required
def set_language():
    """
    تبديل لغة الواجهة الشخصية (بند إضافي، 2026-07-23) — أي مستخدم يقدر
    يغيّر لغته هو بس، بدون أي صلاحية خاصة (نفس فلسفة "غيّر كلمة مرورك
    أنت" لو كانت موجودة). النطاق الحالي مقصور على شاشات الإدخال الميداني
    (عامل/دكتور/ممرض) — راجع بند 44 بـMASTER_SPEC.md.
    """
    lang = request.form.get("language")
    if lang in current_app.config["SUPPORTED_LANGUAGES"]:
        current_user.language = lang
        db.session.commit()
    return redirect(request.referrer or url_for("core.home"))


@core_bp.route("/settings/theme", methods=["POST"])
@login_required
def set_theme():
    """تبديل الوضع الليلي/النهاري الشخصي (بند إضافي 158) — نفس فلسفة
    `set_language` بالضبط: أي مستخدم يبدّل تفضيله هو بس، بدون صلاحية
    خاصة، ويُحفَظ بحسابه فيرجع معه بأي جهاز يسجّل دخول منه."""
    theme = request.form.get("theme")
    if theme in ("light", "dark"):
        current_user.theme = theme
        db.session.commit()
    return redirect(request.referrer or url_for("core.home"))


@core_bp.route("/settings/set-ui-level", methods=["POST"])
@login_required
def set_ui_level():
    """تبديل مستوى تبسيط الواجهة (بند إضافي 225) — نفس فلسفة
    `set_theme` بالضبط."""
    level = request.form.get("ui_level")
    if level in ("normal", "simple"):
        current_user.ui_level = level
        db.session.commit()
    return redirect(request.referrer or url_for("core.home"))


@core_bp.route("/settings/send-test-email-report", methods=["POST"])
@login_required
def send_test_email_report():
    """زر "أرسل تقرير تجريبي الآن" (بند إضافي 160، المرحلة ج) — يسمح
    لمن يدير البلاغات يتأكد إن إعداد Resend يشتغل فعلياً بدون انتظار
    الجدولة اليومية التلقائية."""
    if not current_user.has_permission("reports.manage"):
        abort(403)
    from app.core.daily_email_report_service import send_daily_report_now
    sent = send_daily_report_now()
    if sent:
        flash(f"تم إرسال التقرير فعلياً لعدد {sent} من المستخدمين.", "success")
    else:
        flash("ما نجح أي إرسال — تأكد إن بريدك مسجَّل وإن متغيرات Resend مضبوطة صحيح.", "error")
    return redirect(request.referrer or url_for("core.home"))


@core_bp.route("/catalog/<token>")
def sales_catalog(token):
    """كتالوج مبيعات عام (بند إضافي 185) — بدون تسجيل دخول، رابط
    مشاركة واحد بالرمز السري لكل مزرعة. يعرض حصراً الرؤوس النشطة
    بغرض "بيع" — صفر بيانات حساسة (مالية، صحية تفصيلية، أسماء فريق)."""
    fs = FarmSettings.get()
    if not fs.sales_catalog_token or token != fs.sales_catalog_token:
        abort(404)
    animals = Animal.query.filter_by(status="active", purpose="بيع").order_by(Animal.animal_no).all()
    from app.core.animal_profile_service import _age_label
    rows = [{
        "animal": a, "age_label": _age_label(a.birth_date),
        "estimated_value": a.workflow.estimated_value if a.workflow else None,
    } for a in animals]
    return render_template("catalog_public.html", rows=rows, farm_settings=fs)


@core_bp.route("/lot/<token>")
def lot_public(token):
    """بروفايل تجاري عام لدفعة بيع (بند إضافي 191.3) — بدون تسجيل
    دخول، عبر رمز مشاركة الدفعة نفسها (منفصل عن رمز الكتالوج العام).
    صفر بيانات مالية داخلية (تكلفة/هامش ربح) — بس ما يهم المشتري."""
    from app.models import SalesLot
    from app.core import sales_lot_service as svc
    lot = SalesLot.query.filter_by(share_token=token).first()
    if not lot:
        abort(404)
    rows = [svc.animal_lot_row(item.animal) for item in lot.items]
    stats = svc.lot_stats(rows)
    return render_template("lot_public.html", lot=lot, rows=rows, stats=stats)


@core_bp.route("/settings/catalog-token/regenerate", methods=["POST"])
@login_required
@require_permission("settings.manage")
def regenerate_catalog_token():
    fs = FarmSettings.get()
    import secrets
    fs.sales_catalog_token = secrets.token_urlsafe(24)
    db.session.commit()
    flash("تم توليد رابط كتالوج جديد — الرابط القديم ما عاد يشتغل", "success")
    return redirect(url_for("core.settings_home"))


@core_bp.route("/")
@login_required
def home():
    """
    نفس الرابط لكل الأدوار، لكن كل واحد يشوف واجهته هو بس — هذا هو مبدأ
    "واجهة حسب الدور" اللي اتفقنا عليه: القالب يقرر شنو يعرض حسب صلاحيات
    current_user، بدون ما نحتاج شاشات منفصلة بروابط مختلفة لكل دور.

    استثناء واحد مقصود (بند 27): دور "العامل" تحديداً (نفس اسم الدور
    الداخلي الثابت بـ`permissions_registry.py`، مو المسمّى الوظيفي القابل
    للتخصيص) يشوف واجهة مبسّطة منفصلة تماماً (5 أزرار كبيرة) بدل اللوحة
    العامة — العامل ميداني، يحتاج أقل احتكاك ممكن، مو لوحة تحكم عامة
    فيها أقسام فاضية حسب صلاحياته المحدودة.
    """
    from app.core import checklist_service
    daily_checklist = checklist_service.daily_checklist_for(current_user)

    if current_user.role.name == "worker":
        my_alerts_count = len(alerts_service.get_alerts(barn_ids=_my_barn_ids(current_user)))
        return render_template(
            "worker_home.html", user=current_user, my_alerts_count=my_alerts_count,
            daily_checklist=daily_checklist,
        )

    # مستوى "بسيط جداً" (بند إضافي 225) — تفضيل شخصي، يبدّل الشاشة
    # الرئيسية بس، نفس البيانات ونفس الصلاحيات تماماً. العامل مستثنى
    # (له أصلاً worker_home.html أبسط أساساً، لا يحتاج مستوى ثانٍ).
    if current_user.ui_level == "simple":
        return render_template("simple_home.html", user=current_user)

    today_tasks_count = today_alerts_count = None
    if current_user.has_permission("tasks.view_own") or current_user.has_permission("animals.view"):
        today_tasks_count, today_alerts_count = _today_counts(current_user)

    vaccinations_overdue_count = vaccinations_upcoming_count = None
    if current_user.has_permission("health.view"):
        vaccinations_overdue_count, vaccinations_upcoming_count = alerts_service.vaccination_counts()

    # إجمالي تنبيهات مربوطة برؤوس محدَّدة (بند إضافي 214) — فقعة على
    # زر "الحيوانات" بالإجراءات السريعة، تجمع كل تنبيه فيه animal_id
    # (بيانات ناقصة، أمراض مفتوحة، وزن متأخر...) بعدد واحد إجمالي —
    # عكس فقعتي التطعيمات اللي منفصلتين لأنها بحاجة تمييز متأخر/قادم.
    animals_alerts_count = None
    if current_user.has_permission("animals.view"):
        animals_alerts_count = sum(alerts_service.alert_counts_by_animal().values())

    return render_template(
        "home.html", user=current_user,
        today_tasks_count=today_tasks_count, today_alerts_count=today_alerts_count,
        vaccinations_overdue_count=vaccinations_overdue_count,
        vaccinations_upcoming_count=vaccinations_upcoming_count,
        animals_alerts_count=animals_alerts_count,
    )


@core_bp.route("/setup-checklist/dismiss", methods=["POST"])
@login_required
def setup_checklist_dismiss():
    """صاحب الحلال بس يقدر يتجاهلها — نفس منطق أي إعداد عام للمزرعة."""
    if current_user.role.name != "owner":
        abort(403)
    settings = FarmSettings.get()
    settings.setup_checklist_dismissed = True
    db.session.commit()
    return redirect(url_for("core.home"))


def _my_barn_ids(user) -> list[int]:
    return [b.id for b in Barn.query.filter_by(responsible_worker_id=user.id).all()]


def _today_counts(user) -> tuple[int, int]:
    """عدد المهام المفتوحة (pending/in_progress) وعدد التنبيهات النشطة
    لهذا المستخدم — نفس استعلامات `today()` بالضبط، بس عدّ بدل جلب
    الصفوف كاملة، مستخدَمة ببطاقة "صفحة اليوم" بالرئيسية (بند إضافي
    206) عشان تعرض رقمين حقيقيين بدل وصف عام بدون أرقام."""
    my_role_name = user.role.name if user.role else None
    tasks_count = (Task.query
                   .filter(
                       Task.status.in_(["pending", "in_progress"]),
                       db.or_(
                           Task.assignee_id == user.id,
                           db.and_(Task.assignee_id.is_(None), Task.target_role == my_role_name),
                       ),
                   ).count())
    if user.has_permission("animals.view"):
        alerts_count = len(alerts_service.get_alerts())
    else:
        alerts_count = len(alerts_service.get_alerts(barn_ids=_my_barn_ids(user)))
    return tasks_count, alerts_count


@core_bp.route("/alerts")
@login_required
@require_permission("animals.view")
def alerts_list():
    return render_template("alerts_list.html", alerts=alerts_service.get_alerts())


@core_bp.route("/alerts/mine")
@login_required
def alerts_mine():
    """
    تنبيهاتي — نفس محرك التنبيهات (بند 20) لكن مقصور على الحظائر اللي
    أنا مسؤول عنها (بند إضافي، 2026-07-23). بدون فحص `animals.view` عمداً
    — العامل (اللي ما يملكها أصلاً) هو المستخدم الأساسي لهذي الشاشة،
    والفلترة بحظائره هو تحديداً كافية أمنياً (ما يشوف غير حظائره).
    """
    my_barn_ids = _my_barn_ids(current_user)
    alerts = alerts_service.get_alerts(barn_ids=my_barn_ids)
    return render_template("alerts_list.html", alerts=alerts, mine=True, my_barn_ids=my_barn_ids)


@core_bp.route("/today")
@login_required
def today():
    """صفحة اليوم (بند إضافي 122) — تجمع مهامي المفتوحة، تنبيهاتي،
    وبلاغاتي المفتوحة بشاشة وحدة، بدل ما يتنقّل المستخدم بين 3 شاشات كل
    صباح. لا منطق جديد — نفس استعلامات tasks_list/alerts_mine/reports_list
    الموجودة أصلاً، مجمَّعة هنا للعرض بس.

    تنبيهات (بند إضافي 136): لمن يملك `animals.view` (المالك/الدكتور —
    عادةً ما هم "عامل مسؤول" رسمياً عن حظيرة معيّنة، فـ`_my_barn_ids`
    ترجع فاضية لهم) تُعرض كل تنبيهات المزرعة هنا مباشرة — نفس محتوى
    شاشة "التنبيهات" المنفصلة القديمة بالضبط، اللي صار رابطها بالقائمة
    الجانبية مكرراً فأُزيل (قرارك الصريح). العامل يبقى يشوف تنبيهات
    حظائره بس، زي ما كان."""
    my_role_name = current_user.role.name if current_user.role else None
    my_tasks = (Task.query
                .filter(
                    Task.status.in_(["pending", "in_progress"]),
                    db.or_(
                        Task.assignee_id == current_user.id,
                        db.and_(Task.assignee_id.is_(None), Task.target_role == my_role_name),
                    ),
                )
                .order_by(Task.due_date, Task.sort_order).all())

    if current_user.has_permission("animals.view"):
        alerts = alerts_service.get_alerts()
    else:
        alerts = alerts_service.get_alerts(barn_ids=_my_barn_ids(current_user))

    my_open_reports = []
    if current_user.has_permission("reports.submit"):
        my_open_reports = (Report.query
                            .filter(Report.reporter_id == current_user.id,
                                    Report.status.notin_(["closed", "cancelled"]))
                            .order_by(Report.created_at.desc()).all())

    return render_template(
        "today.html", my_tasks=my_tasks, alerts=alerts,
        my_open_reports=my_open_reports, today=date.today(),
    )


def _animals_list_context(*, bulk_mode: bool) -> dict:
    """سياق مشترك بين "سجل الحيوانات" (تصفح عادي) و"الإجراء الجماعي"
    (بند إضافي 132) — نفس منطق الفلترة بالضبط، الفرق الوحيد هو
    `bulk_mode` اللي يتحكم بعرض عمود التأشير وشريط الإجراء الجماعي
    بالقالب."""
    from app.health.health_service import animal_under_withdrawal

    filter_key = request.args.get("filter", "all")
    if filter_key not in animal_filters_service.FILTERS:
        filter_key = "all"
    animals = animal_filters_service.get_filtered(filter_key)

    # فلترة بحظيرة كاملة (بند إضافي، 2026-07-24) — طلبك "عمليات جماعية
    # لدفعة أو حظيرة كاملة": يحصر القائمة بحظيرة واحدة، و"تحديد الكل"
    # الموجود أصلاً بأعلى الشاشة يصير عملياً "تحديد كل رؤوس الحظيرة"
    # بمجرد الفلترة — بدون أي منطق تحديد إضافي منفصل.
    barn_filter_id = request.args.get("barn_id")
    if barn_filter_id:
        animals = [a for a in animals if a.barn_id == int(barn_filter_id)]

    withdrawal_map = {a.id: animal_under_withdrawal(a.id) for a in animals}
    alert_counts = alerts_service.alert_counts_by_animal()
    return dict(
        animals=animals, withdrawal_map=withdrawal_map, alert_counts=alert_counts, today=date.today(),
        filters=animal_filters_service.FILTERS, active_filter=filter_key,
        counts=animal_filters_service.get_counts(),
        barns=Barn.query.order_by(Barn.barn_name).all(),
        active_barn_id=int(barn_filter_id) if barn_filter_id else None,
        bulk_mode=bulk_mode,
    )


@core_bp.route("/animals")
@login_required
@require_permission("animals.view")
def animals_list():
    return render_template("animals_list.html", **_animals_list_context(bulk_mode=False))


@core_bp.route("/animals/simple")
@login_required
@require_permission("animals.view")
def animals_list_simple():
    """سجل الحيوانات — واجهة "بسيط جداً" (بند إضافي 227): بطاقات كبيرة
    بصورة/أيقونة بدل جدول بأعمدة، بدون فلاتر. نفس بيانات `animals_list`
    (كل الرؤوس النشطة)، بس عرض مختلف بالكامل."""
    animals = animal_filters_service.get_filtered("all")
    alert_counts = alerts_service.alert_counts_by_animal()
    return render_template("animals_list_simple.html", animals=animals, alert_counts=alert_counts)


@core_bp.route("/animals/bulk")
@login_required
@require_permission("animals.view")
def animals_bulk_home():
    """شاشة "الإجراء الجماعي" (بند إضافي 132) — نفس شاشة سجل الحيوانات
    بالضبط بس مع شريط التأشير الجماعي، بدل ما تكون مدمجة داخل سجل
    الحيوانات العادي (كانت قبل هذا البند). مربوطة من القائمة الجانبية
    بدل رابط "دفعات استقبال جديدة" السابق — شاشة الحجر الصحي نفسها
    (`batches.batches_list`) لسا موجودة زي ما هي، بس صار الوصول لها عبر
    زر "🏥 متابعة الحجر الصحي" بأعلى هذي الشاشة بدل رابط جانبي مستقل."""
    return render_template("animals_list.html", **_animals_list_context(bulk_mode=True))


@core_bp.route("/animals/smart-sale")
@login_required
@require_permission("animals.view")
def smart_sale_report():
    rows = smart_sale_service.get_recommendations()
    return render_template("smart_sale_report.html", rows=rows)


@core_bp.route("/animals/<int:animal_id>/repro-flags", methods=["POST"])
@login_required
@require_permission("health.manage")
def animal_repro_flags_save(animal_id):
    animal = Animal.query.get_or_404(animal_id)

    def _bool(field):
        value = request.form.get(field)
        return {"yes": True, "no": False}.get(value)

    animal.refuses_nursing = _bool("refuses_nursing")
    animal.udder_damaged = _bool("udder_damaged")
    db.session.add(animal)
    db.session.commit()
    flash("تم حفظ علامات البيع", "success")
    return redirect(url_for("core.animal_detail", animal_id=animal.id, tab="summary"))


BULK_ACTIONS = {
    "weight": _l("وزن جماعي"),
    "vaccination": _l("تحصين جماعي"),
    "note": _l("ملاحظة جماعية"),
    "barn_move": _l("نقل حظيرة جماعي"),
    "purpose": _l("تحديد الغرض جماعياً (تربية/تسمين/بيع)"),
    "sale": _l("بيع جماعي"),
    "mark_dead": _l("تسجيل نفوق جماعي"),
    "disease": _l("علاج/مرض جماعي"),
    "isolation": _l("عزل جماعي"),
    "sonar": _l("فحص سونار جماعي"),
    "treatment_plan": _l("خطة علاج مخطَّط (بانتظار تأكيد التنفيذ)"),
}


@core_bp.route("/animals/bulk/select", methods=["POST"])
@login_required
@require_permission("animals.view")
def animals_bulk_select():
    from app.models import Pharmacy, Doctor, DiseaseType

    action = request.form.get("bulk_action")
    # "استقبال دفعة جديدة" (بند إضافي 132) — مو إجراء يُطبَّق على رؤوس
    # مؤشَّرة مسبقاً (هذي رؤوس جديدة أصلاً لسا ما انسجلت)، فتوجيه مباشر
    # لنفس نموذج الشراء الجماعي القديم بدل المرور بمنطق التأشير تحت.
    if action == "new_batch":
        return redirect(url_for("core.animals_bulk_purchase"))

    animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
    if not animal_ids:
        flash("لازم تحدد رأس واحد على الأقل", "error")
        return redirect(url_for("core.animals_bulk_home"))
    if action not in BULK_ACTIONS:
        flash("إجراء جماعي غير معروف", "error")
        return redirect(url_for("core.animals_bulk_home"))

    animals = Animal.query.filter(Animal.id.in_(animal_ids)).order_by(Animal.animal_no).all()
    # عمر كل رأس بالأيام (بند إضافي 60) — يُستخدم بس لعرض/مطابقة جدول
    # الجرعة حسب العمر بشاشة التحصين الجماعي (`PharmacyDoseRule`)، مو
    # لحساب أي جرعة — مجرد قيمة معروضة على الرأس نفسه.
    for a in animals:
        a.age_days = (date.today() - a.birth_date).days if a.birth_date else None
    return render_template(
        "bulk_action_form.html", animals=animals, action=action,
        action_label=BULK_ACTIONS[action], today=date.today().isoformat(),
        barns=Barn.query.order_by(Barn.barn_name).all(),
        pharmacies=Pharmacy.query.filter_by(status="active").all(),
        vaccines=Pharmacy.query.filter_by(status="active", medicine_class="vaccine").all(),
        doctors=Doctor.query.filter_by(status="active").all(),
        disease_types=DiseaseType.query.order_by(DiseaseType.name).all(),
    )


@core_bp.route("/animals/bulk/apply/weight", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animals_bulk_apply_weight():
    animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
    record_date = date.fromisoformat(request.form["date"])
    weights_by_id = {}
    notes_by_id = {}
    for animal_id in animal_ids:
        w = request.form.get(f"weight_{animal_id}")
        if w:
            weights_by_id[animal_id] = float(w)
        n = request.form.get(f"note_{animal_id}")
        if n:
            notes_by_id[animal_id] = n
    results = bulk_service.apply_bulk_weight(
        animal_ids=animal_ids, record_date=record_date,
        weights_by_id=weights_by_id, notes_by_id=notes_by_id, actor_user_id=current_user.id,
    )
    done = sum(1 for r in results.values() if r.startswith("تم"))
    flash(f"وزن جماعي: {done} من {len(animal_ids)} تم تسجيلهم", "success")
    return redirect(url_for("core.animals_bulk_home"))


@core_bp.route("/animals/bulk/apply/vaccination", methods=["POST"])
@login_required
@require_permission("health.manage")
def animals_bulk_apply_vaccination():
    from app.models import Pharmacy

    animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
    record_date = date.fromisoformat(request.form["date"])

    # لقاحين بحد أقصى بنفس الجلسة (بند إضافي 60) — كل لقاح مربوط إلزامياً
    # بدواء صيدلية فعلي من فئة "لقاح"، وكل رأس له مربع تأشير مستقل لكل
    # لقاح (اللي ما تؤشر عليه ما ينحصّن به إطلاقاً).
    vaccine_slots = []
    for slot_no in (1, 2):
        pharmacy_id = request.form.get(f"vaccine_{slot_no}_pharmacy_id")
        if not pharmacy_id:
            continue
        pharmacy = Pharmacy.query.get(int(pharmacy_id))
        if not pharmacy or pharmacy.medicine_class != "vaccine":
            flash("لازم تختار لقاحاً فعلياً مسجَّلاً بالصيدلية بفئة (لقاح)", "error")
            return redirect(url_for("core.animals_bulk_home"))
        doses = {}
        for animal_id in animal_ids:
            if not request.form.get(f"vaccinated_{slot_no}_{animal_id}"):
                continue
            dose_raw = request.form.get(f"dose_{slot_no}_{animal_id}")
            doses[animal_id] = float(dose_raw) if dose_raw else None
        if doses:
            vaccine_slots.append({"pharmacy_id": pharmacy.id, "doses": doses})

    if not vaccine_slots:
        flash("لازم تختار لقاحاً واحداً على الأقل وتؤشر على رأس واحد فيه", "error")
        return redirect(url_for("core.animals_bulk_home"))

    results = bulk_service.apply_bulk_vaccination(
        record_date=record_date, actor_user_id=current_user.id, vaccine_slots=vaccine_slots,
    )
    done = sum(1 for r in results.values() if r == "تم")
    flash(f"تحصين جماعي: {done} تسجيل ناجح", "success")
    for (pharmacy_id, animal_id), r in results.items():
        if r.startswith("مرفوض"):
            flash(f"رأس #{animal_id}: {r}", "error")
    return redirect(url_for("core.animals_bulk_home"))


@core_bp.route("/animals/bulk/apply/note", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animals_bulk_apply_note():
    animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
    extra_notes_by_id = {
        animal_id: request.form.get(f"note_{animal_id}")
        for animal_id in animal_ids if request.form.get(f"note_{animal_id}")
    }
    results = bulk_service.apply_bulk_note(
        animal_ids=animal_ids,
        general_note=request.form["general_note"].strip(),
        note_date=date.fromisoformat(request.form["date"]) if request.form.get("date") else date.today(),
        extra_notes_by_id=extra_notes_by_id, actor_user_id=current_user.id,
    )
    flash(f"ملاحظة جماعية: أُضيفت لـ{len(results)} رأس", "success")
    return redirect(url_for("core.animals_bulk_home"))


@core_bp.route("/animals/bulk/apply/barn-move", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animals_bulk_apply_barn_move():
    animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
    results = bulk_service.apply_bulk_barn_move(
        animal_ids=animal_ids, barn_id=int(request.form["barn_id"]), actor_user_id=current_user.id,
    )
    flash(f"نقل حظيرة جماعي: تم نقل {len(results)} رأس", "success")
    return redirect(url_for("core.animals_bulk_home"))


@core_bp.route("/animals/bulk/apply/purpose", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animals_bulk_apply_purpose():
    animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
    results = bulk_service.apply_bulk_purpose(
        animal_ids=animal_ids, purpose=request.form["purpose"], actor_user_id=current_user.id,
    )
    flash(f"تحديد الغرض جماعياً: تم تحديد {len(results)} رأس", "success")
    return redirect(url_for("core.animals_bulk_home"))


@core_bp.route("/animals/bulk/apply/sale", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animals_bulk_apply_sale():
    animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
    sale_date = date.fromisoformat(request.form["date"]) if request.form.get("date") else date.today()
    prices_by_id = {}
    for animal_id in animal_ids:
        p = request.form.get(f"price_{animal_id}")
        if p:
            prices_by_id[animal_id] = float(p)
    results = bulk_service.apply_bulk_sale(
        animal_ids=animal_ids, sale_date=sale_date, prices_by_id=prices_by_id,
        notes=request.form.get("notes") or None, actor_user_id=current_user.id,
    )
    done = sum(1 for r in results.values() if r.startswith("تم"))
    flash(f"بيع جماعي: {done} من {len(animal_ids)} تم بيعهم — راجع التفاصيل أدناه لو فيه رؤوس مرفوضة", "success")
    for animal_id, r in results.items():
        if r.startswith("مرفوض"):
            flash(f"رأس #{animal_id}: {r}", "error")
        elif "تنبيه" in r:
            flash(f"رأس #{animal_id}: {r.split('— تنبيه: ')[-1]}", "warning")
    return redirect(url_for("core.animals_bulk_home"))


@core_bp.route("/animals/bulk/apply/mark-dead", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animals_bulk_apply_mark_dead():
    animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
    results = bulk_service.apply_bulk_mark_dead(
        animal_ids=animal_ids,
        death_date=date.fromisoformat(request.form["date"]) if request.form.get("date") else date.today(),
        reason=request.form.get("reason") or None, actor_user_id=current_user.id,
    )
    flash(f"تسجيل نفوق جماعي: تم تسجيله لـ{len(results)} رأس (بدون شرط اكتمال الدورة)", "success")
    return redirect(url_for("core.animals_bulk_home"))


@core_bp.route("/animals/bulk/apply/disease", methods=["POST"])
@login_required
@require_permission("health.manage")
def animals_bulk_apply_disease():
    animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
    results = bulk_service.apply_bulk_disease(
        animal_ids=animal_ids,
        disease_name=request.form["disease_name"].strip(),
        record_date=date.fromisoformat(request.form["date"]) if request.form.get("date") else date.today(),
        severity=request.form.get("severity") or None,
        pharmacy_id=request.form.get("pharmacy_id") or None,
        quantity_used_per_head=float(request.form["quantity_used_per_head"]) if request.form.get("quantity_used_per_head") else None,
        actor_user_id=current_user.id,
    )
    done = sum(1 for r in results.values() if r.startswith("تم"))
    flash(f"علاج/مرض جماعي: {done} من {len(animal_ids)} تم تسجيلهم", "success")
    for animal_id, r in results.items():
        if r.startswith("مرفوض"):
            flash(f"رأس #{animal_id}: {r}", "error")
    return redirect(url_for("core.animals_bulk_home"))


@core_bp.route("/animals/bulk/apply/treatment-plan", methods=["POST"])
@login_required
@require_permission("health.manage")
def animals_bulk_apply_treatment_plan():
    """خطة علاج جماعي (بند إضافي 50) — على عكس التحصين/العلاج الجماعي
    أعلاه (تسجيل فوري + خصم مباشر)، هذا الإجراء **ما يسجّل ولا يخصم أي
    شيء الآن** — بس يولّد مهمة "علاج مخطَّط" مقترحة لكل رأس محدَّد،
    كلها مرتبطة ببعضها كدفعة واحدة بالواجهة (source_id مشترك). الخصم
    الفعلي يصير فقط لما الطبيب يفتح "تأكيد التنفيذ" بكل مهمة على حدة."""
    from app.team import task_service as tsvc
    from app.models import Pharmacy

    animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
    pharmacy = Pharmacy.query.get_or_404(int(request.form["pharmacy_id"]))
    quantity_per_head = float(request.form["quantity_per_head"])
    treatment_kind = request.form["treatment_kind"]
    reason = request.form.get("reason")
    due = request.form.get("due_date")
    due_date = date.fromisoformat(due) if due else date.today()

    animals = Animal.query.filter(Animal.id.in_(animal_ids)).order_by(Animal.animal_no).all()
    created = []
    for animal in animals:
        task = tsvc.create_suggested_task(
            title=f'💊 تنفيذ علاج مخطَّط: {pharmacy.name} — {animal.animal_no}',
            task_type="planned_treatment",
            barn_id=animal.barn_id, animal_id=animal.id,
            due_date=due_date, source_type="BatchTreatmentPlan",
            notes=reason,
        )
        task.planned_pharmacy_id = pharmacy.id
        task.planned_quantity = quantity_per_head
        task.planned_treatment_kind = treatment_kind
        created.append(task)

    if created:
        batch_id = created[0].id
        for t in created:
            t.source_id = batch_id
        db.session.commit()

    flash(f"تم إنشاء خطة علاج لـ {len(created)} رأس — بانتظار مراجعة الدكتور وتأكيد التنفيذ لكل رأس.", "success")
    return redirect(url_for("team.tasks_list"))


@core_bp.route("/animals/bulk/apply/isolation", methods=["POST"])
@login_required
@require_permission("health.manage")
def animals_bulk_apply_isolation():
    animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
    results = bulk_service.apply_bulk_isolation(
        animal_ids=animal_ids, reason=request.form.get("reason") or None,
        note_date=date.fromisoformat(request.form["date"]) if request.form.get("date") else date.today(),
        actor_user_id=current_user.id,
    )
    done = sum(1 for r in results.values() if r.startswith("تم"))
    if done:
        flash(f"عزل جماعي: {done} من {len(animal_ids)} تم عزلهم", "success")
    for animal_id, r in results.items():
        if r.startswith("مرفوض"):
            flash(r, "error")
    return redirect(url_for("core.animals_bulk_home"))


@core_bp.route("/animals/bulk/apply/sonar", methods=["POST"])
@login_required
@require_permission("repro.manage")
def animals_bulk_apply_sonar():
    animal_ids = [int(x) for x in request.form.getlist("animal_ids")]
    result_by_id = {}
    embryo_count_by_id = {}
    for animal_id in animal_ids:
        r = request.form.get(f"result_{animal_id}")
        if r:
            result_by_id[animal_id] = r
        e = request.form.get(f"embryo_{animal_id}")
        if e:
            embryo_count_by_id[animal_id] = int(e)
    results = bulk_service.apply_bulk_sonar(
        animal_ids=animal_ids,
        exam_date=date.fromisoformat(request.form["date"]) if request.form.get("date") else date.today(),
        result_by_id=result_by_id, embryo_count_by_id=embryo_count_by_id,
        doctor_id=request.form.get("doctor_id") or None, actor_user_id=current_user.id,
    )
    flash(f"فحص سونار جماعي: تم تسجيله لـ{len(results)} رأس", "success")
    return redirect(url_for("core.animals_bulk_home"))


@core_bp.route("/animals/bulk-purchase", methods=["GET", "POST"])
@login_required
@require_permission("animals.manage")
def animals_bulk_purchase():
    if request.method == "POST":
        count = int(request.form.get("row_count", 0))
        rows = []
        for i in range(count):
            animal_no = request.form.get(f"animal_no_{i}")
            if not animal_no or not animal_no.strip():
                continue
            rows.append({
                "animal_no": animal_no,
                "gender": request.form.get(f"gender_{i}"),
                "weight": float(request.form[f"weight_{i}"]) if request.form.get(f"weight_{i}") else None,
                "price": float(request.form[f"price_{i}"]) if request.form.get(f"price_{i}") else None,
            })
        if not rows:
            flash("لازم رأس واحد على الأقل برقم صحيح", "error")
            return redirect(url_for("core.animals_bulk_purchase"))
        results = bulk_service.apply_bulk_purchase(
            rows=rows, barn_id=request.form.get("barn_id") or None,
            purchase_date=date.fromisoformat(request.form["purchase_date"]) if request.form.get("purchase_date") else date.today(),
            species=request.form.get("species") or "sheep_goat", actor_user_id=current_user.id,
        )
        done = sum(1 for r in results.values() if r.startswith("تمت"))
        flash(f"شراء دفعة جديدة: {done} من {len(rows)} أُضيفوا بنجاح", "success")
        for animal_no, r in results.items():
            if r.startswith("مرفوض"):
                flash(f"{animal_no}: {r}", "error")
        return redirect(url_for("core.animals_bulk_home"))

    return render_template(
        "animals_bulk_purchase.html",
        barns=Barn.query.order_by(Barn.barn_name).all(),
        today=date.today().isoformat(),
    )


SOURCE_FORM_MAP = {
    "birth": AnimalSource.BIRTH,
    "purchase": AnimalSource.PURCHASE,
    "gift": AnimalSource.GIFT,
    "opening_balance": AnimalSource.OPENING_BALANCE,
}


# حظائر النظام الإلزامية (بند إضافي، 2026-07-28) — تُزرع تلقائياً أول
# مرة تحتاجها الشاشة (نفس نمط `FarmSettings.get()` الموجود أصلاً)، عشان
# أي مزرعة جديدة تلقى هذي الحظائر جاهزة للاختيار بدون ما يضطر المالك
# ينشئها يدوياً. `barn_type="عزل"` نفس القيمة اللي تبحث عنها أصلاً
# `isolation_service`/`batch_service` (بدون تعديل عليهم) — "عزل_مرض"
# قيمة جديدة مخصّصة لبروتوكول الإجهاض/الحالات المرضية تحديداً.
_SYSTEM_BARNS = [
    ("Q-NEW", "حظيرة العزل للمستجدين", "عزل"),
    ("PREG", "حظيرة الحوامل", "حوامل"),
    ("A", "A-عادية", "عادية"),
    ("Q-SICK", "حظيرة عزل مرض", "عزل_مرض"),
]


def _seed_system_barns() -> None:
    existing_types = {b.barn_type for b in Barn.query.filter(Barn.barn_type.isnot(None)).all()}
    created = False
    for barn_no, barn_name, barn_type in _SYSTEM_BARNS:
        if barn_type in existing_types:
            continue
        if Barn.query.filter_by(barn_no=barn_no).first():
            continue
        db.session.add(Barn(barn_no=barn_no, barn_name=barn_name, barn_type=barn_type))
        created = True
    if created:
        db.session.commit()


@core_bp.route("/animals/species-types/new", methods=["GET", "POST"])
@login_required
@require_permission("animals.manage")
def species_types_new():
    """إضافة فصيلة جديدة (بند إضافي، 2026-07-28) — **تحذير مقصود بالواجهة**:
    فصيلة جديدة ما تدخل محرك دورة الإنتاج تلقائياً (مبني على بيولوجيا
    الحلال فقط) — نفس معاملة النعام حالياً، بأمان، لين يُبنى لها نظام
    مخصّص لاحقاً لو احتجتِه."""
    if request.method == "POST":
        value = request.form["name"].strip()
        if not value:
            flash("اسم الفصيلة مطلوب", "error")
            return redirect(url_for("core.species_types_new"))
        if SpeciesType.query.filter_by(code=value).first():
            flash(f'"{value}" موجودة بالقائمة أصلاً', "error")
            return redirect(url_for("core.species_types_new"))
        db.session.add(SpeciesType(code=value, label_ar=value))
        db.session.commit()
        flash("تمت إضافة الفصيلة", "success")
        return redirect(url_for("core.animals_new"))
    return render_template("animal_option_form.html", title=_("إضافة فصيلة جديدة"),
                            back_endpoint="core.animals_new",
                            warning=_("فصيلة جديدة ما تدخل محرك دورة الإنتاج (تقريع/حمل/فطام) تلقائياً — تُعامَل بأمان مثل النعام لين يُبنى لها نظام مخصّص."))


@core_bp.route("/animals/breeds/new", methods=["GET", "POST"])
@login_required
@require_permission("animals.manage")
def breeds_new():
    if request.method == "POST":
        value = request.form["name"].strip()
        if not value:
            flash("اسم السلالة مطلوب", "error")
            return redirect(url_for("core.breeds_new"))
        if Breed.query.filter_by(name=value).first():
            flash(f'"{value}" موجودة بالقائمة أصلاً', "error")
            return redirect(url_for("core.breeds_new"))
        db.session.add(Breed(name=value))
        db.session.commit()
        flash("تمت إضافة السلالة", "success")
        return redirect(url_for("core.animals_new"))
    return render_template("animal_option_form.html", title=_("إضافة سلالة جديدة"),
                            back_endpoint="core.animals_new")


@core_bp.route("/breeds")
@login_required
@require_permission("animals.view")
def breeds_list():
    """دليل السلالات وملاحظات رعايتها المحلية (بند إضافي 174) — النظام
    ما يعرض أي معلومة سلالة/مناخ جاهزة هنا، هذي ملاحظات المستخدم نفسه
    (أو طبيبه) المبنية على خبرته الفعلية بمنطقته."""
    breeds = Breed.query.order_by(Breed.name).all()
    return render_template("breeds_list.html", breeds=breeds)


@core_bp.route("/breeds/<int:breed_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("animals.manage")
def breed_edit(breed_id):
    breed = Breed.query.get_or_404(breed_id)
    if request.method == "POST":
        breed.care_notes = request.form.get("care_notes", "").strip() or None
        db.session.commit()
        flash("تم حفظ ملاحظات السلالة", "success")
        return redirect(url_for("core.breeds_list"))
    return render_template("breed_edit_form.html", breed=breed)


@core_bp.route("/animals/colors/new", methods=["GET", "POST"])
@login_required
@require_permission("animals.manage")
def colors_new():
    if request.method == "POST":
        value = request.form["name"].strip()
        if not value:
            flash("اسم اللون مطلوب", "error")
            return redirect(url_for("core.colors_new"))
        if AnimalColor.query.filter_by(name=value).first():
            flash(f'"{value}" موجود بالقائمة أصلاً', "error")
            return redirect(url_for("core.colors_new"))
        db.session.add(AnimalColor(name=value))
        db.session.commit()
        flash("تمت إضافة اللون", "success")
        return redirect(url_for("core.animals_new"))
    return render_template("animal_option_form.html", title=_("إضافة لون جديد"),
                            back_endpoint="core.animals_new")


@core_bp.route("/animals/new", methods=["GET", "POST"])
@login_required
@require_permission("animals.manage")
def animals_new():
    if request.method == "POST":
        source = request.form["source"]
        # الحظيرة إلزامية (بند إضافي، 2026-07-28) — ما فيه خيار "بدون
        # حظيرة" بالواجهة، بس نتحقق هنا كمان لو الطلب وصل مباشر للسيرفر.
        if not request.form.get("barn_id"):
            flash("الحظيرة مطلوبة", "error")
            return redirect(url_for("core.animals_new"))
        if not request.form.get("color"):
            flash("اللون مطلوب", "error")
            return redirect(url_for("core.animals_new"))
        from app.finance.finance_service import save_invoice_file
        try:
            animal = create_animal(
                animal_no=request.form.get("animal_no", "").strip() or None,
                source=SOURCE_FORM_MAP.get(source, AnimalSource.PURCHASE),
                gender=request.form["gender"],
                species=request.form.get("species") or "sheep_goat",
                barn_id=request.form.get("barn_id") or None,
                mother_id=request.form.get("mother_id") or None,
                father_id=request.form.get("father_id") or None,
                birth_date=date.fromisoformat(request.form["birth_date"]) if request.form.get("birth_date") else None,
                purchase_date=date.fromisoformat(request.form["purchase_date"]) if request.form.get("purchase_date") else None,
                entry_date=date.fromisoformat(request.form["entry_date"]) if request.form.get("entry_date") else None,
                weight=float(request.form["weight"]) if request.form.get("weight") else None,
                price=float(request.form["price"]) if request.form.get("price") else None,
                purpose=request.form.get("purpose") or None,
                color=request.form.get("color") or None,
                name=request.form.get("name") or None,
                image_url=request.form.get("image_url") or None,
                breed=request.form.get("breed") or None,
                is_pregnant_at_intake=bool(request.form.get("is_pregnant_at_intake")),
                invoice_file_url=save_invoice_file(request.files.get("invoice_file")),
            )
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("core.animals_new"))
        except IntegrityError:
            db.session.rollback()
            flash(f"رقم الحيوان \"{request.form.get('animal_no', '')}\" مستخدم من قبل", "error")
            return redirect(url_for("core.animals_new"))

        db.session.add(AuditLog(
            actor_user_id=current_user.id,
            action="animal.create",
            entity_type="Animal",
            entity_id=animal.id,
            details=f"source={source}",
        ))
        db.session.commit()
        flash("تمت إضافة الحيوان", "success")
        isolation_warning = getattr(animal, "_isolation_barn_warning", None)
        if isolation_warning:
            flash(isolation_warning, "warning")

        # إشعار تيليجرام فوري بالولادة (بند إضافي 231) — قبل كذا كان
        # الاعتماد كلياً على المهام (تعرف بالولادة بس لو فتحت "مهامي")،
        # مو حدث بحجم البيع أهمية. نفس نمط إشعارات نقص المخزون
        # (`stock_alert_service.py`): كل من يملك health.manage.
        if source == "birth":
            from app.core import telegram_service
            from app.models import User
            mother = Animal.query.get(request.form.get("mother_id")) if request.form.get("mother_id") else None
            for u in User.query.filter(User.telegram_chat_id.isnot(None), User.is_active_account.is_(True)).all():
                if u.has_permission("health.manage"):
                    telegram_service.notify_user(
                        u,
                        f"🍼 ولادة جديدة — {animal.animal_no}"
                        + (f" (الأم {mother.animal_no})" if mother else ""),
                    )
        return redirect(url_for("core.animals_list"))

    _seed_system_barns()
    SpeciesType.seed_defaults()
    Breed.seed_defaults()
    AnimalColor.seed_defaults()
    return render_template(
        "animal_form.html",
        barns=Barn.query.order_by(Barn.barn_name).all(),
        mothers=Animal.query.filter_by(gender="أنثى").order_by(Animal.animal_no).all(),
        fathers=Animal.query.filter_by(gender="ذكر").order_by(Animal.animal_no).all(),
        breeds=Breed.query.order_by(Breed.name).all(),
        species_types=SpeciesType.query.order_by(SpeciesType.label_ar).all(),
        colors=AnimalColor.query.order_by(AnimalColor.name).all(),
    )


@core_bp.route("/animals/<int:animal_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("animals.manage")
def animals_edit(animal_id):
    """تعديل بيانات حيوان موجود (بند إضافي، 2026-07-23) — أول شاشة تعديل
    فعلية لحيوان بالنظام، أضيفت أساساً عشان تسمح باستبدال رقم مؤقت
    (TEMP-ID) برقم/رقعة دائمة بعد ما توصل. **المصدر والفصيلة لا يتغيّران**
    عمداً — كلاهما مربوط بحركة مالية وحدث دورة إنتاج سُجّلا وقت الإنشاء،
    وتغييرهما بعدين يكسر تلك السجلات أو يكرّرها. لو أُدخل المصدر غلط،
    الأصح أرشفة هذا الرأس وإضافة رأس جديد صحيح (نفس نصيحة `cycle_engine`
    لسيناريوهات مشابهة)."""
    animal = Animal.query.get_or_404(animal_id)
    if request.method == "POST":
        new_no = request.form.get("animal_no", "").strip()
        if not new_no:
            flash("رقم الحيوان مطلوب", "error")
            return redirect(url_for("core.animals_edit", animal_id=animal.id))
        if not request.form.get("barn_id"):
            flash("الحظيرة مطلوبة", "error")
            return redirect(url_for("core.animals_edit", animal_id=animal.id))
        if not request.form.get("color"):
            flash("اللون مطلوب", "error")
            return redirect(url_for("core.animals_edit", animal_id=animal.id))
        animal.animal_no = new_no
        animal.name = request.form.get("name") or None
        animal.gender = request.form["gender"]
        animal.color = request.form.get("color") or None
        animal.purpose = request.form.get("purpose") or None
        animal.breed = request.form.get("breed") or "عام/غير محدد"
        animal.barn_id = request.form.get("barn_id") or None
        animal.birth_date = date.fromisoformat(request.form["birth_date"]) if request.form.get("birth_date") else None
        animal.purchase_date = date.fromisoformat(request.form["purchase_date"]) if request.form.get("purchase_date") else None
        animal.entry_date = date.fromisoformat(request.form["entry_date"]) if request.form.get("entry_date") else None
        animal.weight = float(request.form["weight"]) if request.form.get("weight") else None
        animal.price = float(request.form["price"]) if request.form.get("price") else None
        animal.image_url = request.form.get("image_url") or None
        db.session.add(animal)
        try:
            db.session.add(AuditLog(
                actor_user_id=current_user.id, action="animal.edit",
                entity_type="Animal", entity_id=animal.id,
            ))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(f"رقم الحيوان \"{new_no}\" مستخدم من قبل", "error")
            return redirect(url_for("core.animals_edit", animal_id=animal.id))
        flash("تم تحديث بيانات الحيوان", "success")
        return redirect(url_for("core.animal_detail", animal_id=animal.id))

    _seed_system_barns()
    Breed.seed_defaults()
    AnimalColor.seed_defaults()
    return render_template(
        "animal_form.html", animal=animal,
        barns=Barn.query.order_by(Barn.barn_name).all(),
        breeds=Breed.query.order_by(Breed.name).all(),
        colors=AnimalColor.query.order_by(AnimalColor.name).all(),
    )


_SPECIES_LABELS_AR = {"sheep_goat": "حلال (ضأن/ماعز)", "ostrich": "نعام"}
_ANIMAL_STATUS_LABELS_AR = {"active": "نشط", "sold": "مباع", "dead": "نافق", "inactive": "غير نشط"}


def _animal_age_label(animal: Animal) -> str | None:
    if not animal.birth_date:
        return None
    days = (date.today() - animal.birth_date).days
    if days < 60:
        return f"{days} يوم"
    if days < 730:
        return f"{days // 30} شهر"
    return f"{days // 365} سنة"


@core_bp.route("/animals/<int:animal_id>/quick-info")
@login_required
def animal_quick_info(animal_id):
    """
    تعبئة تلقائية لبيانات الحيوان بنموذج البلاغ (بند 28) — فحص أخف من
    `require_permission("animals.view")` العادي عمداً: نفس قائمة أرقام
    الحيوانات (animal_no) أصلاً مكشوفة لأي مستخدم يملك `reports.submit`
    (تظهر بقائمة اختيار الحيوان بنموذج البلاغ العادي وبنموذج العامل
    المبسّط، بند 27) بغض النظر عن صلاحية `animals.view`، فنقبل أي من
    الصلاحيتين هنا. **إصلاح أمني (بند 29)**: كانت هذي النقطة بدون أي فحص
    صلاحية إطلاقاً (فقط `login_required`) — أي دور مخصّص (يُنشأ لاحقاً من
    شاشة الأدوار) بدون `animals.view` ولا `reports.submit` كان يقدر يجيب
    بيانات أي حيوان بالمزرعة برقم تخمين بسيط بالرابط. الأدوار الستة
    الافتراضية ما كانت متأثرة عملياً (كلها تملك واحدة من الصلاحيتين على
    الأقل)، لكنها ثغرة حقيقية لأي دور مخصّص جديد.
    """
    if not (current_user.has_permission("animals.view") or current_user.has_permission("reports.submit")):
        abort(403)
    animal = Animal.query.get_or_404(animal_id)
    return jsonify({
        "animal_no": animal.animal_no,
        "species_label": _SPECIES_LABELS_AR.get(animal.species, animal.species),
        "gender": animal.gender or "-",
        "age_label": _animal_age_label(animal) or "-",
        "barn_name": animal.barn.barn_name if animal.barn else "بدون حظيرة",
        "status_label": _ANIMAL_STATUS_LABELS_AR.get(animal.status, animal.status),
        "image_url": animal.image_url,
    })


@core_bp.route("/animals/<int:animal_id>")
@login_required
@require_permission("animals.view")
def animal_detail(animal_id):
    from app.health.health_service import animal_under_withdrawal

    animal = Animal.query.get_or_404(animal_id)
    profile = animal_profile_service.get_profile(animal)
    # النعام ما يدخل محرك دورة الإنتاج (بند 23) — مبني على بيولوجيا
    # المجترات فقط (تقريع/حمل/فطام)، فما ننشئ له صف ProductionWorkflow.
    wf = cycle_engine.get_or_create_workflow(animal) if animal.species == "sheep_goat" else None
    withdrawal_until = animal_under_withdrawal(animal.id)
    breed_row = Breed.query.filter_by(name=animal.breed).first() if animal.breed else None
    animal_alerts = alerts_service.alerts_for_animal(animal.id) if current_user.has_permission("animals.view") else []
    return render_template(
        "animal_detail.html", wf=wf,
        withdrawal_until=withdrawal_until,
        withdrawal_days_left=(withdrawal_until - date.today()).days if withdrawal_until else None,
        today=date.today().isoformat(),
        breed_care_notes=breed_row.care_notes if breed_row else None,
        animal_alerts=animal_alerts,
        **profile,
    )


@core_bp.route("/weights/new-simple")
@login_required
@require_permission("animals.manage")
def animal_weight_new_simple():
    """تسجيل وزن — واجهة "بسيط جداً" (بند إضافي 226): اختر الحيوان
    ببطاقة كبيرة، اكتب الوزن، احفظ. يبني رابط POST لنفس
    `core.animal_weight_new` الحالية عبر استبدال JS بسيط (بدون أي
    منطق حفظ جديد)."""
    return render_template(
        "animal_weight_new_simple.html",
        animals=Animal.query.filter_by(status="active").order_by(Animal.animal_no).all(),
        post_url_template=url_for("core.animal_weight_new", animal_id=0),
        today=date.today().isoformat(),
    )


@core_bp.route("/animals/<int:animal_id>/weights/new", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animal_weight_new(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    try:
        add_weight_record(
            animal=animal,
            record_date=date.fromisoformat(request.form["date"]),
            weight=float(request.form["weight"]),
            notes=request.form.get("notes") or None,
            recorded_by_id=current_user.id,
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("core.animal_detail", animal_id=animal.id, tab="weights"))
    cycle_engine.evaluate(animal)
    db.session.commit()
    flash("تم تسجيل الوزن", "success")
    return redirect(url_for("core.animal_detail", animal_id=animal.id, tab="weights"))


@core_bp.route("/animals/<int:animal_id>/birth-record", methods=["POST"])
@login_required
@require_permission("health.manage")
def animal_birth_record_save(animal_id):
    from app.models import BirthRecord

    animal = Animal.query.get_or_404(animal_id)
    record = BirthRecord.query.filter_by(animal_id=animal.id).first()
    if record is None:
        record = BirthRecord(animal_id=animal.id)

    def _bool(field):
        value = request.form.get(field)
        return {"yes": True, "no": False}.get(value)

    record.breathing_ok = _bool("breathing_ok")
    record.standing_ok = _bool("standing_ok")
    record.colostrum_received = _bool("colostrum_received")
    record.cord_treated = _bool("cord_treated")
    record.birth_defects = request.form.get("birth_defects") or None
    record.recorded_by_id = current_user.id
    db.session.add(record)
    db.session.commit()
    flash("تم حفظ قائمة تحقق الولادة", "success")
    return redirect(url_for("core.animal_detail", animal_id=animal.id, tab="summary"))


@core_bp.route("/animals/<int:animal_id>/isolation/enter", methods=["GET", "POST"])
@login_required
@require_permission("animals.manage")
def animal_isolation_enter(animal_id):
    """دخول عزل يدوي واضح (بند إضافي 148) — لأي حالة استثنائية بمعزل عن
    خطة العزل التلقائية بعد الولادة."""
    animal = Animal.query.get_or_404(animal_id)
    isolation_barns = Barn.query.filter_by(barn_type="عزل").order_by(Barn.barn_name).all()
    if request.method == "POST":
        isolation_service.enter_isolation(
            animal_id=animal.id,
            reason=request.form.get("reason") or None,
            note_date=date.fromisoformat(request.form["date"]),
            actor_user_id=current_user.id,
            barn_id=int(request.form["barn_id"]) if request.form.get("barn_id") else None,
        )
        flash(f"تم نقل {animal.animal_no} للعزل", "success")
        return redirect(url_for("core.animal_detail", animal_id=animal.id))
    return render_template(
        "isolation_enter_form.html", animal=animal, isolation_barns=isolation_barns,
        today=date.today().isoformat(),
    )


@core_bp.route("/animals/<int:animal_id>/isolation/exit", methods=["GET", "POST"])
@login_required
@require_permission("animals.manage")
def animal_isolation_exit(animal_id):
    """خروج من العزل (بند إضافي 148) — خروج مبكر يحتاج تأكيد فحص بيطري
    وتحصين، وإلا تُرفض العملية (`isolation_service.IsolationExitBlocked`)."""
    from app.models import FarmSettings

    animal = Animal.query.get_or_404(animal_id)
    target_barns = Barn.query.filter(Barn.barn_type != "عزل").order_by(Barn.barn_name).all()
    settings = FarmSettings.get()
    days_in = (date.today() - animal.isolation_started_at).days if animal.isolation_started_at else None
    is_early = days_in is not None and days_in < settings.isolation_days

    if request.method == "POST":
        try:
            isolation_service.exit_isolation(
                animal_id=animal.id,
                target_barn_id=int(request.form["barn_id"]),
                note_date=date.fromisoformat(request.form["date"]),
                actor_user_id=current_user.id,
                vet_checked=request.form.get("vet_checked") == "1",
                vaccinated=request.form.get("vaccinated") == "1",
                notes=request.form.get("notes") or None,
            )
        except isolation_service.IsolationExitBlocked as e:
            flash(str(e), "error")
            return redirect(url_for("core.animal_isolation_exit", animal_id=animal.id))
        flash(f"تم إخراج {animal.animal_no} من العزل", "success")
        return redirect(url_for("core.animal_detail", animal_id=animal.id))
    return render_template(
        "isolation_exit_form.html", animal=animal, target_barns=target_barns,
        today=date.today().isoformat(), days_in=days_in, is_early=is_early,
        isolation_days=settings.isolation_days,
    )


@core_bp.route("/animals/<int:animal_id>/milk/new", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animal_milk_new(animal_id):
    from app.health.health_service import animal_under_withdrawal

    animal = Animal.query.get_or_404(animal_id)
    add_milk_record(
        animal=animal,
        record_date=date.fromisoformat(request.form["date"]),
        session=request.form["session"],
        quantity_liters=float(request.form["quantity_liters"]),
        notes=request.form.get("notes") or None,
        recorded_by_id=current_user.id,
    )
    flash("تم تسجيل الحليب", "success")
    # تنبيه فترة التحريم (بند إضافي، 2026-07-23) — تسجيل تحذيري بس (مو
    # منع)، عشان يبقى القرار للمالك/الدكتور لو الحليب يُستخدم للاستهلاك
    # المنزلي بدل البيع مثلاً. الحقل موجود أصلاً (`animal_under_withdrawal`)
    # وكان يُعرض بس بصفحة تفاصيل الرأس، بدون أي تنبيه فعلي وقت التسجيل.
    until = animal_under_withdrawal(animal.id)
    if until:
        flash(f'تنبيه: {animal.animal_no} تحت فترة تحريم دواء حتى {until} — الحليب المسجَّل الآن قد يكون غير آمن للبيع/الاستهلاك.', "warning")
    return redirect(url_for("core.animal_detail", animal_id=animal.id, tab="milk"))


@core_bp.route("/animals/<int:animal_id>/notes/new", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animal_note_new(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    add_note(
        animal=animal,
        note_date=date.fromisoformat(request.form["date"]) if request.form.get("date") else date.today(),
        note=request.form["note"].strip(),
        created_by_id=current_user.id,
    )
    flash("تمت إضافة الملاحظة", "success")
    return redirect(url_for("core.animal_detail", animal_id=animal.id, tab="notes"))


# خريطة "متطلب ناقص ← زر ينقل للمكان المقصود" (بند إضافي 73، 2026-07-29)
# — مطابقة بادئة نص عليها (مو مساواة تامة، عشان فيه متطلبات نصها متغيّر
# برقم مثل "فترة حجر 21 يوم..."). كل بند بالقائمة (نص جزئي، تسمية الزر،
# دالة تبني الرابط) — أول تطابق يفوز. اللي ماله تطابق يرجع بلا زر
# (بدل رابط مخترع لصفحة مو موجودة فعلياً).
_MISSING_ITEM_ACTIONS = [
    ("وزن مسجّل", "تسجيل وزن ←", lambda aid: url_for("core.animal_detail", animal_id=aid, tab="weights")),
    ("وزن عند الولادة", "تسجيل وزن ←", lambda aid: url_for("core.animal_detail", animal_id=aid, tab="weights")),
    ("فحص صحي أو زيارة بيطرية أو تطعيم", "زيارة بيطرية ←", lambda aid: url_for("health.vet_visits_new", animal_id=aid)),
    ("فحص دكتور خلال فترة العزل", "زيارة بيطرية ←", lambda aid: url_for("health.vet_visits_new", animal_id=aid)),
    ("فحص خصوبة/زيارة بيطرية", "زيارة بيطرية ←", lambda aid: url_for("health.vet_visits_new", animal_id=aid)),
    ("تحصين المولود", "تسجيل تحصين ←", lambda aid: url_for("health.vaccinations_new", animal_id=aid)),
    ("تحصين الأم بعد الولادة", "تسجيل تحصين ←", lambda aid: url_for("health.vaccinations_new", animal_id=aid)),
    ("لا يوجد أمراض مفتوحة", "مراجعة الأمراض ←", lambda aid: url_for("core.animal_detail", animal_id=aid, tab="diseases")),
    ("فترة حجر", "تفاصيل الرأس ←", lambda aid: url_for("core.animal_detail", animal_id=aid)),
    ("رقم الحيوان", "تعديل بيانات الرأس ←", lambda aid: url_for("core.animals_edit", animal_id=aid)),
    ("تاريخ الميلاد أو الشراء", "تعديل بيانات الرأس ←", lambda aid: url_for("core.animals_edit", animal_id=aid)),
    ("تاريخ الدخول", "تعديل بيانات الرأس ←", lambda aid: url_for("core.animals_edit", animal_id=aid)),
]


def _missing_item_action(item_text: str, animal_id: int):
    for prefix, label, build_url in _MISSING_ITEM_ACTIONS:
        if item_text.startswith(prefix) or prefix in item_text:
            return label, build_url(animal_id)
    return None


@core_bp.route("/animals/<int:animal_id>/workflow")
@login_required
@require_permission("animals.view")
def animal_workflow(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if animal.species == "ostrich":
        flash("النعام ما يدخل دورة الإنتاج — راجع سجل النعام (بيض/تفقيس).", "error")
        return redirect(url_for("ostrich.eggs_list"))
    if animal.species != "sheep_goat":
        flash("هذه الفصيلة ما تدخل محرك دورة الإنتاج (مبني على بيولوجيا الحلال فقط) — لا يوجد نظام دورة مخصّص لها بعد.", "error")
        return redirect(url_for("core.animal_detail", animal_id=animal.id))
    wf = cycle_engine.get_or_create_workflow(animal)
    cycle_engine.evaluate(animal)
    db.session.commit()
    events = CycleEvent.query.filter_by(animal_id=animal.id).order_by(CycleEvent.created_at.desc()).all()
    missing_items = (wf.missing_items or "").split("|") if wf.missing_items else []
    missing_items_with_actions = [
        (item, _missing_item_action(item, animal.id)) for item in missing_items
    ]
    sale_finance = None
    if animal.status == "sold":
        sale_finance = (Finance.query
                         .filter_by(related_animal_id=animal.id, operation_type="sale", is_cancelled=False)
                         .order_by(Finance.id.desc()).first())
    from app.health.health_service import animal_under_withdrawal
    return render_template(
        "animal_workflow.html",
        animal=animal, wf=wf, events=events,
        stages=cycle_engine.STAGES,
        active_stages=cycle_engine.ROUTE_STAGES[wf.route],
        route_label=cycle_engine.ROUTE_LABELS[wf.route],
        missing_items=missing_items,
        missing_items_with_actions=missing_items_with_actions,
        sale_finance=sale_finance,
        withdrawal_until=animal_under_withdrawal(animal.id),
    )


@core_bp.route("/animals/<int:animal_id>/sale-invoice")
@login_required
@require_permission("animals.view")
def animal_sale_invoice(animal_id):
    """يبني/يرجّع فاتورة بيع الحيوان — رقم الفاتورة يثبت أول مرة بس، أي
    تنزيل بعده لنفس السجل يرجّع نفس PDF بدون رقم جديد (بند إضافي 75)."""
    from flask import send_file
    from app.finance.finance_service import issue_sale_invoice
    from app.reports.export_service import build_invoice_pdf

    animal = Animal.query.get_or_404(animal_id)
    fin = (Finance.query
           .filter_by(related_animal_id=animal.id, operation_type="sale", is_cancelled=False)
           .order_by(Finance.id.desc()).first())
    if not fin:
        flash("ما فيه عملية بيع مسجّلة لهذا الحيوان.", "error")
        return redirect(url_for("core.animal_workflow", animal_id=animal.id))
    if fin.no_invoice:
        flash("هذا البيع مسجَّل بدون فاتورة.", "error")
        return redirect(url_for("core.animal_workflow", animal_id=animal.id))
    fin = issue_sale_invoice(fin)
    buf = build_invoice_pdf(fin, animal, FarmSettings.get())
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"{fin.invoice_number}.pdf")


@core_bp.route("/animals/<int:animal_id>/workflow/plan", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animal_workflow_plan(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    wf = cycle_engine.get_or_create_workflow(animal)
    wf.target_sale_date = date.fromisoformat(request.form["target_sale_date"]) if request.form.get("target_sale_date") else None
    wf.estimated_value = float(request.form["estimated_value"]) if request.form.get("estimated_value") else None
    wf.target_profit_margin = float(request.form["target_profit_margin"]) if request.form.get("target_profit_margin") else None
    wf.weaning_date = date.fromisoformat(request.form["weaning_date"]) if request.form.get("weaning_date") else None
    db.session.add(wf)
    db.session.commit()
    cycle_engine.evaluate(animal)
    db.session.commit()
    flash("تم تحديث بيانات التخطيط", "success")
    return redirect(url_for("core.animal_workflow", animal_id=animal.id))


@core_bp.route("/animals/<int:animal_id>/sell", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animal_sell(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    override_reason = request.form.get("withdrawal_override_reason") or None
    if override_reason and not current_user.has_permission("sales.override_withdrawal"):
        override_reason = None  # دفاع بعمق — تجاهل صامت لو المستخدم ما يملك الصلاحية فعلاً
    try:
        cycle_engine.sell_animal(
            animal,
            sale_price=float(request.form["sale_price"]),
            actor_user_id=current_user.id,
            sale_date=date.fromisoformat(request.form["sale_date"]) if request.form.get("sale_date") else None,
            notes=request.form.get("notes"),
            buyer_name=request.form.get("buyer_name") or None,
            buyer_phone=request.form.get("buyer_phone") or None,
            no_invoice=bool(request.form.get("no_invoice")),
            withdrawal_override_reason=override_reason,
        )
        flash("تم تسجيل البيع", "success")

        # إشعار تيليجرام فوري بالبيع (بند إضافي 231) — حدث مالي مهم،
        # نفس نمط إشعار الولادة فوق. أصحاب صلاحية finance.full.manage
        # (صاحب الحلال + المحاسب افتراضياً).
        from app.core import telegram_service
        from app.models import User
        for u in User.query.filter(User.telegram_chat_id.isnot(None), User.is_active_account.is_(True)).all():
            if u.has_permission("finance.full.manage"):
                telegram_service.notify_user(
                    u, f"💰 بيع رأس — {animal.animal_no} بسعر {request.form['sale_price']}",
                )
    except cycle_engine.CycleExitBlocked as e:
        # يشمل الآن حظر فترة التحريم أيضاً (بند إضافي 50) — كان تحذيراً
        # بعد البيع، صار رفضاً حقيقياً قبله.
        flash(str(e), "error")
    return redirect(url_for("core.animal_workflow", animal_id=animal.id))


@core_bp.route("/animals/<int:animal_id>/send-to-market", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animal_send_to_market(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    try:
        cycle_engine.send_to_market(animal, actor_user_id=current_user.id, note=request.form.get("note"))
        flash("تم تسجيل خروج الرأس للسوق", "success")
    except cycle_engine.CycleExitBlocked as e:
        flash(str(e), "error")
    return redirect(url_for("core.animal_workflow", animal_id=animal.id))


@core_bp.route("/animals/<int:animal_id>/return-from-market", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animal_return_from_market(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    cycle_engine.return_from_market(animal, actor_user_id=current_user.id, note=request.form.get("note"))
    flash("تم تسجيل رجوع الرأس للمزرعة بدون بيع", "success")
    return redirect(url_for("core.animal_workflow", animal_id=animal.id))


@core_bp.route("/animals/<int:animal_id>/mark-dead", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animal_mark_dead(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    cycle_engine.mark_animal_dead(
        animal,
        actor_user_id=current_user.id,
        reason=request.form.get("reason"),
        death_date=date.fromisoformat(request.form["death_date"]) if request.form.get("death_date") else None,
    )
    flash("تم تسجيل النفوق (بدون شرط اكتمال الدورة)", "success")
    return redirect(url_for("core.animal_workflow", animal_id=animal.id))


@core_bp.route("/animals/<int:animal_id>/archive", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animal_archive(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    try:
        cycle_engine.delete_animal(
            animal,
            actor_user_id=current_user.id,
            force=bool(request.form.get("force")),
            reason=request.form.get("reason"),
        )
        flash("تم أرشفة الحيوان", "success")
    except cycle_engine.CycleExitBlocked as e:
        flash(str(e), "error")
    return redirect(url_for("core.animal_workflow", animal_id=animal.id))


@core_bp.route("/barns")
@login_required
@require_permission("animals.view")
def barns_list():
    barns = Barn.query.order_by(Barn.barn_name).all()
    return render_template("barns_list.html", barns=barns)


def _save_feeding_schedule(barn_id: int) -> None:
    """مواعيد وجبات العلف لحظيرة (بند إضافي 131) — استبدال كامل بسيط،
    نفس فلسفة `_save_dose_rules` بملف `health/routes.py` بالضبط: يمسح كل
    مواعيد هذي الحظيرة ويعيد إنشاءها من القائمة المُرسَلة، ويتجاهل أي
    صف فاضي بصمت."""
    BarnFeedingSchedule.query.filter_by(barn_id=barn_id).delete()
    times = [t for t in request.form.getlist("meal_time") if t]
    for order, t in enumerate(sorted(times)):
        hh, mm = t.split(":")
        db.session.add(BarnFeedingSchedule(
            barn_id=barn_id, meal_time=time(int(hh), int(mm)), sort_order=order,
        ))


@core_bp.route("/barns/new", methods=["GET", "POST"])
@login_required
@require_permission("barns.manage")
def barns_new():
    from app.models import User
    if request.method == "POST":
        barn = Barn(
            barn_no=request.form["barn_no"].strip(),
            barn_name=request.form["barn_name"].strip(),
            barn_type=request.form.get("barn_type") or None,
            capacity=int(request.form["capacity"]) if request.form.get("capacity") else None,
            responsible_worker_id=request.form.get("responsible_worker_id") or None,
            notes=request.form.get("notes"),
        )
        db.session.add(barn)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            flash(f'رقم الحظيرة "{request.form["barn_no"]}" مستخدم من قبل', "error")
            return redirect(url_for("core.barns_new"))
        _save_feeding_schedule(barn.id)
        db.session.add(AuditLog(actor_user_id=current_user.id, action="barn.create",
                                 entity_type="Barn", entity_id=barn.id))
        db.session.commit()
        flash("تمت إضافة الحظيرة", "success")
        return redirect(url_for("core.barns_list"))
    return render_template("barn_form.html", workers=User.query.filter_by(is_active_account=True).order_by(User.name).all())


@core_bp.route("/barns/<int:barn_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("barns.manage")
def barns_edit(barn_id):
    """
    تعديل حظيرة موجودة — أهم استخدام لها عملياً: تغيير "العامل المسؤول"
    بعدين (بند 2 إضافي، 2026-07-23) — كان يُحدَّد مرة وحدة بس عند
    الإنشاء بدون أي طريقة لتغييره لاحقاً، رغم إنه أساس توجيه المهام
    التلقائي (`task_service.py`) والتنبيهات (`/alerts/mine`) للعامل.
    """
    from app.models import User
    barn = Barn.query.get_or_404(barn_id)
    if request.method == "POST":
        barn.barn_no = request.form["barn_no"].strip()
        barn.barn_name = request.form["barn_name"].strip()
        barn.barn_type = request.form.get("barn_type") or None
        barn.capacity = int(request.form["capacity"]) if request.form.get("capacity") else None
        barn.responsible_worker_id = request.form.get("responsible_worker_id") or None
        barn.notes = request.form.get("notes")
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            flash(f'رقم الحظيرة "{request.form["barn_no"]}" مستخدم من قبل', "error")
            return redirect(url_for("core.barns_edit", barn_id=barn.id))
        _save_feeding_schedule(barn.id)
        db.session.add(AuditLog(actor_user_id=current_user.id, action="barn.update",
                                 entity_type="Barn", entity_id=barn.id))
        db.session.commit()
        flash("تم تحديث الحظيرة", "success")
        return redirect(url_for("core.barns_list"))
    return render_template(
        "barn_form.html", barn=barn,
        workers=User.query.filter_by(is_active_account=True).order_by(User.name).all(),
    )


@core_bp.route("/settings")
@login_required
@require_permission("settings.manage")
def settings_home():
    from app.models import FarmSettings
    services = ServiceToggle.query.order_by(ServiceToggle.name).all()
    roles = Role.query.order_by(Role.id).all()
    fs = FarmSettings.get()
    fs.ensure_catalog_token()
    indicators_table = None
    if current_user.has_permission("analytics.view"):
        from app.reports import report_service as report_svc
        start, end, _range_key = report_svc.parse_date_range({})
        indicators_table = report_svc.overview_report(start, end)["table"]
    return render_template(
        "settings.html", services=services, roles=roles, fs=fs,
        indicators_table=indicators_table,
    )


@core_bp.route("/settings/telegram-status")
@login_required
@require_permission("settings.manage")
def telegram_status():
    """تشخيص حالة بوت تيليجرام من المتصفح مباشرة (بند إضافي 232،
    تعديل) — أمر `flask telegram-status` يحتاج Shell بلوحة Render،
    وهذي ميزة مدفوعة (مو متاحة بخطة Free). نفس المنطق بالضبط، بس
    كصفحة ويب عادية بدل CLI."""
    from app.core.telegram_service import diagnose
    return render_template("telegram_status.html", info=diagnose())


@core_bp.route("/settings/farm", methods=["POST"])
@login_required
@require_permission("settings.manage")
def farm_settings_save():
    from app.models import FarmSettings
    fs = FarmSettings.get()
    for field in (
        "gestation_days", "sponge_duration_days", "ram_entry_after_sponge_days",
        "pre_birth_feed_change_days", "postpartum_feed_days", "male_sale_after_birth_days",
        "alert_before_days", "vaccination_repeat_days", "isolation_days",
        "doctor_check_hours", "postpartum_vaccination_days",
        "min_breeding_age_days", "min_male_breeding_age_days", "min_rest_after_birth_days",
        "regular_sale_age_days", "udhiyah_min_age_days", "female_delayed_conception_days",
        "report_stale_hours", "ostrich_incubation_days", "workflow_stall_alert_days",
        # بند إضافي 105 — كانت مخزَّنة بدون أي شاشة تعديل.
        "quarantine_days", "reweigh_followup_days", "antiparasitic_redose_days", "weight_check_interval_days",
        "newborn_route_max_age_days", "male_fertility_exam_alt_age_days",
        "weaning_min_age_days", "weaning_alt_age_days",
        "concentrate_increase_window_days", "abortion_barn_monitor_days",
        # بند إضافي 218 — تقرير علف الحظيرة المفصَّل حسب الفئة.
        "weaning_solid_feed_age_days", "ram_breeding_season_window_days",
        "creep_feed_start_age_days", "creep_feed_target_grams_per_day",
        # بند إضافي 236 — كشف حمل ضمني.
        "estrus_return_window_days", "implicit_pregnancy_sonar_check_days",
        # بند إضافي 237 — تنبيه مخزون تنبؤي.
        "predictive_stock_alert_days",
        # بند إضافي 188 — بروتوكول حديث الولادة وأمه.
        "colostrum_window_hours", "placenta_check_hours", "postpartum_mother_followup_days",
    ):
        setattr(fs, field, int(request.form[field]))
    fs.target_profit_margin_percent = float(request.form["target_profit_margin_percent"])
    fs.concentrate_increase_max_percent_weekly = float(request.form["concentrate_increase_max_percent_weekly"])
    fs.ca_phosphorus_target_ratio = float(request.form["ca_phosphorus_target_ratio"])
    fs.ca_phosphorus_tolerance = float(request.form["ca_phosphorus_tolerance"])
    db.session.add(fs)
    db.session.commit()
    flash("تم حفظ الإعدادات الزمنية", "success")
    return redirect(url_for("core.settings_home"))


@core_bp.route("/settings/farm-identity", methods=["POST"])
@login_required
@require_permission("settings.manage")
def farm_identity_save():
    """بيانات هوية المزرعة لرأس فاتورة البيع (بند إضافي 75) — منفصلة عمداً
    عن farm_settings_save لأنها نصوص حرة، مو أرقام تُحوَّل بـint()/float()."""
    from app.models import FarmSettings
    fs = FarmSettings.get()
    fs.farm_name = request.form.get("farm_name") or None
    fs.farm_phone = request.form.get("farm_phone") or None
    fs.farm_address = request.form.get("farm_address") or None
    fs.vat_number = request.form.get("vat_number") or None
    db.session.add(fs)
    db.session.commit()
    flash("تم حفظ بيانات المزرعة", "success")
    return redirect(url_for("core.settings_home"))


@core_bp.route("/settings/roles/new", methods=["GET", "POST"])
@login_required
@require_permission("roles.manage")
def role_new():
    if request.method == "POST":
        display_name = request.form["display_name"].strip()
        slug = request.form.get("name", "").strip() or display_name
        role = Role(name=slug, display_name=display_name, is_system=False)
        db.session.add(role)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            flash(f'اسم الدور "{slug}" مستخدم من قبل', "error")
            return redirect(url_for("core.role_new"))
        db.session.add(AuditLog(actor_user_id=current_user.id, action="role.create",
                                 entity_type="Role", entity_id=role.id, details=display_name))
        db.session.commit()
        flash("تم إنشاء المسمّى الوظيفي — الحين حدّد صلاحياته", "success")
        return redirect(url_for("core.role_edit", role_id=role.id))
    return render_template("role_form.html")


@core_bp.route("/settings/roles/<int:role_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("roles.manage")
def role_edit(role_id):
    role = Role.query.get_or_404(role_id)
    if request.method == "POST":
        if role.is_system and role.name == "owner":
            flash("ما تقدر تعدّل صلاحيات دور صاحب الحلال — يملك كل الصلاحيات دائماً", "error")
            return redirect(url_for("core.role_edit", role_id=role.id))
        role.display_name = request.form.get("display_name", role.display_name).strip()
        selected_codes = set(request.form.getlist("permissions"))
        role.permissions = Permission.query.filter(Permission.code.in_(selected_codes)).all()
        db.session.add(AuditLog(actor_user_id=current_user.id, action="role.update_permissions",
                                 entity_type="Role", entity_id=role.id,
                                 details=f"{len(selected_codes)} permissions"))
        db.session.commit()
        flash("تم تحديث صلاحيات الدور", "success")
        return redirect(url_for("core.settings_home"))

    current_codes = {p.code for p in role.permissions}
    return render_template(
        "role_edit.html", role=role, all_permissions=PERMISSIONS, current_codes=current_codes,
    )


@core_bp.route("/settings/services/<int:service_id>/toggle", methods=["POST"])
@login_required
@require_permission("settings.manage")
def toggle_service(service_id):
    service = ServiceToggle.query.get_or_404(service_id)
    service.is_enabled = not service.is_enabled
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        action="service.toggle",
        entity_type="ServiceToggle",
        entity_id=service.id,
        details=f"{service.key} -> {'enabled' if service.is_enabled else 'disabled'}",
    ))
    db.session.commit()
    flash(f"تم {'تفعيل' if service.is_enabled else 'تعطيل'} خدمة {service.name}", "success")
    return redirect(url_for("core.settings_home"))


# ---------- النسخ الاحتياطي (بند 34) ----------

@core_bp.route("/settings/backup")
@login_required
@require_permission("settings.manage")
def backup_list():
    return render_template(
        "settings_backup.html",
        supported=backup_service.is_backup_supported(),
        backups=backup_service.list_backups(),
    )


@core_bp.route("/settings/backup/create", methods=["POST"])
@login_required
@require_permission("settings.manage")
def backup_create():
    try:
        filename = backup_service.create_backup()
        db.session.add(AuditLog(actor_user_id=current_user.id, action="backup.create",
                                 entity_type="Backup", details=filename))
        db.session.commit()
        flash(f"تم إنشاء نسخة احتياطية: {filename}", "success")
    except RuntimeError as e:
        flash(str(e), "error")
    return redirect(url_for("core.backup_list"))


@core_bp.route("/settings/backup/<filename>/download")
@login_required
@require_permission("settings.manage")
def backup_download(filename):
    path = backup_service.resolve_backup_path(filename)
    if not path:
        abort(404)
    return send_file(path, as_attachment=True)


# ---------- سجل التدقيق (بند 34) ----------

@core_bp.route("/settings/audit")
@login_required
@require_permission("audit.view")
def audit_log_list():
    # فلترة (بند إضافي 104) — قبل هذا آخر 200 حدث بس بدون أي فلترة،
    # يصير غير عملي بمزرعة نشطة بسرعة (200 حدث ممكن تصير ساعات قليلة).
    from app.models import AuditLog, User
    query = AuditLog.query

    start = request.args.get("start")
    end = request.args.get("end")
    actor_user_id = request.args.get("actor_user_id", type=int)
    action = request.args.get("action")

    if start:
        query = query.filter(db.func.date(AuditLog.created_at) >= start)
    if end:
        query = query.filter(db.func.date(AuditLog.created_at) <= end)
    if actor_user_id:
        query = query.filter(AuditLog.actor_user_id == actor_user_id)
    if action:
        query = query.filter(AuditLog.action == action)

    rows = query.order_by(AuditLog.created_at.desc()).limit(200).all()
    actions = [r[0] for r in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()]
    return render_template(
        "audit_log.html", rows=rows, actions=actions,
        users=User.query.order_by(User.name).all(),
        start=start or "", end=end or "", actor_user_id=actor_user_id, action=action or "",
    )


# ---------- استكمال البيانات والجاهزية (بند 33) ----------

@core_bp.route("/settings/readiness")
@login_required
@require_permission("settings.manage")
def readiness_check():
    return render_template("settings_readiness.html", checks=readiness_service.run_checks())


@core_bp.route("/settings/data-integrity")
@login_required
@require_permission("settings.manage")
def data_integrity_check():
    from app.core import data_integrity_service
    return render_template("settings_data_integrity.html", issues=data_integrity_service.run_full_audit())


@core_bp.route("/settings/simulation-data", methods=["GET", "POST"])
@login_required
@require_permission("settings.manage")
def simulation_data_purge():
    """تنظيف بيانات المحاكاة (بند إضافي 181) — مقصورة على المالك (نفس
    منطق تجاهل قائمة التجهيز) لأنه إجراء حذف حقيقي، وإن كان مستهدفاً
    لبيانات المحاكاة فقط. تأكيد مزدوج: كتابة عبارة صريحة + checkbox،
    نفس مستوى حذر عمليات الحذف الحرجة الثانية بالنظام."""
    if current_user.role.name != "owner":
        abort(403)
    from app.core import simulation_purge_service as svc
    result = None
    if request.method == "POST":
        if request.form.get("confirm_phrase") != "حذف بيانات المحاكاة" or request.form.get("confirm_check") != "1":
            flash("لازم تكتب العبارة بالضبط وتؤشّر على التأكيد.", "error")
        else:
            result = svc.purge_simulation_data()
            db.session.add(AuditLog(
                actor_user_id=current_user.id, action="simulation_data.purge",
                entity_type="Animal", details=str(result),
            ))
            db.session.commit()
            flash("تم حذف بيانات المحاكاة.", "success")
    preview = svc.preview_simulation_data()
    return render_template("settings_simulation_data.html", preview=preview, result=result)


@core_bp.route("/settings/simulation-data/run", methods=["POST"])
@login_required
@require_permission("settings.manage")
def simulation_data_run():
    """وضع عرض تجريبي (بند إضافي 211) — يشغّل نفس محاكاة `flask
    simulate-farm-month` من زر بالإعدادات بدل الـCLI، لتعبئة المزرعة
    ببيانات واقعية كاملة (رؤوس SIM-، مهام، أمراض، تقريع) بضغطة وحدة،
    عشان تُعرض للزوار بدون لمس بيانات المزرعة الحقيقية — نفس بادئة
    SIM- المستخدمة بأداة التنظيف (بند 181)، فزر "حذف بيانات المحاكاة"
    بنفس الصفحة يمسحها بعدين بأمان. مقصور على المالك، وتأكيده مربّع
    اختيار بس (بند إضافي 213 — كتابة عبارة نصية بالضبط كانت تفشل على
    الجوال بسبب تصحيح تلقائي/رموز خفية من لوحة المفاتيح، والإجراء
    نفسه إضافي مو حذف حقيقي، وقابل للتراجع بضغطة زر الحذف بنفس
    الصفحة، فمستوى الحذر هنا أخف من عملية الحذف الفعلية بالأسفل)."""
    if current_user.role.name != "owner":
        abort(403)
    if request.form.get("confirm_check") != "1":
        flash("لازم تؤشّر على مربّع التأكيد.", "error")
        return redirect(url_for("core.simulation_data_purge"))

    from app.core.simulation_service import run_farm_month_simulation
    try:
        days = int(request.form.get("days") or 30)
    except ValueError:
        days = 30
    days = max(1, min(days, 90))
    send_email = request.form.get("send_email") == "1"

    result = run_farm_month_simulation(days, send_email=send_email)
    if not result["ok"]:
        flash(result["message"], "error")
        return redirect(url_for("core.simulation_data_purge"))

    db.session.add(AuditLog(
        actor_user_id=current_user.id, action="simulation_data.run",
        entity_type="Animal", details=str(result["counters"]),
    ))
    db.session.commit()
    flash(f"تم تشغيل العرض التجريبي ({days} يوم) — {result['counters']['animals_purchased']} رأس، "
          f"{result['counters']['matings']} تقريع، {result['counters']['diseases_opened']} حالة مرضية. "
          f"تقدر تحذفها لاحقاً من نفس الصفحة.", "success")
    return redirect(url_for("core.simulation_data_purge"))


# ---------- شاشة متابعة مبسّطة (بند إضافي 106) ----------

FAMILY_VIEW_ROLES = [
    ("owner", "مهام صاحب الحلال"),
    ("doctor", "مهام الطبيب"),
    ("worker", "مهام العامل"),
]


@core_bp.route("/family-view")
@login_required
@require_permission("analytics.view")
def family_view():
    """شاشة عرض ومتابعة مبسّطة (بند 106، وسّعت بند إضافي 109) مصمَّمة
    لمستخدم مسنّ — خط كبير، تنقّل بأزرار كبيرة بدل قوائم متفرّعة.
    المهام مبوَّبة حسب الدور (صاحب الحلال/الطبيب/العامل) بدل حسب كل
    عامل لحاله — يشمل مهام بلا عامل محدد تطابق دور المستخدم (بند 107)."""
    from app.models import User, Task, Feed, Pharmacy, Equipment, Role
    from app.core import stock_stats_service
    from app.equipment import equipment_service
    from app.reports.report_service import _to_local_date, _utc_datetime_widened

    today = date.today()

    def _tasks_for_role(role_name):
        user_ids = [u.id for u in User.query.join(Role).filter(
            Role.name == role_name, User.is_active_account.is_(True)).all()]
        assignee_filter = Task.assignee_id.in_(user_ids) if user_ids else False
        done_today = []
        for t in Task.query.filter(
            assignee_filter, Task.status.in_(("done", "failed")),
            db.or_(
                db.and_(Task.completed_at.isnot(None), _utc_datetime_widened(Task.completed_at, today, today)),
                db.and_(Task.failed_at.isnot(None), _utc_datetime_widened(Task.failed_at, today, today)),
            ),
        ).order_by(Task.completed_at.desc()).all():
            when = _to_local_date(t.completed_at) if t.status == "done" and t.completed_at else (
                _to_local_date(t.failed_at) if t.status == "failed" and t.failed_at else None)
            if when == today:
                done_today.append(t)
        open_tasks = (Task.query.filter(
            Task.status.in_(("pending", "in_progress")),
            db.or_(assignee_filter, db.and_(Task.assignee_id.is_(None), Task.target_role == role_name)),
        ).order_by(Task.due_date).all())
        return done_today, open_tasks

    tasks_by_role = {}
    for role_name, role_label in FAMILY_VIEW_ROLES:
        done_today, open_tasks = _tasks_for_role(role_name)
        tasks_by_role[role_name] = {"label": role_label, "done_today": done_today, "open_tasks": open_tasks}

    def _with_alert(item, stats):
        return {"item": item, "stats": stats, "alert": stock_stats_service.stock_alert_level(item, stats)}

    feed_items = [
        _with_alert(f, stock_stats_service.feed_consumption_stats(f))
        for f in Feed.query.filter_by(status="active").order_by(Feed.name).all()
    ]
    pharmacy_items = [
        _with_alert(p, stock_stats_service.pharmacy_consumption_stats(p))
        for p in Pharmacy.query.filter_by(status="active").order_by(Pharmacy.name).all()
    ]
    equipment_items = [
        dict(_with_alert(e, equipment_service.consumption_stats(e)),
             borrows=equipment_service.outstanding_borrows(e))
        for e in Equipment.query.filter_by(status="active").order_by(Equipment.name).all()
    ]

    return render_template(
        "family_view.html", tasks_by_role=tasks_by_role, family_view_roles=FAMILY_VIEW_ROLES,
        feed_items=feed_items, pharmacy_items=pharmacy_items, equipment_items=equipment_items, today=today,
    )
