"""إشعارات Push حقيقية (بند إضافي، طلبك الصريح: "ابيك تصير مثل
الواتساب... يجيني تنبيه والجوال بجيبي") — بروتوكول Web Push القياسي
المدعوم بكل المتصفحات الحديثة (Chrome/Edge/Firefox مباشرة، Safari/iOS
فقط لو ثبّت المستخدم التطبيق كـ"أضف للشاشة الرئيسية"). الإرسال يمر
عبر خادم دفع المتصفح نفسه (Google/Mozilla/Apple) — التطبيق ما يحتاج
اتصال دائم بالجهاز، يكفي إرسال طلب واحد وقت الحدث.

مفاتيح VAPID (توقيع يثبت لخادم الدفع إن الإشعار فعلاً من هذا الموقع)
تُقرأ من متغيرات بيئة (نفس نمط `TELEGRAM_BOT_TOKEN` — سر لا يُخزَّن
بقاعدة البيانات ولا بالكود): `VAPID_PRIVATE_KEY_B64URL` و
`VAPID_PUBLIC_KEY_B64URL`. تُولَّد مرة وحدة بأمر `flask generate-vapid-keys`
(راجع app/cli.py) وتُحفظ بمتغيرات بيئة Render.

إصلاح — بلاغ مستخدم حقيقي بعد تجربة حية: "فشل الإرسال — تأكد إن
مفاتيح VAPID مضبوطة". السبب الفعلي: `pywebpush.webpush()` يمرّر
`vapid_private_key` لـ`py_vapid.Vapid.from_string()`، اللي يتوقّع نص
Base64URL خام (32 بايت مفتاح خاص، أو DER مُرمَّز) بدون أي رؤوس PEM —
هو نفسه يحذف فواصل الأسطر بس **يبقي** سطري `-----BEGIN/END-----`
كنص، فيفسد فك الترميز بالكامل ("ASN.1 parsing error: invalid
length"). التخزين السابق (PEM كامل مُرمَّز Base64) كان صحيحاً كـPEM
حقيقي لكنه **صيغة خاطئة لما تتوقعه py_vapid تحديداً** — تم تأكيده
بإعادة إنتاج نفس الخطأ محلياً بنفس القيمة اللي ولّدها الأمر القديم.
الحل: تخزين المفتاح الخاص كـDER مُرمَّز Base64URL مباشرة (نفس الصيغة
اللي يتوقعها `Vapid.from_der()` داخلياً)، بدون أي تغليف PEM إضافي.
"""
import base64
import json
import os

from pywebpush import webpush, WebPushException


def vapid_configured() -> bool:
    return bool(os.environ.get("VAPID_PRIVATE_KEY_B64URL")) and bool(os.environ.get("VAPID_PUBLIC_KEY_B64URL"))


def get_vapid_public_key() -> str | None:
    """المفتاح العام (Base64URL) — يُرسَل للمتصفح وقت الاشتراك، آمن
    مشاركته بالكامل (على عكس المفتاح الخاص)."""
    return os.environ.get("VAPID_PUBLIC_KEY_B64URL")


def _private_key_str() -> str | None:
    """نص Base64URL خام (DER) جاهز يُمرَّر مباشرة لـ`pywebpush.webpush()`
    — بدون أي فك/إعادة ترميز هنا، لأن py_vapid نفسه يتولى فك الترميز
    داخلياً (`Vapid.from_string`)."""
    return os.environ.get("VAPID_PRIVATE_KEY_B64URL") or None


