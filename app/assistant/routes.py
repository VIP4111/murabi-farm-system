from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_babel import gettext as _
from flask_login import login_required, current_user

from app.assistant import assistant_bp
from app.assistant import nlu_service as svc
from app.assistant import farm_note_service, draft_action_service
from app.auth.decorators import require_permission, rate_limited
from app.extensions import db
from app.models import AssistantMessage, FarmNote, Barn, Animal, AssistantDraftAction, User

HISTORY_LIMIT = 50


# بند إضافي 318 — طلبك الصريح: "أرفض كثرة الشاشات... نريد البدء فوراً
# في إعادة هيكلة وتجميع الشاشات (UX Consolidation)". دمجنا 3 شاشات
# مستقلة (محادثة، دفتر ملاحظات، إدخال ذكي) بصفحة واحدة بتبويبات —
# `chat()` صارت تجمّع بيانات الثلاثة معاً، والراوتات القديمة تحوّل
# لنفس الصفحة (بدون كسر أي رابط قديم محفوظ). صفر تغيير على منطق
# الخدمات نفسها (`farm_note_service`/`draft_action_service`) — هذا
# دمج عرض بس.
@assistant_bp.route("/")
@login_required
@require_permission("assistant.use")
def chat():
    messages = list(reversed(
        AssistantMessage.query.filter_by(user_id=current_user.id)
        .order_by(AssistantMessage.created_at.desc()).limit(HISTORY_LIMIT).all()
    ))

    notes = barns = pending = history = assignable_users = None
    if current_user.has_permission("farm_notes.manage"):
        notes = FarmNote.query.order_by(FarmNote.created_at.desc()).limit(100).all()
        barns = Barn.query.order_by(Barn.barn_name).all()

    if current_user.has_permission("assistant.draft_actions.confirm"):
        # خط دفاع ثانٍ (كسول، عند فتح الشاشة) بجانب الـCron الفعلي —
        # نفس نمط `catch_up_daily_tasks_before_request` بالضبط (بند 89).
        draft_action_service.expire_stale_drafts()
        pending_q = AssistantDraftAction.query.filter_by(status="pending")
        history_q = AssistantDraftAction.query.filter(AssistantDraftAction.status != "pending")
        # بند إضافي 315 — عامل بدون animals.view يشوف مسوداته هو بس.
        if not current_user.has_permission("animals.view"):
            pending_q = pending_q.filter_by(created_by_id=current_user.id)
            history_q = history_q.filter_by(created_by_id=current_user.id)
        pending = pending_q.order_by(AssistantDraftAction.created_at.asc()).all()
        history = history_q.order_by(AssistantDraftAction.created_at.desc()).limit(30).all()
        assignable_users = User.query.filter_by(is_active_account=True).order_by(User.name).all()

    active_tab = request.args.get("tab", "chat")
    return render_template(
        "assistant/chat.html", messages=messages, active_tab=active_tab,
        notes=notes, barns=barns, pending=pending, history=history, assignable_users=assignable_users,
        gemini_configured=svc.llm_bridge.is_gemini_configured(),
    )


@assistant_bp.route("/send", methods=["POST"])
@login_required
@require_permission("assistant.use")
@rate_limited("assistant_send", max_calls=30, window_seconds=300)
def send():
    image_file = request.files.get("image") if not request.is_json else None
    message_text = (request.get_json(silent=True) or {}).get("message", "").strip() if request.is_json \
        else request.form.get("message", "").strip()

    if not message_text and not (image_file and image_file.filename):
        if request.is_json:
            return jsonify({"error": _("الرسالة فاضية")}), 400
        flash(_("اكتب سؤالك أولاً"), "error")
        return redirect(url_for("assistant.chat"))

    if image_file and image_file.filename:
        # بند إضافي 305 — صورة مرفقة: نحفظها (رابط دائم للعرض بالسجل)
        # ونحلّل البايتات الخام مباشرة (بدون تحميل الرابط مرة ثانية).
        from app.core.cloud_storage_service import save_upload
        ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "heif"}
        MAX_IMAGE_BYTES = 8 * 1024 * 1024
        image_file.stream.seek(0)
        image_bytes = image_file.stream.read()
        image_file.stream.seek(0)
        image_url = save_upload(image_file, subfolder="assistant_chat",
                                 allowed_extensions=ALLOWED_IMAGE_EXTENSIONS, max_bytes=MAX_IMAGE_BYTES)
        if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            return jsonify({"error": _("الصورة غير صالحة أو حجمها كبير جداً (الحد 8 ميجا)")}), 400
        reply = svc.ask_and_record_with_image(
            current_user, message_text, image_bytes, image_file.mimetype or "image/jpeg", image_url,
        )
    else:
        reply = svc.ask_and_record(current_user, message_text)

    if request.is_json or image_file:
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
    flash(_("تم مسح المحادثة"), "success")
    return redirect(url_for("assistant.chat"))


# ============================================================
# دفتر ملاحظات المزرعة (بند إضافي 298) — صار تبويب داخل `chat()`
# (بند إضافي 318). الراوت القديم `/farm-notes` يبقى يشتغل كتحويل بس،
# عشان أي رابط محفوظ قديم ما ينكسر.
# ============================================================

@assistant_bp.route("/farm-notes")
@login_required
@require_permission("farm_notes.manage")
def farm_notes_list():
    return redirect(url_for("assistant.chat", tab="notes"))


