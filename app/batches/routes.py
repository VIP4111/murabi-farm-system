from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_babel import gettext as _
from flask_login import login_required, current_user

from app.batches import batches_bp
from app.auth.decorators import require_permission
from app.core import batch_service
from app.models import AnimalBatch, Animal, Barn, AnimalColor, Breed

BATCH_ENTRY_SLOTS = range(20)


@batches_bp.route("/")
@login_required
@require_permission("animals.view")
def batches_list():
    batches = AnimalBatch.query.order_by(AnimalBatch.created_at.desc()).all()
    return render_template("batches/batches_list.html", batches=batches)


@batches_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_permission("animals.manage")
def batches_new():
    if request.method == "POST":
        entries = []
        for i in BATCH_ENTRY_SLOTS:
            gender = request.form.get(f"gender_{i}")
            if not gender:
                continue
            entries.append({
                "animal_no": request.form.get(f"animal_no_{i}") or None,
                "gender": gender,
                "color": request.form.get(f"color_{i}") or None,
                "weight": float(request.form[f"weight_{i}"]) if request.form.get(f"weight_{i}") else None,
                "price": float(request.form[f"price_{i}"]) if request.form.get(f"price_{i}") else None,
                "breed": request.form.get(f"breed_{i}") or None,
            })
        if not entries:
            flash(_("لازم رأس واحدة على الأقل بالدفعة — حدد الجنس على الأقل لكل صف."), "error")
            return redirect(url_for("batches.batches_new"))
        try:
            batch = batch_service.create_batch(
                source=request.form["source"],
                arrival_date=date.fromisoformat(request.form["arrival_date"]),
                notes=request.form.get("notes") or None,
                actor_user_id=current_user.id, entries=entries,
            )
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("batches.batches_new"))
        flash(f'تم تسجيل الدفعة "{batch.batch_no}" ({len(entries)} رأس) وعزلها بحظيرة الحجر الصحي.', "success")
        return redirect(url_for("batches.batch_detail", batch_id=batch.id))
    # بند إضافي 291 — طلبك الصريح "ابدأ" بعد ما لقينا فجوة حقيقية:
    # هذي الشاشة كانت تقرأ قائمة سلالات ثابتة بالكود (`Animal.BREEDS`
    # القديمة)، منفصلة تماماً عن جدول `Breed` الحقيقي اللي تضيف له
    # سلالات جديدة من شاشة "+ حيوان جديد" — أي سلالة تضيفها هناك ما
    # كانت تظهر هنا إطلاقاً. صارت تقرأ من نفس المصدر الحقيقي الوحيد.
    Breed.seed_defaults()
    return render_template(
        "batches/batch_form.html", entry_slots=BATCH_ENTRY_SLOTS,
        sources=AnimalBatch.SOURCES, breeds=Breed.query.order_by(Breed.name).all(),
        today=date.today().isoformat(),
        colors=AnimalColor.query.order_by(AnimalColor.name).all(),
    )


@batches_bp.route("/<int:batch_id>")
@login_required
@require_permission("animals.view")
def batch_detail(batch_id):
    batch = AnimalBatch.query.get_or_404(batch_id)
    permanent_barns = Barn.query.filter(Barn.barn_type != "عزل").order_by(Barn.barn_name).all()
    return render_template(
        "batches/batch_detail.html", batch=batch, permanent_barns=permanent_barns,
        STAGE_QUARANTINE=AnimalBatch.STAGE_QUARANTINE, STAGE_TAGGING=AnimalBatch.STAGE_TAGGING,
        STAGE_DISTRIBUTED=AnimalBatch.STAGE_DISTRIBUTED,
    )


@batches_bp.route("/<int:batch_id>/advance", methods=["POST"])
@login_required
@require_permission("gates.approve")
def batch_advance(batch_id):
    batch = AnimalBatch.query.get_or_404(batch_id)
    try:
        created = batch_service.advance_batch_stage(batch, actor_user_id=current_user.id)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("batches.batch_detail", batch_id=batch.id))
    flash(_("تقدّمت الدفعة لمرحلة الترقيم/الفحص — تولّدت %(n)s مهمة فحص فردي.", n=len(created)), "success")
    return redirect(url_for("batches.batch_detail", batch_id=batch.id))


@batches_bp.route("/<int:batch_id>/distribute", methods=["POST"])
@login_required
@require_permission("gates.approve")
def batch_distribute(batch_id):
    batch = AnimalBatch.query.get_or_404(batch_id)
    assignments = {}
    for animal in batch.animals:
        barn_id = request.form.get(f"barn_id_{animal.id}")
        if barn_id:
            assignments[animal.id] = int(barn_id)
    try:
        created = batch_service.distribute_batch(batch, assignments=assignments, actor_user_id=current_user.id)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("batches.batch_detail", batch_id=batch.id))
    flash(_("تم توزيع %(n)s رأس على حظائرها الدائمة.", n=len(created)), "success")
    return redirect(url_for("batches.batch_detail", batch_id=batch.id))


@batches_bp.route("/animals/<int:animal_id>/hold", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animal_hold(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    try:
        batch_service.hold_animal(animal, reason=request.form.get("reason"), actor_user_id=current_user.id)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("batches.batch_detail", batch_id=animal.batch_id))
    flash(_("استُبعدت %(no)s من التقدّم الجماعي التالي.", no=animal.animal_no), "success")
    return redirect(url_for("batches.batch_detail", batch_id=animal.batch_id))


@batches_bp.route("/animals/<int:animal_id>/release", methods=["POST"])
@login_required
@require_permission("animals.manage")
def animal_release(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    try:
        batch_service.release_hold(animal, actor_user_id=current_user.id)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("batches.batch_detail", batch_id=animal.batch_id))
    flash(_("تم تحرير استبعاد %(no)s.", no=animal.animal_no), "success")
    return redirect(url_for("batches.batch_detail", batch_id=animal.batch_id))


@batches_bp.route("/animals/<int:animal_id>/catch-up", methods=["POST"])
@login_required
@require_permission("gates.approve")
def animal_catch_up(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    batch = AnimalBatch.query.get_or_404(animal.batch_id) if animal.batch_id else None
    if not batch:
        flash(_("هذا الرأس مو ضمن أي دفعة."), "error")
        return redirect(url_for("core.animal_detail", animal_id=animal.id))
    barn_id = request.form.get("barn_id")
    try:
        batch_service.advance_single_animal(
            batch, animal, actor_user_id=current_user.id,
            barn_id=int(barn_id) if barn_id else None,
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("batches.batch_detail", batch_id=batch.id))
    flash(_("لحقت %(no)s بمرحلة الدفعة الحالية.", no=animal.animal_no), "success")
    return redirect(url_for("batches.batch_detail", batch_id=batch.id))
