from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_babel import gettext as _
from flask_login import login_required, current_user

from app.repro import repro_bp
from app.auth.decorators import require_permission
from app.extensions import db
from app.models import (
    Animal, Barn, Doctor, AuditLog, FarmSettings,
    Mating, Pregnancy, SonarResult,
    TwinEstrusProgram, TwinEstrusAttempt, ReproDevice, HormoneInjection,
)


def _females():
    return Animal.query.filter_by(gender="أنثى").order_by(Animal.animal_no).all()


def _age_days(animal: Animal) -> int | None:
    if not animal.birth_date:
        return None
    return (date.today() - animal.birth_date).days


def _males():
    """قائمة الفحول المتاحة بفورم التقريع (بند إضافي 231) — فحل أصغر من
    `min_male_breeding_age_days` يُستبعد صامتاً من القائمة أساساً: هذا مو
    قرار حكم يستاهل تحذير قابل للتجاوز (زي القرابة)، هذا عدم نضج
    فسيولوجي بسيط. فحل بدون تاريخ ميلاد مسجَّل (عمره غير معروف) يبقى
    بالقائمة — ما نمنعه بناءً على معلومة ناقصة."""
    fs = FarmSettings.get()
    rows = Animal.query.filter_by(gender="ذكر").order_by(Animal.animal_no).all()
    return [m for m in rows if (age := _age_days(m)) is None or age >= fs.min_male_breeding_age_days]


def _log(action, entity_type, entity_id, details=""):
    db.session.add(AuditLog(
        actor_user_id=current_user.id, action=action,
        entity_type=entity_type, entity_id=entity_id, details=details,
    ))


def _send_override_request(*, female_id, male_id, relation, reason, date_, male_note, barn_id, notes):
    """طلب تجاوز تحذير قرابة وراثية (بند إضافي 231) — الدكتور ما يملك
    صلاحية التجاوز المباشر، فبدل ما نرفضه بصمت، نرسل طلبه لكل من يملك
    `repro.override_close_relation` (صاحب الحلال افتراضياً): إشعار
    تيليجرام فيه رابط جاهز يفتح نفس الفورم معبّى، ومهمة متابعة بحسابه —
    نفس نمط إشعارات نقص المخزون (`stock_alert_service.py`)."""
    from app.models import User, Task
    from app.core import telegram_service

    female = Animal.query.get(female_id)
    male = Animal.query.get(male_id)
    link = url_for(
        "repro.matings_new", female_id=female_id, male_id=male_id, date=date_,
        male_note=male_note or "", barn_id=barn_id or "", notes=notes or "",
        confirm_relation="1", override_reason=reason, _external=True,
    )
    message = (
        f"⚠️ طلب تجاوز قرابة وراثية من {current_user.name}\n"
        f"{female.animal_no if female else '-'} × {male.animal_no if male else '-'} "
        f"({relation['label']} — {relation['relation_type']})\n"
        f"السبب: {reason}\n"
        f"للمراجعة والتأكيد: {link}"
    )
    for user in User.query.filter(User.is_active_account.is_(True)).all():
        if not user.has_permission("repro.override_close_relation"):
            continue
        telegram_service.notify_user(user, message)
        task = Task(
            title=f"طلب تجاوز قرابة وراثية — {female.animal_no if female else '-'} × {male.animal_no if male else '-'}",
            task_type="custom", status="pending", assignee_id=user.id,
            notes=f"طلب من {current_user.name}. السبب: {reason}\nرابط التأكيد: {link}",
        )
        db.session.add(task)
    _log("mating.override_requested", "Animal", male_id,
         details=f"طلب من {current_user.name} — {reason}")
    db.session.commit()


# ---------- تقييم أداء الفحول (بند إضافي 183) ----------

@repro_bp.route("/sires")
@login_required
@require_permission("repro.view")
def sires_list():
    from app.core.sire_score_service import all_sire_scorecards
    return render_template("repro/sires_list.html", cards=all_sire_scorecards())


# ---------- التقريع العادي ----------

@repro_bp.route("/matings")
@login_required
@require_permission("repro.view")
def matings_list():
    rows = Mating.query.order_by(Mating.date.desc()).all()
    return render_template("repro/matings_list.html", rows=rows)


