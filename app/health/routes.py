from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.health import health_bp
from app.auth.decorators import require_permission
from app.extensions import db
from app.models import (
    Pharmacy, Doctor, VetVisit, Disease, Vaccination, Animal, AuditLog, DiseaseType, Symptom,
    FarmSettings, Task, TreatmentProtocol, TreatmentProtocolStep, ProtocolApplication,
)
from app.health import health_service
from app.team import task_service as tsvc
from app.core import protocol_service

PROTOCOL_STEP_SLOTS = range(8)


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
    items = Pharmacy.query.order_by(Pharmacy.name).all()
    return render_template(
        "health/pharmacy_list.html", items=items, today=date.today(),
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
    # بدائل بنفس الفئة (بند إضافي، 2026-07-24) — أدوية نشطة، فوق حدها
    # الأدنى فعلياً، بنفس تصنيف الدواء الناقص — اقتراح سريع بدون أي
    # افتراض علمي (نفس الاسم/الشركة/التركيبة)، بس تصنيف مطابق كما أدخله
    # الدكتور بنفسه بحقل "الفئة".
    alternatives = {}
    for item in items:
        if not item.category:
            continue
        alternatives[item.id] = (
            Pharmacy.query.filter_by(status="active", category=item.category)
            .filter(Pharmacy.id != item.id)
            .filter(Pharmacy.available_qty > db.func.coalesce(Pharmacy.min_stock_qty, 0))
            .all()
        )
    return render_template("health/pharmacy_shortages.html", items=items, alternatives=alternatives)


@health_bp.route("/pharmacy/new", methods=["GET", "POST"])
@login_required
@require_permission("pharmacy.manage")
def pharmacy_new():
    if request.method == "POST":
        item = Pharmacy(
            name=request.form["name"],
            category=request.form.get("category"),
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
            notes=request.form.get("notes"),
        )
        db.session.add(item)
        db.session.commit()
        flash("تمت إضافة الدواء", "success")
        return redirect(url_for("health.pharmacy_list"))
    return render_template(
        "health/pharmacy_form.html",
        medicine_classes=Pharmacy.MEDICINE_CLASSES,
        medicine_class_labels=Pharmacy.MEDICINE_CLASS_LABELS_AR,
    )


@health_bp.route("/pharmacy/<int:pharmacy_id>/edit", methods=["GET", "POST"])
@login_required
@require_permission("pharmacy.manage")
def pharmacy_edit(pharmacy_id):
    item = Pharmacy.query.get_or_404(pharmacy_id)
    if request.method == "POST":
        item.name = request.form["name"]
        item.category = request.form.get("category")
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
        item.notes = request.form.get("notes")
        db.session.commit()
        flash("تم تحديث بيانات الدواء", "success")
        return redirect(url_for("health.pharmacy_list"))
    return render_template(
        "health/pharmacy_form.html", item=item,
        medicine_classes=Pharmacy.MEDICINE_CLASSES,
        medicine_class_labels=Pharmacy.MEDICINE_CLASS_LABELS_AR,
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
    return render_template(
        "health/diagnose_start.html",
        animals=Animal.query.filter_by(status="active").order_by(Animal.animal_no).all(),
        primary_symptoms=Symptom.query.filter_by(is_primary=True).order_by(Symptom.name).all(),
        selected_primary_id=primary_id,
        secondary_symptoms=secondary_symptoms,
        animal_id=request.args.get("animal_id", type=int),
    )


@health_bp.route("/diagnose/result", methods=["POST"])
@login_required
@require_permission("health.manage")
def diagnose_result():
    symptom_ids = [int(x) for x in request.form.getlist("symptom_ids")]
    results = health_service.score_diagnoses(symptom_ids=symptom_ids)
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
