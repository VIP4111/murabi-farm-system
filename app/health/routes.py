from datetime import date, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.health import health_bp
from app.auth.decorators import require_permission
from app.extensions import db
from app.models import (
    Pharmacy, PharmacyBatch, PharmacyDoseRule, UsageRoute, DrugCatalogEntry, VaccinationSchedule, Doctor, VetVisit,
    Disease, Vaccination, Animal, AuditLog, Barn,
    DiseaseType, Symptom, FarmSettings, Task, TreatmentProtocol, TreatmentProtocolStep,
    ProtocolApplication, DiseaseSymptomLink, EmergencySymptom,
)
from app.health import health_service
from app.team import task_service as tsvc
from app.core import protocol_service

PROTOCOL_STEP_SLOTS = range(8)


# ---------- مركز الطبيب (بند إضافي 169) ----------

@health_bp.route("/dashboard")
@login_required
@require_permission("health.view")
def dashboard():
    """مركز إدارة الطبيب — بديل عن التنقّل اليدوي بين 8 روابط متفرّقة
    بالقائمة الجانبية (صيدلية/زيارات/أمراض/تحصينات/تقويم/تشخيص/دليل
    حقن/بروتوكولات). يجمع بصفحة وحدة: (1) سجل متابعة الحالات المرضية
    النشطة والمغلقة حديثاً، (2) التحصينات المستحقة خلال أسبوع، (3)
    موسوعة مرجعية سريعة (روابط لكل الأدلة العامة الموجودة أصلاً بالنظام
    — أمراض شائعة، حقن، بروتوكولات، تشخيص، أعراض طوارئ) — بدون تكرار
    أي منطق موجود، مجرد واجهة تجميع."""
    today = date.today()
    active_cases = (
        Disease.query.filter_by(status="active")
        .order_by(Disease.date.desc()).all()
    )
    recent_closed = (
        Disease.query.filter_by(status="closed")
        .order_by(Disease.closed_at.desc()).limit(8).all()
    )
    upcoming_vaccinations = (
        Vaccination.query.filter(
            Vaccination.next_due_date.isnot(None),
            Vaccination.next_due_date <= today + timedelta(days=7),
        )
        .join(Animal).filter(Animal.status == "active")
        .order_by(Vaccination.next_due_date).limit(15).all()
    )
    return render_template(
        "health/dashboard.html",
        active_cases=active_cases, recent_closed=recent_closed,
        upcoming_vaccinations=upcoming_vaccinations, today=today,
    )


def _complete_originating_task(task_id):
    """بند إضافي 50 — لو الشاشة اتفتحت عبر "تأكيد التنفيذ" لمهمة علاج
    مخطَّط، أنجز المهمة وجدول متابعة إعادة وزن تلقائية، فوراً بعد نجاح
    التسجيل الطبي الفعلي (الخصم الحقيقي صار هناك، مو بإنشاء المهمة)."""
    if not task_id:
        return
    task = Task.query.get(int(task_id))
    if not task:
        return
    tsvc.complete_task_via_treatment(task, actor=current_user)
    tsvc.schedule_reweigh_followup(task, actor=current_user)
    flash("تم إنجاز المهمة المرتبطة تلقائياً، وجُدولت مهمة متابعة إعادة وزن.", "success")


def _check_redose_guard(*, animal_id, pharmacy_id, override_reason, entity_type):
    """حارس منع تكرار جرعة الطفيليات خلال N يوماً (بند إضافي 50) — تحذير
    قابل للتجاوز بسبب صريح، يُستدعى من الشاشات الثلاث (زيارة/مرض/تطعيم)
    قبل التسجيل الفعلي. يرجّع (ok: bool, notes_suffix: str|None)."""
    pharmacy = Pharmacy.query.get(int(pharmacy_id)) if pharmacy_id else None
    redose_days = FarmSettings.get().antiparasitic_redose_days
    guard = health_service.redose_guard_warning(animal_id=animal_id, pharmacy=pharmacy, redose_days=redose_days)
    if not guard:
        return True, None
    if not override_reason:
        flash(guard["message"] + " اكتب سبب التجاوز بالحقل المخصص لو متأكد من الحاجة للتكرار.", "warning")
        return False, None
    db.session.add(AuditLog(actor_user_id=current_user.id, action="health.redose_override",
                             entity_type=entity_type, details=override_reason))
    return True, f"تجاوز حارس تكرار الطفيليات ({guard['days_since']} يوماً منذ آخر جرعة): {override_reason}"


@health_bp.context_processor
def _inject_injection_guide():
    """يجعل دليل الحقن الميداني متاحاً لأي قالب بوحدة الصحة (بند إضافي،
    2026-07-24) — نفس البيانات اللي تُعرض بشاشة `/health/injection-guide`
    الكاملة، مستخدَمة أيضاً بمعاينة سريعة عند اختيار دواء بودجت
    `_medicine_widget.html` (مصدر واحد، صفر تكرار محتوى)."""
    return {"injection_guide": health_service.INJECTION_GUIDE}


# ---------- الصيدلية ----------

@health_bp.route("/pharmacy")
@login_required
@require_permission("health.view")
def pharmacy_list():
    health_service.seed_default_vaccine_catalog()
    items = Pharmacy.query.order_by(Pharmacy.name).all()
    stockout = {p.id: health_service.pharmacy_days_until_stockout(p) for p in items}
    return render_template(
        "health/pharmacy_list.html", items=items, today=date.today(), stockout=stockout,
        medicine_class_labels=Pharmacy.MEDICINE_CLASS_LABELS_AR,
    )


@health_bp.route("/pharmacy/shortages")
@login_required
@require_permission("health.view")
def pharmacy_shortages():
    """قائمة نواقص الصيدلية (بند إضافي، 2026-07-24) — أي دواء نشط وصل
    مخزونه للحد الأدنى أو أقل (`min_stock_qty`). هذي الشاشة نفسها هي
    "قائمة المشتريات المطلوبة" — ما احتجنا سلة/جدول منفصل، المقارنة
    الحية بين المتوفر والحد الأدنى كافية."""
    items = (Pharmacy.query.filter_by(status="active")
             .filter(Pharmacy.available_qty <= db.func.coalesce(Pharmacy.min_stock_qty, 0))
             .order_by(Pharmacy.name).all())
    # بدائل بنفس فئة الدواء (بند إضافي، 2026-07-24 — أُعيد ربطها بـ
    # `medicine_class` بدل حقل "الفئة" النصي الحر بعد إلغائه من الفورم
    # ببند 61، 2026-07-28: `medicine_class` قائمة مغلقة أدق وما تعتمد على
    # دقة كتابة الطبيب) — أدوية نشطة، فوق حدها الأدنى فعلياً، بنفس فئة
    # الدواء الناقص — اقتراح سريع بدون أي افتراض علمي (نفس الاسم/الشركة/
    # التركيبة).
    alternatives = {}
    for item in items:
        if not item.medicine_class:
            continue
        alternatives[item.id] = (
            Pharmacy.query.filter_by(status="active", medicine_class=item.medicine_class)
            .filter(Pharmacy.id != item.id)
            .filter(Pharmacy.available_qty > db.func.coalesce(Pharmacy.min_stock_qty, 0))
            .all()
        )
    return render_template("health/pharmacy_shortages.html", items=items, alternatives=alternatives)