@repro_bp.route("/matings/export")
@login_required
@require_permission("repro.view")
def matings_export():
    """تصدير سجل التقريع (البيانات الوراثية الأساسية) Excel بضغطة زر
    واحدة (بند إضافي 179)."""
    from flask import Response
    from app.reports import export_service as ex
    rows = Mating.query.order_by(Mating.date.desc()).all()
    columns = ["التاريخ", "الأنثى", "الفحل", "ملاحظة الفحل الخارجي", "الحظيرة"]
    table_rows = [
        [
            str(r.date), r.female.animal_no if r.female else "-",
            r.male.animal_no if r.male else "-", r.male_note or "-",
            r.barn.barn_name if r.barn else "-",
        ]
        for r in rows
    ]
    buf = ex.build_excel("سجل التقريع", columns, table_rows)
    return Response(
        buf.read(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=matings_export.xlsx"},
    )


@repro_bp.route("/matings/new", methods=["GET", "POST"])
@login_required
@require_permission("repro.manage")
def matings_new():
    if request.method == "POST":
        female_id = int(request.form["female_id"])
        male_id = int(request.form["male_id"]) if request.form.get("male_id") else None

        # دفاع بعمق (بند إضافي 231) — تأكيد إضافي إن الفحل المختار فعلاً
        # ضمن قائمة الفحول المسموحة (عمر كافٍ)، حتى لو حاول أحد يرسل
        # male_id مباشرة بدون المرور بالقائمة المفلترة بالفورم.
        if male_id and male_id not in {m.id for m in _males()}:
            flash(_("هذا الفحل غير متاح للتقريع (عمره أقل من الحد الأدنى المسموح)"), "error")
            return render_template(
                "repro/mating_form.html",
                females=_females(), males=_males(), barns=Barn.query.order_by(Barn.barn_name).all(),
                form_data=request.form,
            )

        # محرك الوقاية من القرابة الوراثية (بند إضافي 175) — لو فيه
        # علاقة قرابة درجة أولى/ثانية موثّقة بالأنساب، ما نحفظ مباشرة؛
        # نعيد عرض النموذج بتحذير حرج ونطلب تأكيداً صريحاً قبل أي حفظ.
        from app.core import lineage_service
        relation = lineage_service.relationship_warning(female_id, male_id) if male_id else None
        if relation and request.form.get("confirm_relation") != "1":
            flash(_("⚠️ تحذير قرابة وراثية — راجع التفاصيل تحت قبل ما تأكد"), "error")
            return render_template(
                "repro/mating_form.html",
                females=_females(), males=_males(), barns=Barn.query.order_by(Barn.barn_name).all(),
                relation_warning=relation,
                form_data=request.form,
                can_override=current_user.has_permission("repro.override_close_relation"),
            )

        # صلاحية التجاوز الفعلي (بند إضافي 231) — تأكيد المربّع لحاله ما
        # يكفي إذا المستخدم ما يملك repro.override_close_relation (صاحب
        # الحلال بس افتراضياً). بدونها، ما نحفظ التقريع — نحوّله لطلب
        # تجاوز يوصل صاحب الحلال بإشعار فوري + مهمة، وهو يقرر بنفسه.
        if relation and not current_user.has_permission("repro.override_close_relation"):
            reason = (request.form.get("override_reason") or "").strip()
            if not reason:
                flash(_("⚠️ لازم تكتب سبب طلب التجاوز قبل الإرسال"), "error")
                return render_template(
                    "repro/mating_form.html",
                    females=_females(), males=_males(), barns=Barn.query.order_by(Barn.barn_name).all(),
                    relation_warning=relation, form_data=request.form, can_override=False,
                )
            _send_override_request(
                female_id=female_id, male_id=male_id, relation=relation, reason=reason,
                date_=request.form["date"], male_note=request.form.get("male_note"),
                barn_id=request.form.get("barn_id"), notes=request.form.get("notes"),
            )
            flash(_("تم إرسال طلب التجاوز لصاحب الحلال للتأكيد — بينتظر رده قبل ما يتسجّل التقريع"), "success")
            return redirect(url_for("repro.matings_list"))

        row = Mating(
            female_id=female_id,
            date=date.fromisoformat(request.form["date"]),
            male_id=male_id,
            male_note=request.form.get("male_note"),
            barn_id=request.form.get("barn_id") or None,
            notes=request.form.get("notes"),
        )
        db.session.add(row)
        db.session.flush()
        _log("mating.create", "Mating", row.id,
             details="تم التأكيد رغم تحذير قرابة وراثية" if relation else "")
        db.session.commit()

        from app.core.cycle_engine import record_cycle_event
        record_cycle_event(row.female, "mating", source_type="Mating", source_id=row.id, event_date=row.date)

        flash(_("تم تسجيل التقريع"), "success")
        return redirect(url_for("repro.matings_list"))

    # تعبئة مسبقة من رابط طلب التجاوز (بند إضافي 231) — صاحب الحلال
    # يفتح نفس الفورم من رسالة تيليجرام/المهمة، معبّى بنفس بيانات طلب
    # الدكتور، عشان يراجعها ويحفظ بضغطة وحدة بدل ما يعيد تعبئتها يدوياً.
    prefill_female_id = request.args.get("female_id", type=int)
    prefill_male_id = request.args.get("male_id", type=int)
    relation_warning = None
    form_data = None
    if prefill_female_id and prefill_male_id:
        from app.core import lineage_service
        relation_warning = lineage_service.relationship_warning(prefill_female_id, prefill_male_id)
        form_data = request.args
    return render_template(
        "repro/mating_form.html",
        females=_females(), males=_males(), barns=Barn.query.order_by(Barn.barn_name).all(),
        relation_warning=relation_warning, form_data=form_data,
        can_override=current_user.has_permission("repro.override_close_relation"),
    )


@repro_bp.route("/matings/suggest-females")
@login_required
@require_permission("repro.manage")
def matings_suggest_females():
    """اقتراح نعاج جاهزة للتقريع وغير قريبة للفحل المختار (بند إضافي
    231) — يُستدعى عبر JS من فورم تقريع جديد بمجرد ما يختار المستخدم
    الفحل، يرجّع JSON بس (مو صفحة كاملة)."""
    from flask import jsonify
    from app.core import lineage_service
    male_id = request.args.get("male_id", type=int)
    if not male_id:
        return jsonify([])
    return jsonify(lineage_service.suggest_unrelated_females(male_id))


# ---------- تشخيص الحمل ----------

@repro_bp.route("/pregnancies")
@login_required
@require_permission("repro.view")
def pregnancies_list():
    from datetime import timedelta
    from app.models import FarmSettings

    rows = Pregnancy.query.order_by(Pregnancy.date.desc()).all()
    gestation_days = FarmSettings.get().gestation_days
    expected_birth = {
        r.id: (r.mating.date if r.mating else r.date) + timedelta(days=gestation_days)
        for r in rows
    }
    return render_template(
        "repro/pregnancies_list.html", rows=rows, expected_birth=expected_birth, today=date.today().isoformat(),
    )


@repro_bp.route("/pregnancies/new", methods=["GET", "POST"])
@login_required
@require_permission("repro.manage")
def pregnancies_new():
    if request.method == "POST":
        row = Pregnancy(
            female_id=int(request.form["female_id"]),
            mating_id=request.form.get("mating_id") or None,
            date=date.fromisoformat(request.form["date"]),
            confirmed=bool(request.form.get("confirmed")),
            sonar_date=date.fromisoformat(request.form["sonar_date"]) if request.form.get("sonar_date") else None,
            embryo_count=int(request.form["embryo_count"]) if request.form.get("embryo_count") else None,
            notes=request.form.get("notes"),
        )
        db.session.add(row)
        db.session.flush()
        _log("pregnancy.create", "Pregnancy", row.id)
        db.session.commit()

        from app.core.cycle_engine import record_cycle_event
        record_cycle_event(row.female, "pregnancy", source_type="Pregnancy", source_id=row.id, event_date=row.date)

        flash(_("تم تسجيل تشخيص الحمل"), "success")
        return redirect(url_for("repro.pregnancies_list"))
    return render_template(
        "repro/pregnancy_form.html",
        females=_females(),
        matings=Mating.query.order_by(Mating.date.desc()).all(),
    )


@repro_bp.route("/pregnancies/<int:pregnancy_id>/abort", methods=["POST"])
@login_required
@require_permission("repro.manage")
def pregnancies_abort(pregnancy_id):
    """بروتوكول الإجهاض والعزل الطبي (بند إضافي 51) — عزل فوري + مهمة
    سحب عيّنات + مراقبة حرارة لبقية حظيرة الدفعة. انظر
    app/core/isolation_service.record_abortion للتفاصيل الكاملة."""
    from app.core.isolation_service import record_abortion

    pregnancy = Pregnancy.query.get_or_404(pregnancy_id)
    if pregnancy.outcome:
        flash(_("هذا الحمل مسجَّل له نتيجة إجهاض مسبقاً."), "error")
        return redirect(url_for("repro.pregnancies_list"))

    result = record_abortion(
        pregnancy=pregnancy,
        outcome_date=date.fromisoformat(request.form["outcome_date"]) if request.form.get("outcome_date") else date.today(),
        notes=request.form.get("notes"),
        actor_user_id=current_user.id,
    )
    isolation_msg = "وتم نقلها لحظيرة العزل الطبي" if result["isolated"] else "⚠️ ما فيه حظيرة عزل معرَّفة بالنظام — راجع الإعدادات"
    flash(
        f"تم تسجيل الإجهاض لـ{result['animal'].animal_no} {isolation_msg}. "
        f"تولّدت مهمة سحب عيّنات + {len(result['monitor_tasks'])} مهمة مراقبة حرارة لبقية الحظيرة.",
        "warning",
    )
    return redirect(url_for("repro.pregnancies_list"))


@repro_bp.route("/pregnancies/<int:pregnancy_id>/confirm", methods=["POST"])
@login_required
@require_permission("repro.manage")
def pregnancies_confirm(pregnancy_id):
    """تأكيد حمل كان مسجَّلاً "غير مؤكَّد" (بند إضافي 283) — قبل هذا
    البند ما فيه أي طريقة تأكّد بها حمل مشكوك فيه لاحقاً بعد ما تتضح
    نتيجته (سونار متأخر، أعراض واضحة...) غير حذف السجل وإعادة تسجيله
    من الصفر. `confirmed=False` كان يعني الحمل يبقى غايباً للأبد عن
    "كم رأس حوامل لدينا" (context_service.pregnant_summary تفحص
    confirmed=True حصراً) — تأكيده هنا هو اللي يُدخله فعلياً بالعدّاد."""
    pregnancy = Pregnancy.query.get_or_404(pregnancy_id)
    if pregnancy.confirmed:
        flash(_("هذا الحمل مؤكَّد أصلاً."), "error")
        return redirect(url_for("repro.pregnancies_list"))
    if pregnancy.outcome:
        flash(_("هذا الحمل مسجَّل له نتيجة إجهاض — ما ينفع يُأكَّد."), "error")
        return redirect(url_for("repro.pregnancies_list"))
    pregnancy.confirmed = True
    _log("pregnancy.confirm", "Pregnancy", pregnancy.id)
    db.session.commit()
    flash(_("تم تأكيد حمل %(no)s — صارت تظهر ضمن عدد الحوامل.", no=pregnancy.female.animal_no), "success")
    return redirect(url_for("repro.pregnancies_list"))


# ---------- فحص السونار (مستقل) ----------

@repro_bp.route("/sonar")
@login_required
@require_permission("repro.view")
def sonar_list():
    rows = SonarResult.query.order_by(SonarResult.exam_date.desc()).all()
    return render_template("repro/sonar_list.html", rows=rows)


@repro_bp.route("/sonar/new", methods=["GET", "POST"])
@login_required
@require_permission("repro.manage")
def sonar_new():
    if request.method == "POST":
        row = SonarResult(
            ewe_id=int(request.form["ewe_id"]),
            program_id=request.form.get("program_id") or None,
            exam_date=date.fromisoformat(request.form["exam_date"]),
            gestation_age_days=int(request.form["gestation_age_days"]) if request.form.get("gestation_age_days") else None,
            result=request.form.get("result"),
            embryo_count=int(request.form["embryo_count"]) if request.form.get("embryo_count") else None,
            heartbeat=bool(request.form.get("heartbeat")),
            doctor_id=request.form.get("doctor_id") or None,
            recheck_date=date.fromisoformat(request.form["recheck_date"]) if request.form.get("recheck_date") else None,
            notes=request.form.get("notes"),
        )
        db.session.add(row)
        db.session.flush()
        _log("sonar.create", "SonarResult", row.id)
        db.session.commit()

        from app.core.cycle_engine import record_cycle_event
        record_cycle_event(row.ewe, "sonar", source_type="SonarResult", source_id=row.id, event_date=row.exam_date)

        # بند إضافي 100 — قبل هذا، `recheck_date` كان يُدخَل بالفورم
        # ويُخزَّن بدون أي أثر فعلي: ما فيه أي مهمة أو تذكير يُنشأ منه،
        # فيبقى "بيانات ميتة" لو الدكتور ما راجع سجل السونار بنفسه صدفة.
        if row.recheck_date:
            from app.team import task_service
            task_service.create_suggested_task(
                title=f"📟 إعادة فحص سونار — {row.ewe.animal_no}",
                task_type="sonar_recheck", animal_id=row.ewe_id, barn_id=row.ewe.barn_id,
                due_date=row.recheck_date, source_type="SonarResult", source_id=row.id,
                notes=f"نتيجة الفحص السابق ({row.exam_date}): {row.result or 'غير محدد'}.",
            )

        flash(_("تم تسجيل فحص السونار"), "success")
        return redirect(url_for("repro.sonar_list"))
    return render_template(
        "repro/sonar_form.html",
        females=_females(),
        doctors=Doctor.query.filter_by(status="active").all(),
        programs=TwinEstrusProgram.query.filter_by(status="active").all(),
    )


# ---------- برامج الشياع التوأمي ----------

@repro_bp.route("/programs")
@login_required
@require_permission("repro.view")
def programs_list():
    rows = TwinEstrusProgram.query.order_by(TwinEstrusProgram.start_date.desc()).all()
    return render_template("repro/programs_list.html", rows=rows)


@repro_bp.route("/programs/new", methods=["GET", "POST"])
@login_required
@require_permission("repro.manage")
def programs_new():
    if request.method == "POST":
        row = TwinEstrusProgram(
            ewe_id=int(request.form["ewe_id"]),
            protocol_name=request.form.get("protocol_name"),
            supervising_doctor_id=request.form.get("supervising_doctor_id") or None,
            ram_id=request.form.get("ram_id") or None,
            ram_note=request.form.get("ram_note"),
            start_date=date.fromisoformat(request.form["start_date"]),
            device_insert_planned_at=date.fromisoformat(request.form["device_insert_planned_at"]) if request.form.get("device_insert_planned_at") else None,
            device_remove_planned_at=date.fromisoformat(request.form["device_remove_planned_at"]) if request.form.get("device_remove_planned_at") else None,
            expected_estrus_start=date.fromisoformat(request.form["expected_estrus_start"]) if request.form.get("expected_estrus_start") else None,
            expected_estrus_end=date.fromisoformat(request.form["expected_estrus_end"]) if request.form.get("expected_estrus_end") else None,
            mating_window_start=date.fromisoformat(request.form["mating_window_start"]) if request.form.get("mating_window_start") else None,
            mating_window_end=date.fromisoformat(request.form["mating_window_end"]) if request.form.get("mating_window_end") else None,
            notes=request.form.get("notes"),
        )
        db.session.add(row)
        db.session.flush()
        _log("twin_estrus_program.create", "TwinEstrusProgram", row.id)
        db.session.commit()
        flash(_("تم إنشاء برنامج الشياع التوأمي"), "success")
        return redirect(url_for("repro.program_detail", program_id=row.id))
    return render_template(
        "repro/program_form.html",
        females=_females(), males=_males(),
        doctors=Doctor.query.filter_by(status="active").all(),
    )


@repro_bp.route("/programs/<int:program_id>")
@login_required
@require_permission("repro.view")
def program_detail(program_id):
    program = TwinEstrusProgram.query.get_or_404(program_id)
    return render_template("repro/program_detail.html", p=program)


@repro_bp.route("/programs/<int:program_id>/attempts/new", methods=["GET", "POST"])
@login_required
@require_permission("repro.manage")
def program_attempt_new(program_id):
    program = TwinEstrusProgram.query.get_or_404(program_id)
    if request.method == "POST":
        row = TwinEstrusAttempt(
            program_id=program.id,
            mating_date=date.fromisoformat(request.form["mating_date"]),
            ram_id=request.form.get("ram_id") or None,
            ram_note=request.form.get("ram_note"),
            confirmation_status=request.form.get("confirmation_status") or "pending",
            observed_by=request.form.get("observed_by"),
            notes=request.form.get("notes"),
        )
        db.session.add(row)
        db.session.flush()
        _log("twin_estrus_attempt.create", "TwinEstrusAttempt", row.id, f"program={program.id}")
        db.session.commit()

        from app.core.cycle_engine import record_cycle_event
        record_cycle_event(program.ewe, "twin_estrus_attempt", source_type="TwinEstrusAttempt",
                            source_id=row.id, event_date=row.mating_date)

        flash(_("تم تسجيل محاولة التقريع"), "success")
        return redirect(url_for("repro.program_detail", program_id=program.id))
    return render_template("repro/attempt_form.html", program=program, males=_males())


@repro_bp.route("/programs/<int:program_id>/devices/new", methods=["GET", "POST"])
@login_required
@require_permission("repro.manage")
def program_device_new(program_id):
    program = TwinEstrusProgram.query.get_or_404(program_id)
    if request.method == "POST":
        row = ReproDevice(
            program_id=program.id,
            device_type=request.form["device_type"],
            trade_name=request.form.get("trade_name"),
            inserted_at=date.fromisoformat(request.form["inserted_at"]),
            inserted_by=request.form.get("inserted_by"),
            planned_remove_at=date.fromisoformat(request.form["planned_remove_at"]) if request.form.get("planned_remove_at") else None,
            notes=request.form.get("notes"),
        )
        db.session.add(row)
        db.session.flush()
        _log("repro_device.create", "ReproDevice", row.id, f"program={program.id}")
        db.session.commit()

        from app.core.cycle_engine import record_cycle_event
        record_cycle_event(program.ewe, "repro_device", source_type="ReproDevice",
                            source_id=row.id, event_date=row.inserted_at)

        flash(_("تم تسجيل جهاز التكاثر"), "success")
        return redirect(url_for("repro.program_detail", program_id=program.id))
    return render_template("repro/device_form.html", program=program)


@repro_bp.route("/programs/<int:program_id>/devices/<int:device_id>/remove", methods=["POST"])
@login_required
@require_permission("repro.manage")
def program_device_remove(program_id, device_id):
    device = ReproDevice.query.filter_by(id=device_id, program_id=program_id).first_or_404()
    device.actual_remove_at = date.fromisoformat(request.form["actual_remove_at"]) if request.form.get("actual_remove_at") else date.today()
    device.early_loss = bool(request.form.get("early_loss"))
    _log("repro_device.remove", "ReproDevice", device.id, f"program={program_id}")
    db.session.commit()
    flash(_("تم تسجيل إزالة الجهاز"), "success")
    return redirect(url_for("repro.program_detail", program_id=program_id))


@repro_bp.route("/programs/<int:program_id>/injections/new", methods=["GET", "POST"])
@login_required
@require_permission("repro.manage")
def program_injection_new(program_id):
    program = TwinEstrusProgram.query.get_or_404(program_id)
    if request.method == "POST":
        row = HormoneInjection(
            program_id=program.id,
            hormone_name=request.form["hormone_name"],
            dose_value=float(request.form["dose_value"]) if request.form.get("dose_value") else None,
            dose_unit=request.form.get("dose_unit"),
            route=request.form.get("route"),
            planned_at=date.fromisoformat(request.form["planned_at"]) if request.form.get("planned_at") else None,
            actual_at=date.fromisoformat(request.form["actual_at"]) if request.form.get("actual_at") else None,
            given_by=request.form.get("given_by"),
            notes=request.form.get("notes"),
        )
        db.session.add(row)
        db.session.flush()
        _log("hormone_injection.create", "HormoneInjection", row.id, f"program={program.id}")
        db.session.commit()

        from app.core.cycle_engine import record_cycle_event
        record_cycle_event(program.ewe, "hormone_injection", source_type="HormoneInjection",
                            source_id=row.id, event_date=row.actual_at or row.planned_at or date.today())

        flash(_("تم تسجيل الحقنة الهرمونية"), "success")
        return redirect(url_for("repro.program_detail", program_id=program.id))
    return render_template("repro/injection_form.html", program=program)


@repro_bp.route("/programs/<int:program_id>/status", methods=["POST"])
@login_required
@require_permission("repro.manage")
def program_set_status(program_id):
    program = TwinEstrusProgram.query.get_or_404(program_id)
    program.status = request.form["status"]
    _log("twin_estrus_program.status", "TwinEstrusProgram", program.id, program.status)
    db.session.commit()
    flash(_("تم تحديث حالة البرنامج"), "success")
    return redirect(url_for("repro.program_detail", program_id=program.id))