def generate_vapid_keys() -> tuple[str, str]:
    """يولّد زوج مفاتيح VAPID جديد ويرجّعهم كنصوص جاهزة للصق بمتغيرات
    بيئة Render — لا يحفظهم بأي مكان (المفتاح الخاص سرّي). المفتاح
    الخاص بصيغة DER مُرمَّز Base64URL (بدون رؤوس PEM) — نفس الصيغة
    اللي يتوقعها `py_vapid.Vapid.from_string()` داخل `pywebpush`."""
    from py_vapid import Vapid02
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, PrivateFormat, NoEncryption,
    )

    vapid = Vapid02()
    vapid.generate_keys()
    private_der = vapid.private_key.private_bytes(
        encoding=Encoding.DER, format=PrivateFormat.PKCS8, encryption_algorithm=NoEncryption(),
    )
    private_b64url = base64.urlsafe_b64encode(private_der).decode().rstrip("=")
    public_raw = vapid.public_key.public_bytes(
        encoding=Encoding.X962, format=PublicFormat.UncompressedPoint,
    )
    public_b64url = base64.urlsafe_b64encode(public_raw).decode().rstrip("=")
    return private_b64url, public_b64url


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
        # بند إضافي (طلبك: "نخلي اختيار التنبيهات المراقَب فيها عن
        # طريق الإعدادات") — كل مستخدم يقدر يلغي أنواع تنبيهات معيّنة
        # لنفسه بس (User.push_muted_categories). تُستبعَد هنا قبل
        # حساب الجديد/المُرسَل سابقاً، فما تُسجَّل بـSentPushAlert
        # أصلاً — لو المستخدم فعّلها لاحقاً، يوصله التنبيه وقتها عادي.
        muted = user.muted_push_categories()
        if muted:
            alerts = [a for a in alerts if a.get("category_key") not in muted]
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

    private_key_str = _private_key_str()
    if not private_key_str:
        current_app.logger.warning("push_service: VAPID keys not configured, skipping send")
        return False

    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=private_key_str,
            vapid_claims={"sub": "mailto:support@murabi-boali.app"},
        )
        return True
    except WebPushException as e:
        status = e.response.status_code if e.response is not None else None
        # إصلاح — بلاغ مستخدم حقيقي بعد تدوير مفاتيح VAPID (خلل صيغة
        # سابق بهذا الملف): أي اشتراك انسجّل بمفتاح عام قديم يفشل بصمت
        # بـ400 "VapidPkHashMismatch" من خادم الدفع — الاشتراك نفسه
        # صار غير صالح نهائياً (مربوط تشفيرياً بمفتاح قديم)، بنفس فئة
        # 404/410 (اشتراك منتهي/ملغى)، لا خطأ عابر يستاهل إعادة محاولة.
        body_text = e.response.text if e.response is not None else ""
        if status in (404, 410) or (status == 400 and "VapidPkHashMismatch" in body_text):
            return False
        current_app.logger.warning("push_service: webpush failed (status=%s): %s", status, e)
        raise


def notify_user(user, title: str, body: str, url: str | None = None) -> bool:
    """إشعار Push فوري لمستخدم محدَّد — لأحداث شخصية (بند إضافي، طلبك:
    "إشعار فوري لمهمة/بلاغ معيّن لك شخصياً") — نفس فلسفة
    `telegram_service.notify_user()` بالضبط: يتجاهل بصمت لو المستخدم
    ما عنده أي اشتراك مسجَّل أو مفاتيح VAPID غير مضبوطة (صفر كسر
    لمسار الاستدعاء الأصلي — توزيع مهمة/بلاغ ينجح بغض النظر عن حالة
    إشعارات Push). يرجّع True لو نجح إرسال إشعار واحد فعلاً على الأقل
    (المستخدم قد يكون له أكثر من جهاز مسجَّل)."""
    from app.extensions import db
    from app.models import PushSubscription

    if not vapid_configured():
        return False
    subs = PushSubscription.query.filter_by(user_id=user.id).all()
    if not subs:
        return False
    sent = False
    for sub in subs:
        try:
            if send_push(sub, {"title": title, "body": body, "url": url or "/today"}):
                sent = True
            else:
                db.session.delete(sub)
        except Exception:
            continue
    db.session.commit()
    return sent
