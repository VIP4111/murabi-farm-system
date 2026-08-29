from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.assistant import assistant_bp
from app.assistant import nlu_service as svc
from app.assistant import farm_note_service, draft_action_service
from app.auth.decorators import require_permission, rate_limited
from app.extensions import db
from app.models import AssistantMessage, FarmNote, Barn, Animal, AssistantDraftAction

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


# ============================================================
# بند إضافي 299 — المرحلة ٤ (الأخيرة): الإدخال الذكي بالنص/الصوت.
# ============================================================

@assistant_bp.route("/drafts")
@login_required
@require_permission("assistant.draft_actions.confirm")
def drafts_list():
    # خط دفاع ثانٍ (كسول، عند فتح الشاشة) بجانب الـCron الفعلي —
    # نفس نمط `catch_up_daily_tasks_before_request` بالضبط (بند 89).
    draft_action_service.expire_stale_drafts()
    pending = (AssistantDraftAction.query.filter_by(status="pending")
               .order_by(AssistantDraftAction.created_at.asc()).all())
    history = (AssistantDraftAction.query.filter(AssistantDraftAction.status != "pending")
               .order_by(AssistantDraftAction.created_at.desc()).limit(30).all())
    return render_template("assistant/drafts_list.html", pending=pending, history=history,
                            gemini_configured=svc.llm_bridge.is_gemini_configured())


@assistant_bp.route("/drafts/new-text", methods=["POST"])
@login_required
@require_permission("assistant.draft_actions.confirm")
@rate_limited("draft_action_propose", max_calls=20, window_seconds=300)
def drafts_new_text():
    raw_text = request.form.get("raw_text", "").strip()
    if not raw_text:
        flash("اكتب وصف الحدث أولاً.", "error")
        return redirect(url_for("assistant.drafts_list"))
    draft_action_service.propose_from_text(raw_text, created_by=current_user)
    flash("تمت معالجة النص — راجع النتيجة أدناه.", "success")
    return redirect(url_for("assistant.drafts_list"))


@assistant_bp.route("/drafts/new-voice", methods=["POST"])
@login_required
@require_permission("assistant.draft_actions.confirm")
@rate_limited("draft_action_propose", max_calls=20, window_seconds=300)
def drafts_new_voice():
    audio_file = request.files.get("audio")
    if not audio_file or not audio_file.filename:
        flash("لازم ترفع مقطع صوتي.", "error")
        return redirect(url_for("assistant.drafts_list"))
    draft_action_service.propose_from_audio(
        audio_file.read(), audio_file.mimetype or "audio/mpeg", created_by=current_user,
    )
    flash("تمت معالجة المقطع الصوتي — راجع النتيجة أدناه.", "success")
    return redirect(url_for("assistant.drafts_list"))


@assistant_bp.route("/drafts/<int:draft_id>/confirm", methods=["POST"])
@login_required
@require_permission("assistant.draft_actions.confirm")
def drafts_confirm(draft_id):
    draft = AssistantDraftAction.query.get_or_404(draft_id)
    try:
        draft_action_service.confirm_draft(draft, actor=current_user)
        flash("تم اعتماد المسودة وتنفيذها فعلياً.", "success")
    except ValueError as e:
        flash(f"تعذّر التنفيذ: {e}", "error")
    return redirect(url_for("assistant.drafts_list"))


@assistant_bp.route("/drafts/<int:draft_id>/reject", methods=["POST"])
@login_required
@require_permission("assistant.draft_actions.confirm")
def drafts_reject(draft_id):
    draft = AssistantDraftAction.query.get_or_404(draft_id)
    try:
        draft_action_service.reject_draft(draft, actor=current_user)
        flash("تم رفض المسودة.", "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("assistant.drafts_list"))