def _save_dose_rules(pharmacy_id: int) -> None:
    """جدول "الجرعة حسب العمر" (بند إضافي، 2026-07-28) — استبدال كامل
    بسيط بدل تحديث جزئي (نفس فلسفة المشروع بتفضيل البساطة الصحيحة على
    التعقيد الذكي): يمسح كل صفوف هذا الدواء ويعيد إنشاءها من القوائم
    المُرسَلة، ويتجاهل أي صف فاضي أو غير مكتمل بصمت."""
    PharmacyDoseRule.query.filter_by(pharmacy_id=pharmacy_id).delete()
    froms = request.form.getlist("dose_age_from")
    tos = request.form.getlist("dose_age_to")
    doses = request.form.getlist("dose_ml")
    for age_from, age_to, dose_ml in zip(froms, tos, doses):
        if not (age_from and age_to and dose_ml):
            continue
        db.session.add(PharmacyDoseRule(
            pharmacy_id=pharmacy_id,
            age_from_days=int(age_from), age_to_days=int(age_to), dose_ml=float(dose_ml),
        ))


@health_bp.route("/pharmacy/new", methods=["GET", "POST"])
@login_required
@require_permission("pharmacy.manage")
def pharmacy_new():
    if request.method == "POST":
        item = Pharmacy(
            name=request.form["name"],
            medicine_class=request.form.get("medicine_class") or None,
            contains_high_copper=bool(request.form.get("contains_high_copper")),
            available_qty=float(request.form.get("available_qty") or 0),
            min_stock_qty=float(request.form.get("min_stock_qty") or 0),
            unit=request.form.get("unit"),
            unit_price=float(request.form["unit_price"]) if request.form.get("unit_price") else None,
            expiry_date=date.fromisoformat(request.form["expiry_date"]) if request.form.get("expiry_date") else None,
            withdrawal_days=int(request.form.get("withdrawal_days") or 0),
            usage_method=request.form.get("usage_method") or None,
            standard_dosage_note=request.form.get("standard_dosage_note") or None,
            protection_days=int(request.form["protection_days"]) if request.form.get("protection_days") else None,
            default_dose_ml=float(request.form["default_dose_ml"]) if request.form.get("default_dose_ml") else None,
            storage_condition=request.form.get("storage_condition") or None,
            notes=request.form.get("notes"),
        )
        db.session.add(item)
        db.session.flush()
        _save_dose_rules(item.id)
        db.session.commit()
        flash("تمت إضافة الدواء", "success")
        return redirect(url_for("health.pharmacy_list"))
    UsageRoute.seed_defaults()
    return render_template(
        "health/pharmacy_form.html",
        medicine_classes=Pharmacy.MEDICINE_CLASSES,
        medicine_class_labels=Pharmacy.MEDICINE_CLASS_LABELS_AR,
        medicine_class_guide=health_service.MEDICINE_CLASS_GUIDE,
        medicine_class_guide_en=health_service.MEDICINE_CLASS_GUIDE_EN,
        storage_conditions=Pharmacy.STORAGE_CONDITIONS,
        storage_condition_labels=Pharmacy.STORAGE_CONDITION_LABELS_AR,
        usage_routes=UsageRoute.query.order_by(UsageRoute.name).all(),
        drug_catalog=DrugCatalogEntry.query.order_by(DrugCatalogEntry.name).all(),
    )


@health_bp.route("/pharmacy/<int:pharmacy_id>/dose-rules")
@login_required
@require_permission("health.view")
def pharmacy_dose_rules_json(pharmacy_id):
    """نقطة نهاية JSON صغيرة (نفس نمط `/animals/<id>/quick-info` ببند 28)
    — تُستخدم من شاشة التحصين الجماعي لجلب جدول الجرعة حسب العمر لدواء
    مختار، وتحسب الجرعة المطابقة لكل رأس بجافاسكربت بالمتصفح (بحث بسيط
    بجدول كتبه الدكتور، مو حساباً جديداً). `default_dose_ml` تُرجَع كقيمة
    احتياطية (بند إضافي 61) تُستخدم بالواجهة بس لو عمر الرأس ما طابق أي
    نطاق بالجدول — تبقى نفس رقم الدكتور، صفر حساب. `available_qty`
    تُرجَع (بند إضافي 64) لشريط فحص المخزون المباشر — عرض بس، السيرفر
    يبقى الحاسم الفعلي لخصم/رفض المخزون (`Pharmacy.deduct_stock`)."""
    rules = PharmacyDoseRule.query.filter_by(pharmacy_id=pharmacy_id).order_by(PharmacyDoseRule.age_from_days).all()
    pharmacy = Pharmacy.query.get_or_404(pharmacy_id)
    return jsonify({
        "protection_days": pharmacy.protection_days,
        "default_dose_ml": pharmacy.default_dose_ml,
        "available_qty": pharmacy.available_qty,
        "unit": pharmacy.unit,
        "rules": [{"age_from_days": r.age_from_days, "age_to_days": r.age_to_days, "dose_ml": r.dose_ml} for r in rules],
    })