@assistant_bp.route("/farm-notes/new", methods=["POST"])
@login_required
@require_permission("farm_notes.manage")
@rate_limited("farm_notes_new", max_calls=20, window_seconds=300)
def farm_notes_new():
    body = request.form.get("body", "").strip()
    if not body:
        flash(_("لازم تكتب نص الملاحظة."), "error")
        return redirect(url_for("assistant.chat", tab="notes"))

    barn_id = request.form.get("barn_id", type=int) or None
    animal_no = request.form.get("animal_no", "").strip()
    animal_id = None
    if animal_no:
        animal = Animal.query.filter_by(animal_no=animal_no).first()
        if not animal:
            flash(_("ما فيه حيوان برقم \"%(no)s\".", no=animal_no), "error")
            return redirect(url_for("assistant.chat", tab="notes"))
        animal_id = animal.id

    farm_note_service.create_note(
        body=body, created_by=current_user,
        title=request.form.get("title", "").strip() or None,
        tag=request.form.get("tag", "").strip() or None,
        barn_id=barn_id, animal_id=animal_id,
    )
    flash(_("تمت إضافة الملاحظة."), "success")
    return redirect(url_for("assistant.chat", tab="notes"))


# ============================================================
# بند إضافي 299 — الإدخال الذكي بالنص/الصوت. صار تبويب داخل `chat()`
# (بند إضافي 318). الراوت القديم `/drafts` يبقى تحويلاً بس.
# ============================================================

@assistant_bp.route("/drafts")
@login_required
@require_permission("assistant.draft_actions.confirm")
def drafts_list():
    return redirect(url_for("assistant.chat", tab="drafts"))


@assistant_bp.route("/drafts/new-text", methods=["POST"])
@login_required
@require_permission("assistant.draft_actions.confirm")
@rate_limited("draft_action_propose", max_calls=20, window_seconds=300)
def drafts_new_text():
    raw_text = request.form.get("raw_text", "").strip()
    if not raw_text:
        flash(_("اكتب وصف الحدث أولاً."), "error")
        return redirect(url_for("assistant.chat", tab="drafts"))
    draft_action_service.propose_from_text(raw_text, created_by=current_user)
    flash(_("تمت معالجة النص — راجع النتيجة أدناه."), "success")
    return redirect(url_for("assistant.chat", tab="drafts"))


@assistant_bp.route("/drafts/new-voice", methods=["POST"])
@login_required
@require_permission("assistant.draft_actions.confirm")
@rate_limited("draft_action_propose", max_calls=20, window_seconds=300)
def drafts_new_voice():
    audio_file = request.files.get("audio")
    if not audio_file or not audio_file.filename:
        flash(_("لازم ترفع مقطع صوتي."), "error")
        return redirect(url_for("assistant.chat", tab="drafts"))

    # بند إضافي 312 — نفس فحص مسار الصورة (بند 305): نقرأ البايتات
    # الخام أولاً للتحليل، ثم نحفظ رابطاً دائماً للمقطع نفسه (نفس
    # `report_service.save_voice_note` الموجودة أصلاً لملاحظات
    # البلاغات الصوتية) عشان تقدر ترجع تسمعه لاحقاً.
    from app.team.report_service import save_voice_note
    audio_file.stream.seek(0)
    audio_bytes = audio_file.stream.read()
    audio_file.stream.seek(0)
    audio_url = save_voice_note(audio_file)

    draft_action_service.propose_from_audio(
        audio_bytes, audio_file.mimetype or "audio/mpeg", created_by=current_user, audio_url=audio_url,
    )
    flash(_("تمت معالجة المقطع الصوتي — راجع النتيجة أدناه."), "success")
    return redirect(url_for("assistant.chat", tab="drafts"))


@assistant_bp.route("/drafts/<int:draft_id>/confirm", methods=["POST"])
@login_required
@require_permission("assistant.draft_actions.confirm")
def drafts_confirm(draft_id):
    draft = AssistantDraftAction.query.get_or_404(draft_id)
    # بند إضافي 316 — لازم يجي من قائمة منسدلة صريحة بواجهة الاعتماد
    # (تحسينك: "أخاف يحول أو يتخذ اتجاه غير مرغوب فيه لو ما اخترت
    # بنفسي") — الحقل فاضي لغير مسودات assign_task، بلا أي أثر.
    assignee_id = request.form.get("assignee_id", type=int)
    try:
        draft_action_service.confirm_draft(draft, actor=current_user, assignee_id=assignee_id)
        flash(_("تم اعتماد المسودة وتنفيذها فعلياً."), "success")
    except PermissionError as e:
        flash(str(e), "error")
    except ValueError as e:
        flash(_("تعذّر التنفيذ: %(err)s", err=e), "error")
    return redirect(url_for("assistant.chat", tab="drafts"))


@assistant_bp.route("/drafts/<int:draft_id>/reject", methods=["POST"])
@login_required
@require_permission("assistant.draft_actions.confirm")
def drafts_reject(draft_id):
    draft = AssistantDraftAction.query.get_or_404(draft_id)
    try:
        draft_action_service.reject_draft(draft, actor=current_user)
        flash(_("تم رفض المسودة."), "success")
    except ValueError as e:
        flash(str(e), "error")
    return redirect(url_for("assistant.chat", tab="drafts"))
