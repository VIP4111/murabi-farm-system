from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.assistant import assistant_bp
from app.assistant import nlu_service as svc
from app.assistant import farm_note_service
from app.auth.decorators import require_permission, rate_limited
from app.extensions import db
from app.models import AssistantMessage, FarmNote, Barn, Animal

HISTORY_LIMIT = 50


@assistant_bp.route("/")
@login_required
@require_permission("assistant.use")
def chat():
    rows = (
        AssistantMessage.query.filter_by(user_id=current_user.id)
        .order_by(AssistantMessage.created_at.desc()).limit(HISTORY_LIMIT).all()
    )
    return render_template("assistant/chat.html", messages=list(reversed(rows)))


@assistant_bp.route("/send", methods=["POST"])
@login_required
@require_permission("assistant.use")
@rate_limited("assistant_send", max_calls=30, window_seconds=300)
def send():
    message_text = (request.get_json(silent=True) or {}).get("message", "").strip() if request.is_json \
        else request.form.get("message", "").strip()
    if not message_text:
        if request.is_json:
            return jsonify({"error": "الرسالة فاضية"}), 400
        flash("اكتب سؤالك أولاً", "error")
        return redirect(url_for("assistant.chat"))

    reply = svc.ask_and_record(current_user, message_text)

    if request.is_json:
        return jsonify({
            "reply": reply.content,
            "intent_code": reply.intent_code,
            "answered_by": reply.answered_by,
            "created_at": reply.created_at.isoformat(),
        })
    return redirect(url_for("assistant.chat"))


@assistant_bp.route("/clear", methods=["POST"])
@login_required
@require_permission("assistant.use")
def clear():
    AssistantMessage.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash("تم مسح المحادثة", "success")
    return redirect(url_for("assistant.chat"))


@assistant_bp.route("/farm-notes")
@login_required
@require_permission("farm_notes.manage")
def farm_notes_list():
    """دفتر ملاحظات المزرعة (بند إضافي 298) — الملاحظات المكتوبة هنا
    تُغذّي ذاكرة المساعد الذكي التراكمية (RAG، `search_farm_notes`)."""
    notes = FarmNote.query.order_by(FarmNote.created_at.desc()).limit(100).all()
    barns = Barn.query.order_by(Barn.barn_name).all()
    return render_template("assistant/farm_notes_list.html", notes=notes, barns=barns,
                            gemini_configured=svc.llm_bridge.is_gemini_configured())


@assistant_bp.route("/farm-notes/new", methods=["POST"])
@login_required
@require_permission("farm_notes.manage")
def farm_notes_new():
    body = request.form.get("body", "").strip()
    if not body:
        flash("لازم تكتب نص الملاحظة.", "error")
        return redirect(url_for("assistant.farm_notes_list"))

    barn_id = request.form.get("barn_id", type=int) or None
    animal_no = request.form.get("animal_no", "").strip()
    animal_id = None
    if animal_no:
        animal = Animal.query.filter_by(animal_no=animal_no).first()
        if not animal:
            flash(f"ما فيه حيوان برقم \"{animal_no}\".", "error")
            return redirect(url_for("assistant.farm_notes_list"))
        animal_id = animal.id

    farm_note_service.create_note(
        body=body, created_by=current_user,
        title=request.form.get("title", "").strip() or None,
        tag=request.form.get("tag", "").strip() or None,
        barn_id=barn_id, animal_id=animal_id,
    )
    flash("تمت إضافة الملاحظة.", "success")
    return redirect(url_for("assistant.farm_notes_list"))