@health_bp.route("/pharmacy/<int:pharmacy_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("pharmacy.manage")
def pharmacy_edit(pharmacy_id):
    item = Pharmacy.query.get_or_404(pharmacy_id)
    if request.method == "POST":
        item.name = request.form["name"]
        item.medicine_class = request.form.get("medicine_class") or None
        item.contains_high_copper = bool(request.form.get("contains_high_copper"))
        item.available_qty = float(request.form.get("available_qty") or 0)
        item.min_stock_qty = float(request.form.get("min_stock_qty") or 0)
        item.unit = request.form.get("unit")
        item.unit_price = float(request.form["unit_price"]) if request.form.get("unit_price") else None
        item.expiry_date = date.fromisoformat(request.form["expiry_date"]) if request.form.get("expiry_date") else None
        item.withdrawal_days = int(request.form.get("withdrawal_days") or 0)
        item.usage_method = request.form.get("usage_method") or None
        item.standard_dosage_note = request.form.get("standard_dosage_note") or None
        item.protection_days = int(request.form["protection_days"]) if request.form.get("protection_days") else None
        item.default_dose_ml = float(request.form["default_dose_ml"]) if request.form.get("default_dose_ml") else None
        item.storage_condition = request.form.get("storage_condition") or None
        item.notes = request.form.get("notes")
        _save_dose_rules(item.id)
        db.session.commit()
        flash("تم تحديث بيانات الدواء", "success")
        return redirect(url_for("health.pharmacy_list"))
    UsageRoute.seed_defaults()
    return render_template(
        "health/pharmacy_form.html", item=item,
        medicine_classes=Pharmacy.MEDICINE_CLASSES,
        medicine_class_labels=Pharmacy.MEDICINE_CLASS_LABELS_AR,
        medicine_class_guide=health_service.MEDICINE_CLASS_GUIDE,
        medicine_class_guide_en=health_service.MEDICINE_CLASS_GUIDE_EN,
        storage_conditions=Pharmacy.STORAGE_CONDITIONS,
        storage_condition_labels=Pharmacy.STORAGE_CONDITION_LABELS_AR,
        usage_routes=UsageRoute.query.order_by(UsageRoute.name).all(),
        drug_catalog=DrugCatalogEntry.query.order_by(DrugCatalogEntry.name).all(),
        dose_rules=item.dose_rules,
    )


@health_bp.route("/pharmacy/<int:pharmacy_id>/purchase", methods=["GET", "POST"])
@login_required
@require_permission("pharmacy.manage")
def pharmacy_purchase(pharmacy_id):
    """تسجيل عملية شراء دواء (بند إضافي 96، وُصِّلت بالمالية ببند 259)
    — يسجّل دفعة مستقلة (`PharmacyBatch`) بتاريخها وتاريخ انتهائها
    الخاص، ويزيد `available_qty` الإجمالي تلقائياً بنفس الكمية —
    فورم التعديل المباشر يبقى شغّال زي ما هو لتصحيحات المخزون العامة،
    مو بديلاً عن هذا الفورم. **بند 259**: لو سعر الوحدة انكتب، تُنشأ
    عملية مالية "شراء" حقيقية بنفس النمط الموحّد للعلف/المعدات (بند
    203) — قبل هذا البند المبلغ كان يختفي تماماً من كل تقارير المالية.
    يحتاج صلاحية `finance.full.manage` كمان لو فيه سعر (نفس قيد شراء
    العلف — أي مبلغ يخرج من حساب المزرعة يحتاج صلاحية مالية)."""
    item = Pharmacy.query.get_or_404(pharmacy_id)
    if request.method == "POST":
        quantity = float(request.form["quantity"])
        unit_price = float(request.form["unit_price"]) if request.form.get("unit_price") else None
        if unit_price is not None and not current_user.has_permission("finance.full.manage"):
            flash("تحتاج صلاحية إدارة المالية كمان عشان تسجّل شراء بسعر (يُنشئ عملية مالية).", "error")
            return redirect(url_for("health.pharmacy_purchase", pharmacy_id=item.id))

        from app.core.stock_purchase_service import record_purchase
        record_purchase(
            kind="pharmacy", item=item, quantity=quantity, unit_price=unit_price,
            purchase_date=date.fromisoformat(request.form["purchase_date"]),
            expiry_date=date.fromisoformat(request.form["expiry_date"]) if request.form.get("expiry_date") else None,
            note=request.form.get("notes"), created_by_id=current_user.id,
        )
        db.session.add(AuditLog(actor_user_id=current_user.id, action="pharmacy.purchase",
                                 entity_type="Pharmacy", entity_id=item.id,
                                 details=f"+{quantity:g} {item.unit or ''}"))
        db.session.commit()
        if unit_price is None:
            flash("تم تسجيل عملية الشراء بالمخزون بس — بدون سعر، ما انسجلت عملية مالية.", "warning")
        else:
            flash("تم تسجيل عملية الشراء — زاد المخزون وانسجلت العملية المالية معاً", "success")
        return redirect(url_for("health.pharmacy_edit", pharmacy_id=item.id))
    return render_template(
        "health/pharmacy_purchase_form.html", item=item, today=date.today().isoformat(),
        batches=PharmacyBatch.query.filter_by(pharmacy_id=item.id).order_by(PharmacyBatch.purchase_date.desc()).all(),
    )


@health_bp.route("/usage-routes/new", methods=["GET", "POST"])
@login_required
@require_permission("medical_options.manage")
def usage_routes_new():
    """إضافة "طريقة استخدام" جديدة للقائمة (بند إضافي 61) — نفس نمط
    disease_types_new/breeds_new/colors_new بالضبط."""
    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            flash("اسم الطريقة مطلوب", "error")
            return redirect(url_for("health.usage_routes_new"))
        if UsageRoute.query.filter_by(name=name).first():
            flash(f'"{name}" موجودة بالقائمة أصلاً', "error")
            return redirect(url_for("health.usage_routes_new"))
        db.session.add(UsageRoute(name=name))
        db.session.commit()
        flash("تمت إضافة طريقة الاستخدام", "success")
        return redirect(url_for("health.pharmacy_new"))
    return render_template("animal_option_form.html", title="إضافة طريقة استخدام جديدة",
                            back_endpoint="health.pharmacy_new")


@health_bp.route("/drug-catalog/new", methods=["GET", "POST"])
@login_required
@require_permission("medical_options.manage")
def drug_catalog_new():
    """إضافة اسم دواء جديد لكتالوج الاقتراحات (بند إضافي 62) — منفصل
    عن صفوف الصيدلية الفعلية (`Pharmacy`)، مجرد قائمة أسماء معروفة تُصفَّى
    حسب فئة الدواء بفورم "دواء جديد"."""
    if request.method == "POST":
        name = request.form["name"].strip()
        medicine_class = request.form.get("medicine_class") or None
        if not name:
            flash("اسم الدواء مطلوب", "error")
            return redirect(url_for("health.drug_catalog_new", medicine_class=medicine_class or ""))
        if DrugCatalogEntry.query.filter_by(name=name).first():
            flash(f'"{name}" موجود بالكتالوج أصلاً', "error")
            return redirect(url_for("health.drug_catalog_new", medicine_class=medicine_class or ""))
        db.session.add(DrugCatalogEntry(name=name, medicine_class=medicine_class))
        db.session.commit()
        flash("تمت إضافة الدواء للكتالوج", "success")
        return redirect(url_for("health.pharmacy_new"))
    return render_template(
        "health/drug_catalog_form.html",
        medicine_classes=Pharmacy.MEDICINE_CLASSES,
        medicine_class_labels=Pharmacy.MEDICINE_CLASS_LABELS_AR,
        preselected_class=request.args.get("medicine_class") or "",
    )


# ---------- الأمراض الشائعة (بند إضافي، 2026-07-23) ----------

@health_bp.route("/disease-types")
@login_required
@require_permission("health.view")
def disease_types_list():
    types = DiseaseType.query.order_by(DiseaseType.name).all()
    return render_template("health/disease_types_list.html", types=types)


@health_bp.route("/disease-types/new", methods=["GET", "POST"])
@login_required
@require_permission("medical_options.manage")
def disease_types_new():
    if request.method == "POST":
        name = request.form["name"].strip()
        if DiseaseType.query.filter_by(name=name).first():
            flash(f'"{name}" موجود بالقائمة أصلاً', "error")
            return redirect(url_for("health.disease_types_new"))
        db.session.add(DiseaseType(name=name, notes=request.form.get("notes") or None))
        db.session.commit()
        flash("تمت إضافة المرض للقائمة", "success")
        return redirect(url_for("health.disease_types_list"))
    return render_template("health/disease_type_form.html")


# ---------- شجرة التشخيص: إدارة الأعراض والروابط (بند إضافي 127، المرحلة 1) ----------
# قبل هذا البند، شجرة القرار التشخيصية (Symptom/DiseaseSymptomLink) كانت
# تُبنى مرة وحدة بس عند `flask seed` (بيانات ثابتة بـapp/cli.py) — أي
# تعديل (وزن، إضافة/حذف رابط مرض↔عرض) يحتاج تعديل كود ونشر جديد. صار
# قابلاً للتعديل بالكامل من الواجهة، بنفس صلاحية بقية "الخيارات الطبية"
# (medical_options.manage).

@health_bp.route("/symptoms")
@login_required
@require_permission("health.view")
def symptoms_list():
    symptoms = Symptom.query.order_by(Symptom.name).all()
    return render_template("health/symptoms_list.html", symptoms=symptoms)


@health_bp.route("/symptoms/new", methods=["GET", "POST"])
@login_required
@require_permission("medical_options.manage")
def symptoms_new():
    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            flash("اسم العرض مطلوب", "error")
            return redirect(url_for("health.symptoms_new"))
        if Symptom.query.filter_by(name=name).first():
            flash(f'"{name}" موجود بالقائمة أصلاً', "error")
            return redirect(url_for("health.symptoms_new"))
        db.session.add(Symptom(name=name, is_primary=bool(request.form.get("is_primary"))))
        db.session.commit()
        flash("تمت إضافة العرض", "success")
        return redirect(url_for("health.symptoms_list"))
    return render_template("health/symptom_form.html")


@health_bp.route("/disease-types/<int:disease_id>")
@login_required
@require_permission("health.view")
def disease_type_detail(disease_id):
    """شاشة إدارة أعراض مرض معيّن — الوزن (1-3) وحقلي "إجباري"/
    "استبعادي" الجديدين (بند إضافي 127) قابلين للتعديل هنا مباشرة، بلا
    حاجة لأي تعديل كود أو بذر جديد."""
    disease = DiseaseType.query.get_or_404(disease_id)
    linked_symptom_ids = {l.symptom_id for l in disease.symptom_links}
    available_symptoms = Symptom.query.filter(~Symptom.id.in_(linked_symptom_ids)).order_by(Symptom.name).all() \
        if linked_symptom_ids else Symptom.query.order_by(Symptom.name).all()
    return render_template(
        "health/disease_type_detail.html",
        disease=disease,
        links=sorted(disease.symptom_links, key=lambda l: l.symptom.name),
        available_symptoms=available_symptoms,
    )


@health_bp.route("/disease-types/link-wizard", methods=["GET", "POST"])
@login_required
@require_permission("medical_options.manage")
def link_wizard():
    """معالج تفاعلي خطوة بخطوة (بند إضافي 127، تكملة) — بديل شاشة
    الجدول لمن يفضّل تدفّق أسئلة مبسّط: مرض ← أعراض (اختيار متعدد) ←
    قوة العرض ← خيارات الأمان، بنفس الحقول والقيود الموجودة أصلاً
    (وزن 1-3، إجباري/استبعادي/عزل). خطوات الواجهة كلها JS بلا تنقّل
    صفحات — POST واحد بالنهاية ينشئ رابط لكل عرض مختار بنفس القيم."""
    if request.method == "POST":
        disease = DiseaseType.query.get_or_404(request.form.get("disease_id", type=int))
        symptom_ids = [int(x) for x in request.form.getlist("symptom_ids")]
        if not symptom_ids:
            flash("لازم تختار عرض واحد على الأقل", "error")
            return redirect(url_for("health.link_wizard"))
        weight = max(1, min(3, request.form.get("weight", type=int) or 2))
        is_required = bool(request.form.get("is_required"))
        is_exclusionary = bool(request.form.get("is_exclusionary"))
        requires_isolation = bool(request.form.get("requires_isolation"))

        created, updated = 0, 0
        for symptom_id in symptom_ids:
            link = DiseaseSymptomLink.query.filter_by(disease_type_id=disease.id, symptom_id=symptom_id).first()
            if link:
                link.weight, link.is_required = weight, is_required
                link.is_exclusionary, link.requires_isolation = is_exclusionary, requires_isolation
                updated += 1
            else:
                db.session.add(DiseaseSymptomLink(
                    disease_type_id=disease.id, symptom_id=symptom_id, weight=weight,
                    is_required=is_required, is_exclusionary=is_exclusionary,
                    requires_isolation=requires_isolation,
                ))
                created += 1
        db.session.add(AuditLog(actor_user_id=current_user.id, action="disease_symptom_link.wizard_batch",
                                 entity_type="DiseaseType", entity_id=disease.id,
                                 details=f"{disease.name}: +{created} جديد، {updated} محدَّث"))
        db.session.commit()
        flash(f"تم — {created} رابط جديد و{updated} تحديث لمرض {disease.name}", "success")
        return redirect(url_for("health.disease_type_detail", disease_id=disease.id))

    return render_template(
        "health/disease_link_wizard.html",
        diseases=DiseaseType.query.order_by(DiseaseType.name).all(),
        symptoms=Symptom.query.order_by(Symptom.name).all(),
    )


@health_bp.route("/disease-types/<int:disease_id>/links/new", methods=["POST"])
@login_required
@require_permission("medical_options.manage")
def disease_symptom_link_new(disease_id):
    disease = DiseaseType.query.get_or_404(disease_id)
    symptom_id = request.form.get("symptom_id", type=int)
    if not symptom_id:
        flash("لازم تختار عرض", "error")
        return redirect(url_for("health.disease_type_detail", disease_id=disease.id))
    if DiseaseSymptomLink.query.filter_by(disease_type_id=disease.id, symptom_id=symptom_id).first():
        flash("هذا العرض مربوط بهذا المرض أصلاً", "error")
        return redirect(url_for("health.disease_type_detail", disease_id=disease.id))
    symptom = Symptom.query.get_or_404(symptom_id)
    link = DiseaseSymptomLink(
        disease_type_id=disease.id, symptom_id=symptom_id,
        weight=max(1, min(3, request.form.get("weight", type=int) or 1)),
        is_required=bool(request.form.get("is_required")),
        is_exclusionary=bool(request.form.get("is_exclusionary")),
        requires_isolation=bool(request.form.get("requires_isolation")),
    )
    db.session.add(link)
    db.session.add(AuditLog(actor_user_id=current_user.id, action="disease_symptom_link.create",
                             entity_type="DiseaseSymptomLink", details=f"{disease.name} + {symptom.name}"))
    db.session.commit()
    flash("تمت إضافة الرابط", "success")
    return redirect(url_for("health.disease_type_detail", disease_id=disease.id))


@health_bp.route("/disease-types/links/<int:link_id>/update", methods=["POST"])
@login_required
@require_permission("medical_options.manage")
def disease_symptom_link_update(link_id):
    link = DiseaseSymptomLink.query.get_or_404(link_id)
    link.weight = max(1, min(3, request.form.get("weight", type=int) or 1))
    link.is_required = bool(request.form.get("is_required"))
    link.is_exclusionary = bool(request.form.get("is_exclusionary"))
    link.requires_isolation = bool(request.form.get("requires_isolation"))
    db.session.add(AuditLog(actor_user_id=current_user.id, action="disease_symptom_link.update",
                             entity_type="DiseaseSymptomLink", entity_id=link.id))
    db.session.commit()
    flash("تم تحديث الرابط", "success")
    return redirect(url_for("health.disease_type_detail", disease_id=link.disease_type_id))


@health_bp.route("/disease-types/links/<int:link_id>/delete", methods=["POST"])
@login_required
@require_permission("medical_options.manage")
def disease_symptom_link_delete(link_id):
    link = DiseaseSymptomLink.query.get_or_404(link_id)
    disease_id = link.disease_type_id
    db.session.add(AuditLog(actor_user_id=current_user.id, action="disease_symptom_link.delete",
                             entity_type="DiseaseSymptomLink", entity_id=link.id))
    db.session.delete(link)
    db.session.commit()
    flash("تم حذف الرابط", "success")
    return redirect(url_for("health.disease_type_detail", disease_id=disease_id))


# ---------- قائمة أعراض الطوارئ الديناميكية (بند إضافي 127، المرحلة 4) ----------
# قبل هذا البند، `EMERGENCY_SYMPTOMS` كان قاموساً ثابتاً بالكود — أي
# إضافة أو تعديل يحتاج تعديل كود ونشر جديد. صار جدولاً قابلاً للإدارة
# من هنا، بنفس صلاحية "الخيارات الطبية" (medical_options.manage).

@health_bp.route("/emergency-symptoms")
@login_required
@require_permission("health.view")
def emergency_symptoms_list():
    entries = EmergencySymptom.query.join(Symptom).order_by(Symptom.name).all()
    linked_symptom_ids = {e.symptom_id for e in entries}
    available_symptoms = Symptom.query.filter(~Symptom.id.in_(linked_symptom_ids)).order_by(Symptom.name).all() \
        if linked_symptom_ids else Symptom.query.order_by(Symptom.name).all()
    return render_template(
        "health/emergency_symptoms_list.html",
        entries=entries, available_symptoms=available_symptoms,
        severity_choices=EmergencySymptom.SEVERITY_CHOICES,
    )


@health_bp.route("/emergency-symptoms/new", methods=["POST"])
@login_required
@require_permission("medical_options.manage")
def emergency_symptoms_new():
    symptom_id = request.form.get("symptom_id", type=int)
    differential = request.form.get("differential", "").strip()
    advice = request.form.get("advice", "").strip()
    if not symptom_id or not differential or not advice:
        flash("لازم تحدد العرض وتكتب التشخيص التفريقي والتوصية", "error")
        return redirect(url_for("health.emergency_symptoms_list"))
    if EmergencySymptom.query.filter_by(symptom_id=symptom_id).first():
        flash("هذا العرض مسجَّل بقائمة الطوارئ أصلاً", "error")
        return redirect(url_for("health.emergency_symptoms_list"))
    severity = request.form.get("severity") or EmergencySymptom.SEVERITY_CHOICES[-1]
    if severity not in EmergencySymptom.SEVERITY_CHOICES:
        severity = EmergencySymptom.SEVERITY_CHOICES[-1]
    entry = EmergencySymptom(symptom_id=symptom_id, severity=severity, differential=differential, advice=advice)
    db.session.add(entry)
    db.session.add(AuditLog(actor_user_id=current_user.id, action="emergency_symptom.create",
                             entity_type="EmergencySymptom"))
    db.session.commit()
    flash("تمت إضافة عرض الطوارئ", "success")
    return redirect(url_for("health.emergency_symptoms_list"))


@health_bp.route("/emergency-symptoms/<int:entry_id>/delete", methods=["POST"])
@login_required
@require_permission("medical_options.manage")
def emergency_symptoms_delete(entry_id):
    entry = EmergencySymptom.query.get_or_404(entry_id)
    db.session.add(AuditLog(actor_user_id=current_user.id, action="emergency_symptom.delete",
                             entity_type="EmergencySymptom", entity_id=entry.id))
    db.session.delete(entry)
    db.session.commit()
    flash("تم حذف عرض الطوارئ", "success")
    return redirect(url_for("health.emergency_symptoms_list"))


# ---------- الأطباء ----------

@health_bp.route("/doctors")
@login_required
@require_permission("health.view")
def doctors_list():
    doctors = Doctor.query.order_by(Doctor.name).all()
    return render_template("health/doctors_list.html", doctors=doctors)


@health_bp.route("/doctors/new", methods=["GET", "POST"])
@login_required
@require_permission("health.manage")
def doctors_new():
    if request.method == "POST":
        doctor = Doctor(
            name=request.form["name"],
            phone=request.form.get("phone"),
            specialty=request.form.get("specialty"),
            is_external=request.form.get("is_external") == "1",
            clinic_name=request.form.get("clinic_name"),
            area=request.form.get("area"),
            notes=request.form.get("notes"),
        )
        db.session.add(doctor)
        db.session.commit()
        flash("تمت إضافة الطبيب", "success")
        return redirect(url_for("health.doctors_list"))
    return render_template("health/doctor_form.html")


# ---------- الزيارات البيطرية ----------

@health_bp.route("/vet-visits")
@login_required
@require_permission("health.view")
def vet_visits_list():
    visits = VetVisit.query.order_by(VetVisit.date.desc()).all()
    return render_template("health/vet_visits_list.html", visits=visits)


@health_bp.route("/vet-visits/new", methods=["GET", "POST"])
@login_required
@require_permission("health.manage")
def vet_visits_new():
    if request.method == "POST":
        animal_id = int(request.form["animal_id"])
        pharmacy_id = request.form.get("pharmacy_id") or None
        ok, override_note = _check_redose_guard(
            animal_id=animal_id, pharmacy_id=pharmacy_id,
            override_reason=request.form.get("redose_override_reason") or None,
            entity_type="VetVisit",
        )
        if not ok:
            return redirect(url_for("health.vet_visits_new"))
        notes = request.form.get("notes")
        if override_note:
            notes = (notes + " | " if notes else "") + override_note
        try:
            health_service.record_vet_visit(
                actor_user_id=current_user.id,
                animal_id=animal_id,
                doctor_id=int(request.form["doctor_id"]),
                date_=date.fromisoformat(request.form["date"]),
                diagnosis=request.form.get("diagnosis"),
                pharmacy_id=pharmacy_id,
                quantity_used=float(request.form["quantity_used"]) if request.form.get("quantity_used") else None,
                cost=float(request.form.get("cost") or 0),
                notes=notes,
            )
        except health_service.IncompleteRecordError as e:
            flash(str(e), "error")
            return redirect(url_for("health.vet_visits_new"))
        flash("تم تسجيل الزيارة (والتكلفة اتحسبت تلقائياً من سعر الوحدة لو الدواء يتطلبها)", "success")
        _complete_originating_task(request.form.get("task_id"))
        return redirect(url_for("health.vet_visits_list"))

    return render_template(
        "health/vet_visit_form.html",
        animals=Animal.query.order_by(Animal.animal_no).all(),
        doctors=Doctor.query.filter_by(status="active").all(),
        medicines=Pharmacy.query.filter_by(status="active").all(),
        # اختصار "تأكيد التنفيذ" من مهمة علاج مخطَّط (بند إضافي 50)
        prefill_task_id=request.args.get("task_id", type=int),
        prefill_animal_id=request.args.get("animal_id", type=int),
        prefill_pharmacy_id=request.args.get("pharmacy_id", type=int),
        prefill_quantity_used=request.args.get("quantity_used", type=float),
    )


# ---------- الأمراض ----------

@health_bp.route("/diseases")
@login_required
@require_permission("health.view")
def diseases_list():
    diseases = Disease.query.order_by(Disease.date.desc()).all()
    return render_template("health/diseases_list.html", diseases=diseases)


@health_bp.route("/diseases/new-simple")
@login_required
@require_permission("health.manage")
def diseases_new_simple():
    """تسجيل حالة مرضية — واجهة "بسيط جداً" (بند إضافي 225): بطاقات
    كبيرة، سؤال وحد بالمرة (JS بسيط بالقالب، بدون منطق سيرفر جديد).
    الفورم يرسل مباشرة لنفس `health.diseases_new` الحالية — صفر منطق
    حفظ مكرَّر، نفس البيانات ونفس التحقق بالضبط."""
    return render_template(
        "health/disease_new_simple.html",
        animals=Animal.query.filter_by(status="active").order_by(Animal.animal_no).all(),
        disease_types=DiseaseType.query.order_by(DiseaseType.name).all(),
        today=date.today().isoformat(),
    )


@health_bp.route("/diseases/new", methods=["GET", "POST"])
@login_required
@require_permission("health.manage")
def diseases_new():
    if request.method == "POST":
        animal_id = int(request.form["animal_id"])
        pharmacy_id = request.form.get("pharmacy_id") or None
        ok, _override_note = _check_redose_guard(
            animal_id=animal_id, pharmacy_id=pharmacy_id,
            override_reason=request.form.get("redose_override_reason") or None,
            entity_type="Disease",
        )
        if not ok:
            return redirect(url_for("health.diseases_new"))
        try:
            health_service.record_disease(
                actor_user_id=current_user.id,
                animal_id=animal_id,
                disease_name=request.form["disease_name"],
                date_=date.fromisoformat(request.form["date"]),
                severity=request.form.get("severity"),
                pharmacy_id=pharmacy_id,
                quantity_used=float(request.form["quantity_used"]) if request.form.get("quantity_used") else None,
                treatment_cost=float(request.form.get("treatment_cost") or 0),
            )
        except health_service.IncompleteRecordError as e:
            flash(str(e), "error")
            return redirect(url_for("health.diseases_new"))
        flash("تم تسجيل الحالة المرضية (والتكلفة اتحسبت تلقائياً من سعر الوحدة لو الدواء يتطلبها)", "success")
        _complete_originating_task(request.form.get("task_id"))
        return redirect(url_for("health.diseases_list"))

    return render_template(
        "health/disease_form.html",
        animals=Animal.query.order_by(Animal.animal_no).all(),
        medicines=Pharmacy.query.filter_by(status="active").all(),
        disease_types=DiseaseType.query.order_by(DiseaseType.name).all(),
        # تعبئة مسبقة من المساعد التشخيصي (بند إضافي، 2026-07-24) —
        # اختياري بالكامل، الدكتور يقدر يعدّل أو يمسح قبل الحفظ.
        prefill_animal_id=request.args.get("animal_id", type=int),
        prefill_disease_name=request.args.get("disease_name"),
        prefill_note=request.args.get("diagnosis_note"),
        # اختصار "تأكيد التنفيذ" من مهمة علاج مخطَّط (بند إضافي 50)
        prefill_task_id=request.args.get("task_id", type=int),
        prefill_pharmacy_id=request.args.get("pharmacy_id", type=int),
        prefill_quantity_used=request.args.get("quantity_used", type=float),
    )


@health_bp.route("/body-condition-guide")
@login_required
@require_permission("health.view")
def body_condition_guide():
    """دليل تقييم حالة الجسم (BCS، بند إضافي 173) — مقياس 1-5 القياسي
    عالمياً لتقييم الأغنام/الماعز باللمس اليدوي فوق العمود الفقري
    والأضلاع (نفس مبدأ INJECTION_GUIDE: مرجع عام موثّق، مو قياساً
    آلياً). **رسوم توضيحية مبسّطة (SVG)، مو صوراً فوتوغرافية حقيقية**
    — التطبيق ما يقدر يولّد صوراً بيطرية موثوقة، فالبديل الأمين رسم
    تخطيطي يوضح الفكرة بدل ادّعاء واقعية غير موجودة."""
    return render_template("health/body_condition_guide.html", scale=health_service.BODY_CONDITION_SCALE)


@health_bp.route("/injection-guide")
@login_required
@require_permission("health.view")
def injection_guide():
    return render_template("health/injection_guide.html", guide=health_service.INJECTION_GUIDE)


# ---------- المساعد التشخيصي (بند إضافي، 2026-07-24) ----------

@health_bp.route("/diagnose")
@login_required
@require_permission("health.manage")
def diagnose_start():
    """الخطوة الأولى: اختيار حيوان + عرض رئيسي. لو `primary` موجود
    بالطلب، نعرض أعراض المتابعة ذات الصلة (الخطوة الثانية) بنفس
    الصفحة — بدون جافاسكربت، إعادة تحميل بس."""
    primary_id = request.args.get("primary", type=int)
    secondary_symptoms = health_service.related_symptoms(primary_id) if primary_id else []
    animal_id = request.args.get("animal_id", type=int)
    selected_animal = Animal.query.get(animal_id) if animal_id else None
    return render_template(
        "health/diagnose_start.html",
        animals=Animal.query.filter_by(status="active").order_by(Animal.animal_no).all(),
        primary_symptoms=Symptom.query.filter_by(is_primary=True).order_by(Symptom.name).all(),
        selected_primary_id=primary_id,
        secondary_symptoms=secondary_symptoms,
        animal_id=animal_id,
        temperature=request.args.get("temperature", type=float),
        selected_animal_age=health_service.animal_age_label(selected_animal),
    )


@health_bp.route("/diagnose/result", methods=["POST"])
@login_required
@require_permission("health.manage")
def diagnose_result():
    symptom_ids = [int(x) for x in request.form.getlist("symptom_ids")]
    temperature = request.form.get("temperature", type=float)
    results = health_service.score_diagnoses(symptom_ids=symptom_ids, temperature=temperature)
    animal = Animal.query.get(int(request.form["animal_id"])) if request.form.get("animal_id") else None
    matched_names = [s.name for s in Symptom.query.filter(Symptom.id.in_(symptom_ids)).all()] if symptom_ids else []

    # بروتوكول الطوارئ والأعراض الحادة (بند إضافي 51) — يفحص أعراض
    # الطوارئ بمعزل عن ترتيب الاحتمالات العادي، ويعزل فوراً لو الحيوان
    # محدَّد.
    emergency = None
    if animal:
        emergency = health_service.check_emergency_symptoms(
            animal_id=animal.id, symptom_names=matched_names, actor_user_id=current_user.id,
        )

    # قوالب بروتوكول علاج مرتبطة بأي من احتمالات التشخيص (بند إضافي 52)
    # — تطبيق بنقرة واحدة بدل الدخول لشاشة البروتوكولات يدوياً.
    disease_type_ids = [r["disease_type"].id for r in results]
    protocols_by_disease = {}
    if disease_type_ids:
        for p in TreatmentProtocol.query.filter(
            TreatmentProtocol.disease_type_id.in_(disease_type_ids), TreatmentProtocol.status == "active",
        ).all():
            protocols_by_disease.setdefault(p.disease_type_id, []).append(p)

    return render_template(
        "health/diagnose_result.html",
        results=results, animal=animal, entered_symptoms=matched_names,
        free_text=request.form.get("free_text_symptoms"),
        today=date.today().isoformat(),
        emergency=emergency,
        temperature=temperature,
        temperature_note=health_service.classify_temperature(temperature),
        animal_age=health_service.animal_age_label(animal),
        protocols_by_disease=protocols_by_disease,
    )


@health_bp.route("/diseases/<int:disease_id>/close", methods=["POST"])
@login_required
@require_permission("health.manage")
def disease_close(disease_id):
    from datetime import datetime, timezone
    disease = Disease.query.get_or_404(disease_id)
    disease.status = "closed"
    disease.recovery_note = request.form["recovery_note"]
    disease.closed_at = datetime.now(timezone.utc)
    disease.closed_by_id = current_user.id
    db.session.add(AuditLog(actor_user_id=current_user.id, action="disease.close",
                             entity_type="Disease", entity_id=disease.id, details=disease.recovery_note))
    db.session.commit()

    from app.core.cycle_engine import record_cycle_event
    record_cycle_event(disease.animal, "disease", source_type="Disease", source_id=disease.id)

    # بند إضافي 111 — قبل هذا، `withdrawal_until` كان يُحسب ويُخزَّن
    # وقت تسجيل الدواء (`_withdrawal_until`)، ويُستخدم بس كبوابة منع
    # بيع (`animal_under_withdrawal`) — بدون أي تذكير فعلي ينبّهك لما
    # تنتهي الفترة فعلاً. إغلاق المرض (نهاية العلاج) هو أنسب لحظة
    # نولّد فيها التذكير، لأنها أول نقطة نتأكد فيها إن العلاج خلص فعلاً.
    if disease.withdrawal_until:
        from app.team import task_service
        task_service.create_suggested_task(
            title=f"✅ تأكد انتهاء فترة سحب الدواء — {disease.animal.animal_no}",
            task_type="withdrawal_reminder", animal_id=disease.animal_id,
            barn_id=disease.animal.barn_id, due_date=disease.withdrawal_until,
            source_type="Disease", source_id=disease.id,
            notes=f"العلاج ({disease.disease_name}) خلص وأُغلق — تأكد إن فترة سحب "
                  f"الدواء انتهت فعلاً ({disease.withdrawal_until}) قبل أي بيع أو ذبح.",
        )

    flash("تم إغلاق السجل المرضي", "success")
    return redirect(url_for("health.diseases_list"))


# ---------- التطعيمات ----------

@health_bp.route("/vaccinations")
@login_required
@require_permission("health.view")
def vaccinations_list():
    rows = Vaccination.query.order_by(Vaccination.date.desc()).all()
    return render_template("health/vaccinations_list.html", rows=rows)


@health_bp.route("/vaccinations/new", methods=["GET", "POST"])
@login_required
@require_permission("health.manage")
def vaccinations_new():
    health_service.seed_default_vaccine_catalog()  # بند إضافي 292
    if request.method == "POST":
        next_due = request.form.get("next_due_date")
        animal_id = int(request.form["animal_id"])
        pharmacy_id = request.form.get("pharmacy_id") or None
        ok, _override_note = _check_redose_guard(
            animal_id=animal_id, pharmacy_id=pharmacy_id,
            override_reason=request.form.get("redose_override_reason") or None,
            entity_type="Vaccination",
        )
        if not ok:
            return redirect(url_for("health.vaccinations_new"))
        try:
            health_service.record_vaccination(
                actor_user_id=current_user.id,
                animal_id=animal_id,
                vaccine_name=request.form["vaccine_name"],
                date_=date.fromisoformat(request.form["date"]),
                next_due_date=date.fromisoformat(next_due) if next_due else None,
                pharmacy_id=pharmacy_id,
                quantity_used=float(request.form["quantity_used"]) if request.form.get("quantity_used") else None,
            )
        except health_service.IncompleteRecordError as e:
            flash(str(e), "error")
            return redirect(url_for("health.vaccinations_new"))
        flash("تم تسجيل التطعيم (والتكلفة اتحسبت تلقائياً من سعر الوحدة لو الدواء يتطلبها)", "success")
        _complete_originating_task(request.form.get("task_id"))
        # تنبيه سياقي فوري (بند إضافي 230): لو حظيرة هذا الرأس فيها موعد
        # بجدول التحصينات مستحق قريباً، وجّه المستخدم لمراجعته فوراً.
        from app.core.alerts_service import vaccination_followup_toast
        from app.core.toast_service import flash_toast
        flash_toast(vaccination_followup_toast(animal_id))
        return redirect(url_for("health.vaccinations_list"))

    return render_template(
        "health/vaccination_form.html",
        animals=Animal.query.order_by(Animal.animal_no).all(),
        medicines=Pharmacy.query.filter_by(status="active").all(),
        # اختصار "تأكيد التنفيذ" من مهمة علاج مخطَّط (بند إضافي 50)
        prefill_task_id=request.args.get("task_id", type=int),
        prefill_animal_id=request.args.get("animal_id", type=int),
        prefill_pharmacy_id=request.args.get("pharmacy_id", type=int),
        prefill_quantity_used=request.args.get("quantity_used", type=float),
    )


# ---------- قوالب بروتوكول العلاج (بند إضافي 52) ----------

@health_bp.route("/protocols")
@login_required
@require_permission("health.view")
def protocols_list():
    protocols = TreatmentProtocol.query.order_by(TreatmentProtocol.name).all()
    return render_template(
        "health/protocols_list.html", protocols=protocols,
        prefill_animal_id=request.args.get("animal_id", type=int),
    )


@health_bp.route("/protocols/new", methods=["GET", "POST"])
@login_required
@require_permission("medical_options.manage")
def protocols_new():
    if request.method == "POST":
        protocol = TreatmentProtocol(
            name=request.form["name"],
            description=request.form.get("description") or None,
            disease_type_id=request.form.get("disease_type_id") or None,
            created_by_id=current_user.id,
        )
        db.session.add(protocol)
        db.session.flush()
        for i in PROTOCOL_STEP_SLOTS:
            step_title = request.form.get(f"step_title_{i}")
            pharmacy_id = request.form.get(f"pharmacy_id_{i}")
            quantity = request.form.get(f"quantity_{i}")
            if step_title and pharmacy_id and quantity:
                db.session.add(TreatmentProtocolStep(
                    protocol_id=protocol.id,
                    day_offset=int(request.form.get(f"day_offset_{i}") or 0),
                    step_title=step_title,
                    pharmacy_id=int(pharmacy_id),
                    quantity=float(quantity),
                    treatment_kind=request.form.get(f"treatment_kind_{i}") or "vet_visit",
                    notes=request.form.get(f"step_notes_{i}") or None,
                ))
        db.session.add(AuditLog(actor_user_id=current_user.id, action="protocol.create",
                                 entity_type="TreatmentProtocol", entity_id=protocol.id))
        db.session.commit()
        flash("تم إنشاء البروتوكول", "success")
        return redirect(url_for("health.protocols_list"))
    return render_template(
        "health/protocol_form.html",
        step_slots=PROTOCOL_STEP_SLOTS,
        medicines=Pharmacy.query.filter_by(status="active").order_by(Pharmacy.name).all(),
        disease_types=DiseaseType.query.order_by(DiseaseType.name).all(),
        treatment_kinds=[("vet_visit", "زيارة بيطرية"), ("disease", "حالة مرضية"), ("vaccination", "تطعيم")],
    )


@health_bp.route("/protocols/<int:protocol_id>/apply", methods=["GET", "POST"])
@login_required
@require_permission("health.manage")
def protocols_apply(protocol_id):
    protocol = TreatmentProtocol.query.get_or_404(protocol_id)
    if request.method == "POST":
        application = protocol_service.apply_protocol(
            protocol, animal_id=int(request.form["animal_id"]),
            start_date=date.fromisoformat(request.form["start_date"]),
            actor_user_id=current_user.id,
        )
        flash(f'تم تطبيق البروتوكول "{protocol.name}" — تولّدت {len(protocol.steps)} مهمة علاج مخطَّطة بانتظار مراجعة الدكتور.', "success")
        return redirect(url_for("core.animal_detail", animal_id=application.animal_id, tab="vet"))
    return render_template(
        "health/protocol_apply_form.html", protocol=protocol,
        animals=Animal.query.filter_by(status="active").order_by(Animal.animal_no).all(),
        prefill_animal_id=request.args.get("animal_id", type=int),
        today=date.today().isoformat(),
    )


# ---------- تقويم التحصينات (بند إضافي 63، 2026-07-28) ----------
# جدولة تحصين جماعي مستقبلي لحظيرة كاملة — مفهوم جديد منفصل عن
# next_due_date (اللي يُحسب بعد تحصين فعلي، مو قبله). هذا البند يبني
# الجدول + شاشات إدارته بس (إنشاء/عرض/إلغاء/تعليم كمكتمل يدوياً) — ربطه
# التلقائي بشاشة التحصين الجماعي الفعلية (بدء مباشر من الحظيرة، شريط
# مخزون حي) هو بند لاحق منفصل.

@health_bp.route("/vaccination-schedule")
@login_required
@require_permission("health.view")
def vaccination_schedule_list():
    upcoming = (VaccinationSchedule.query.filter_by(status="scheduled")
                .order_by(VaccinationSchedule.planned_date).all())
    past = (VaccinationSchedule.query.filter(VaccinationSchedule.status != "scheduled")
            .order_by(VaccinationSchedule.planned_date.desc()).limit(30).all())
    return render_template(
        "health/vaccination_schedule_list.html",
        upcoming=upcoming, past=past, today=date.today(),
    )


@health_bp.route("/vaccination-schedule/new", methods=["GET", "POST"])
@login_required
@require_permission("health.manage")
def vaccination_schedule_new():
    health_service.seed_default_vaccine_catalog()  # بند إضافي 292
    if request.method == "POST":
        pharmacy = Pharmacy.query.get_or_404(int(request.form["pharmacy_id"]))
        if pharmacy.medicine_class != "vaccine":
            flash("لازم تختار لقاحاً فعلياً مسجَّلاً بالصيدلية بفئة (لقاح)", "error")
            return redirect(url_for("health.vaccination_schedule_new"))
        # رؤوس مختارة يدوياً (بند إضافي 210) — لو ما اختار المستخدم
        # ولا رأس (ترك القائمة فاضية أو ضغط "الكل")، نخزّن فاضي عشان
        # يبقى يعني "كل رؤوس الحظيرة" حياً (سلوك `live_head_count`
        # الأصلي بلا تغيير).
        selected_ids = request.form.getlist("animal_ids")
        target_ids = ",".join(selected_ids) if selected_ids else None
        schedule = VaccinationSchedule(
            barn_id=int(request.form["barn_id"]),
            pharmacy_id=pharmacy.id,
            planned_date=date.fromisoformat(request.form["planned_date"]),
            notes=request.form.get("notes") or None,
            target_animal_ids=target_ids,
        )
        db.session.add(schedule)
        db.session.add(AuditLog(actor_user_id=current_user.id, action="vaccination_schedule.create",
                                 entity_type="VaccinationSchedule", details=f"barn={schedule.barn_id}"))
        db.session.commit()
        flash("تمت جدولة التحصين", "success")
        return redirect(url_for("health.vaccination_schedule_list"))
    barns = Barn.query.order_by(Barn.barn_name).all()
    barn_animals = {
        b.id: [{"id": a.id, "animal_no": a.animal_no}
               for a in Animal.query.filter_by(barn_id=b.id, status="active").order_by(Animal.animal_no).all()]
        for b in barns
    }
    return render_template(
        "health/vaccination_schedule_form.html",
        barns=barns,
        vaccines=Pharmacy.query.filter_by(status="active", medicine_class="vaccine").all(),
        today=date.today().isoformat(),
        barn_head_counts={b.id: Animal.query.filter_by(barn_id=b.id, status="active").count() for b in barns},
        barn_animals=barn_animals,
    )


@health_bp.route("/vaccination-schedule/<int:schedule_id>/cancel", methods=["POST"])
@login_required
@require_permission("health.manage")
def vaccination_schedule_cancel(schedule_id):
    schedule = VaccinationSchedule.query.get_or_404(schedule_id)
    schedule.status = "cancelled"
    db.session.commit()
    flash("تم إلغاء الجدولة", "success")
    return redirect(url_for("health.vaccination_schedule_list"))


@health_bp.route("/vaccination-schedule/<int:schedule_id>/complete", methods=["POST"])
@login_required
@require_permission("health.manage")
def vaccination_schedule_complete(schedule_id):
    """تعليم يدوي بالوقت الحالي (بند 63) — لو التحصين الفعلي صار عبر
    شاشة التحصين الجماعي العادية بدون ربط تلقائي بعد. الربط الآلي
    (تعليم تلقائي عند تنفيذ التحصين الفعلي) بند لاحق."""
    from datetime import datetime, timezone
    schedule = VaccinationSchedule.query.get_or_404(schedule_id)
    schedule.status = "completed"
    schedule.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash("تم تعليم الجدولة كمكتملة", "success")
    return redirect(url_for("health.vaccination_schedule_list"))
