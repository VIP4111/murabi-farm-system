"""
محرك دورة حياة البلاغ — نقطة الدخول الموحّدة لكل انتقال حالة، بدل ما تتفرّق
منطق الانتقالات بين القوالب والراوتات. كل دالة هنا تتحقق من صلاحية الفاعل
قبل التنفيذ وترفع ReportPermissionError لو ما يملك الحق، حتى لو كان معه
صلاحية `reports.manage` العامة — لأن بعض الانتقالات (الإغلاق تحديداً) حصرية
لنفس الشخص اللي استلم البلاغ (manager_id)، مو لأي حامل صلاحية.
"""
import os
import uuid
from datetime import datetime, timezone
from flask import current_app
from app.extensions import db
from app.models import Report, AuditLog


def _now():
    return datetime.now(timezone.utc)


ALLOWED_AUDIO_EXTENSIONS = {"webm", "mp3", "wav", "m4a", "ogg", "aac"}
MAX_AUDIO_BYTES = 8 * 1024 * 1024  # 8MB — كافي لملاحظة صوتية قصيرة بالميدان


def save_voice_note(file_storage) -> str | None:
    """
    حفظ ملاحظة صوتية مرفوعة من نموذج البلاغ (بند 28) — تخزين محلي بسيط
    (`app/static/uploads/audio/`) نفس فلسفة المشروع الحالية (لا سحابة
    منفصلة بعد). ترجع None بصمت لأي إدخال غير صالح (بدون ملف، امتداد
    غير مدعوم، حجم صفر أو أكبر من الحد) بدل ما ترفع استثناء — تسجيل
    الملاحظة الصوتية اختياري أصلاً، فشلها ما يوقف رفع البلاغ نفسه.
    """
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        return None
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0 or size > MAX_AUDIO_BYTES:
        return None

    upload_dir = os.path.join(current_app.config["UPLOAD_DIR"], "audio")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(upload_dir, filename))
    return f"/uploads/audio/{filename}"


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "heif"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8MB — نفس حد الملاحظة الصوتية


def save_evidence_image(file_storage) -> str | None:
    """
    حفظ صورة دليل مرفوعة من نموذج البلاغ عن طريق الكاميرا أو معرض الصور
    (بدل رابط نصي كان يتطلب من المستخدم رفع الصورة لمكان خارجي بنفسه أولاً).
    نفس فلسفة `save_voice_note` بالضبط: تخزين محلي بسيط، ترجع None بصمت
    لأي إدخال غير صالح بدل رفع استثناء، لأن الصورة اختيارية أصلاً.
    """
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0 or size > MAX_IMAGE_BYTES:
        return None

    upload_dir = os.path.join(current_app.config["UPLOAD_DIR"], "images")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(upload_dir, filename))
    return f"/uploads/images/{filename}"


class ReportPermissionError(Exception):
    """يُرفع لما يحاول مستخدم يسوي انتقال حالة ما يملك الحق فيه."""


class ReportStateError(Exception):
    """يُرفع لما يُطلب انتقال ما ينطبق على حالة البلاغ الحالية."""


def submit_report(*, reporter, description, report_type=None, animal_id=None, barn_id=None,
                   evidence_image_url=None, evidence_audio_url=None) -> Report:
    report = Report(
        reporter_id=reporter.id, description=description, report_type=report_type,
        animal_id=animal_id, barn_id=barn_id,
        evidence_image_url=evidence_image_url, evidence_audio_url=evidence_audio_url,
        status="new",
    )
    db.session.add(report)
    db.session.flush()
    db.session.add(AuditLog(actor_user_id=reporter.id, action="report.submit",
                             entity_type="Report", entity_id=report.id))
    db.session.commit()
    return report


def _require_manage(actor):
    if not actor.has_permission("reports.manage"):
        raise ReportPermissionError("ما تملك صلاحية إدارة البلاغات.")


def accept_report(report: Report, *, actor) -> Report:
    _require_manage(actor)
    if report.status != "new":
        raise ReportStateError("البلاغ مو بحالة \"جديد\".")
    report.status = "accepted"
    report.manager_id = actor.id
    report.accepted_at = _now()
    db.session.add(AuditLog(actor_user_id=actor.id, action="report.accept",
                             entity_type="Report", entity_id=report.id))
    db.session.commit()
    return report


def postpone_report(report: Report, *, actor, reason: str) -> Report:
    _require_manage(actor)
    if report.status not in ("new", "accepted"):
        raise ReportStateError("لا يمكن تأجيل بلاغ بهذي الحالة.")
    if report.manager_id and report.manager_id != actor.id:
        raise ReportPermissionError("هذا البلاغ مستلم من دكتور ثاني.")
    report.status = "postponed"
    report.postpone_reason = reason
    db.session.add(AuditLog(actor_user_id=actor.id, action="report.postpone",
                             entity_type="Report", entity_id=report.id, details=reason))
    db.session.commit()
    return report


def resume_postponed_report(report: Report, *, actor) -> Report:
    """يرجّع بلاغ مؤجَّل لصندوق الوارد (حالة "جديد") ليُعاد التعامل معه."""
    _require_manage(actor)
    if report.status != "postponed":
        raise ReportStateError("البلاغ مو مؤجَّل.")
    report.status = "new"
    report.manager_id = None
    db.session.add(AuditLog(actor_user_id=actor.id, action="report.resume",
                             entity_type="Report", entity_id=report.id))
    db.session.commit()
    return report


