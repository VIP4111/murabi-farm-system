"""إشعارات Push حقيقية (بند إضافي، طلبك الصريح: "ابيك تصير مثل
الواتساب... يجيني تنبيه والجوال بجيبي") — بروتوكول Web Push القياسي
المدعوم بكل المتصفحات الحديثة (Chrome/Edge/Firefox مباشرة، Safari/iOS
فقط لو ثبّت المستخدم التطبيق كـ"أضف للشاشة الرئيسية"). الإرسال يمر
عبر خادم دفع المتصفح نفسه (Google/Mozilla/Apple) — التطبيق ما يحتاج
اتصال دائم بالجهاز، يكفي إرسال طلب واحد وقت الحدث.

مفاتيح VAPID (توقيع يثبت لخادم الدفع إن الإشعار فعلاً من هذا الموقع)
تُقرأ من متغيرات بيئة (نفس نمط `TELEGRAM_BOT_TOKEN` — سر لا يُخزَّن
بقاعدة البيانات ولا بالكود): `VAPID_PRIVATE_KEY_PEM_B64` و
`VAPID_PUBLIC_KEY_B64URL`. تُولَّد مرة وحدة بأمر `flask generate-vapid-keys`
(راجع app/cli.py) وتُحفظ بمتغيرات بيئة Render.
"""
import base64
import json
import os

from pywebpush import webpush, WebPushException


def vapid_configured() -> bool:
    return bool(os.environ.get("VAPID_PRIVATE_KEY_PEM_B64")) and bool(os.environ.get("VAPID_PUBLIC_KEY_B64URL"))


def get_vapid_public_key() -> str | None:
    """المفتاح العام (Base64URL) — يُرسَل للمتصفح وقت الاشتراك، آمن
    مشاركته بالكامل (على عكس المفتاح الخاص)."""
    return os.environ.get("VAPID_PUBLIC_KEY_B64URL")


def _private_key_pem() -> bytes | None:
    raw = os.environ.get("VAPID_PRIVATE_KEY_PEM_B64")
    if not raw:
        return None
    return base64.b64decode(raw)


def generate_vapid_keys() -> tuple[str, str]:
    """يولّد زوج مفاتيح VAPID جديد ويرجّعهم كنصوص جاهزة للصق بمتغيرات
    بيئة Render — لا يحفظهم بأي مكان (المفتاح الخاص سرّي)."""
    from py_vapid import Vapid02
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    vapid = Vapid02()
    vapid.generate_keys()
    private_pem_b64 = base64.b64encode(vapid.private_pem()).decode()
    public_raw = vapid.public_key.public_bytes(
        encoding=Encoding.X962, format=PublicFormat.UncompressedPoint,
    )
    public_b64url = base64.urlsafe_b64encode(public_raw).decode().rstrip("=")
    return private_pem_b64, public_b64url


PUSH_ALERT_CHECK_INTERVAL_MINUTES = 15


def check_and_send_alert_push_notifications() -> None:
    """نقطة الفحص الدورية لتحويل التنبيهات الحية (`alerts_service`) لـ
    Push فعلي — بنفس فلسفة `catch_up_daily_tasks_before_request` بالضبط
    (موثّقة بـ`app/core/scheduler.py`): Render المجاني ينام، فـ
    BackgroundScheduler وحده مو كافٍ لضمان فحص دوري حقيقي — هذي الدالة
    تُستدعى من `before_request` (نفس نمط التدارك) بحارس زمني
    (`PUSH_ALERT_CHECK_INTERVAL_MINUTES`) عشان ما تُحسب كل تنبيهات
    المزرعة كاملة بكل طلب وارد، بس مرة كل ~15 دقيقة بغض النظر مين زار
    الموقع.

    `SentPushAlert` يمنع تكرار نفس التنبيه — بدونه كل فحص كان يرسل كل
    التنبيهات النشطة من جديد (هي محسوبة حية بدون تخزين أصلاً، القرار
    التصميمي الموثَّق بأعلى `scheduler.py`)."""
    from datetime import datetime, timedelta, timezone
    from app.extensions import db
    from app.models import FarmSettings, PushSubscription, SentPushAlert
    from app.core import alerts_service

    fs = FarmSettings.get()
    now = datetime.now(timezone.utc)
    last_check = fs.last_push_alert_check
    if last_check is not None:
        last_check_aware = last_check if last_check.tzinfo else last_check.replace(tzinfo=timezone.utc)
        if now - last_check_aware < timedelta(minutes=PUSH_ALERT_CHECK_INTERVAL_MINUTES):
            return
    fs.last_push_alert_check = now
    db.session.commit()

    if not vapid_configured():
        return

    user_ids = [row[0] for row in db.session.query(PushSubscription.user_id).distinct().all()]
    if not user_ids:
        return

    from app.models import User
    for user in User.query.filter(User.id.in_(user_ids)).all():
        try:
            alerts = alerts_service.get_alerts_for_user(user)
        except Exception:
            continue
        if not alerts:
            continue
        already_sent = {
            row[0] for row in
            db.session.query(SentPushAlert.alert_key).filter_by(user_id=user.id).all()
        }
        new_alerts = [a for a in alerts if alerts_service.alert_key(a) not in already_sent]
        if not new_alerts:
            continue

        subs = PushSubscription.query.filter_by(user_id=user.id).all()
        for alert in new_alerts[:5]:
            key = alerts_service.alert_key(alert)
            delivered = False
            for sub in subs:
                try:
                    if send_push(sub, {
                        "title": f"{alert.get('icon', '')} {alert.get('category', '')}".strip(),
                        "body": alert.get("label", ""),
                        "url": alerts_service.alert_action_url(alert) or "/today",
                    }):
                        delivered = True
                    else:
                        db.session.delete(sub)
                except Exception:
                    continue
            db.session.add(SentPushAlert(user_id=user.id, alert_key=key))
            db.session.commit()


def send_push(subscription, payload: dict) -> bool:
    """يرسل إشعار واحد لاشتراك واحد. يرجّع False (بدون ما يفشل الطلب
    كله) لو الاشتراك انتهت صلاحيته أو أُلغي من طرف المستخدم (410/404 —
    شائع جداً، المستخدم مسح المتصفح أو ألغى الإذن) — الطرف المستدعي
    يحذف الاشتراك حينها. أي خطأ ثاني (شبكة، مفاتيح خاطئة) يُسجَّل ويُرفع
    للأعلى عشان ما ينكتم بصمت.
    """
    from flask import current_app

    private_pem = _private_key_pem()
    if not private_pem:
        current_app.logger.warning("push_service: VAPID keys not configured, skipping send")
        return False

    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=private_pem.decode(),
            vapid_claims={"sub": "mailto:support@murabi-boali.app"},
        )
        return True
    except WebPushException as e:
        status = e.response.status_code if e.response is not None else None
        if status in (404, 410):
            return False
        current_app.logger.warning("push_service: webpush failed (status=%s): %s", status, e)
        raise
