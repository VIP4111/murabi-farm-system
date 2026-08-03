from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.assistant import assistant_bp
from app.assistant import nlu_service as svc
from app.auth.decorators import require_permission, rate_limited
from app.extensions import db
from app.models import AssistantMessage

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