def cancel_report(report: Report, *, actor, reason: str) -> Report:
    if not reason or not reason.strip():
        raise ReportStateError("سبب الإلغاء إلزامي.")
    _require_manage(actor)
    if report.status not in ("new", "accepted"):
        raise ReportStateError("لا يمكن إلغاء بلاغ بهذي الحالة.")
    if report.manager_id and report.manager_id != actor.id:
        raise ReportPermissionError("هذا البلاغ مستلم من دكتور ثاني.")
    report.status = "cancelled"
    report.cancel_reason = reason
    report.manager_id = actor.id
    db.session.add(AuditLog(actor_user_id=actor.id, action="report.cancel",
                             entity_type="Report", entity_id=report.id, details=reason))
    db.session.commit()
    return report


def transfer_report(report: Report, *, actor, executor, note: str) -> Report:
    if not note or not note.strip():
        raise ReportStateError("ملاحظة التنفيذ إلزامية عند التحويل.")
    _require_manage(actor)
    if report.status != "accepted":
        raise ReportStateError("لازم تُقبل التذكرة قبل تحويلها.")
    if report.manager_id != actor.id:
        raise ReportPermissionError("هذا البلاغ مستلم من دكتور ثاني — بس هو يقدر يحوّله.")
    if not executor.is_active_account:
        raise ReportStateError("لا يمكن التحويل لحساب معطّل.")

    report.executor_id = executor.id
    report.transfer_note = note
    report.transferred_at = _now()
    # يبقى بحالة "مقبولة" من منظور الدكتور (لسا مسؤول عنها)، لكن نعرضه
    # للمنفّذ كـ"قيد التنفيذ" بالواجهة حسب executor_id + عدم وجود executed_at.
    db.session.add(AuditLog(actor_user_id=actor.id, action="report.transfer",
                             entity_type="Report", entity_id=report.id,
                             details=f"to={executor.id}: {note}"))
    db.session.commit()
    return report


def executor_mark_done(report: Report, *, actor, note=None, evidence_image_url=None, evidence_audio_url=None) -> Report:
    if report.executor_id != actor.id:
        raise ReportPermissionError("أنت مو المنفّذ المحوَّل له هذا البلاغ.")
    if report.status != "accepted" or not report.executor_id:
        raise ReportStateError("هذا البلاغ مو محوَّل لك حالياً.")
    report.status = "executed_pending_review"
    report.execution_note = note
    report.execution_evidence_image_url = evidence_image_url
    report.execution_evidence_audio_url = evidence_audio_url
    report.executed_at = _now()
    db.session.add(AuditLog(actor_user_id=actor.id, action="report.execute",
                             entity_type="Report", entity_id=report.id))
    db.session.commit()
    return report


def close_report(report: Report, *, actor, note=None) -> Report:
    """الإغلاق حصري تماماً لصاحب manager_id — القيد الثابت اللي طلبه صاحب
    النظام: لا يقدر يغيّر closer أو يضغط زر الإغلاق أي حساب غير الدكتور
    اللي استلم البلاغ أصلاً، بغض النظر عن صلاحياته الأخرى."""
    if report.manager_id != actor.id:
        raise ReportPermissionError("الإغلاق حصري لمن استلم البلاغ أصلاً.")
    if report.status not in ("accepted", "executed_pending_review"):
        raise ReportStateError("البلاغ مو جاهز للإغلاق.")
    report.status = "closed"
    report.closer_id = actor.id
    report.closed_at = _now()
    if note:
        report.execution_note = ((report.execution_note + " | ") if report.execution_note else "") + note
    db.session.add(AuditLog(actor_user_id=actor.id, action="report.close",
                             entity_type="Report", entity_id=report.id))
    db.session.commit()
    return report


def self_execute_and_close(report: Report, *, actor, note=None, evidence_image_url=None) -> Report:
    """الدكتور ينفّذ البلاغ بنفسه بدون تحويل — يغلقه مباشرة."""
    _require_manage(actor)
    if report.manager_id != actor.id:
        raise ReportPermissionError("هذا البلاغ مستلم من دكتور ثاني.")
    if report.status != "accepted":
        raise ReportStateError("البلاغ مو بحالة مقبولة.")
    report.execution_note = note
    report.execution_evidence_image_url = evidence_image_url
    report.executed_at = _now()
    return close_report(report, actor=actor)


def delete_cancelled_report(report: Report, *, actor) -> None:
    """حذف نهائي — حصري لصاحب الحلال، وبس للبلاغات الملغاة."""
    if not actor.has_permission("reports.delete_final"):
        raise ReportPermissionError("الحذف النهائي حصري لصاحب الحلال.")
    if report.status != "cancelled":
        raise ReportStateError("الحذف النهائي بس للبلاغات الملغاة.")
    db.session.add(AuditLog(actor_user_id=actor.id, action="report.delete_final",
                             entity_type="Report", entity_id=report.id))
    db.session.delete(report)
    db.session.commit()
