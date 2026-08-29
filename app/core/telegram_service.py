"""إشعارات فورية مجانية عبر تيليجرام (بند إضافي 157) — طلبك: بديل
مجاني بالكامل لإشعارات واتساب (اللي تحتاج اشتراك مدفوع). تيليجرام
Bot API مجاني 100% بلا حد أقصى رسائل.

**الإعداد المطلوب منك مرة وحدة**:
1. افتح تيليجرام وابحث عن "BotFather"، أرسل له `/newbot` واتبع
   التعليمات — يعطيك توكن (نص طويل شكله `123456:ABC-DEF...`).
2. حط هذا التوكن كمتغير بيئة `TELEGRAM_BOT_TOKEN` بلوحة Render (نفس
   أسلوب متغيرات Cloudinary، بند 151).
3. كل عضو فريق يفتح محادثة مع البوت (يبحث باسم البوت اللي اخترته)
   ويرسل له أي رسالة (مثلاً "مرحبا").
4. شغّل أمر `flask telegram-updates` (من Shell بلوحة Render) — يطبع
   لك اسم كل شخص راسل البوت مع رقم "Chat ID" بتاعه.
5. انسخ كل Chat ID وحطه بشاشة "تعديل عضو الفريق" لذلك الشخص.

بدون التوكن، أو لعضو بدون Chat ID مسجَّل، الإرسال يتجاهَل بصمت —
صفر كسر بالنظام لو ما فعّلت الميزة بعد.
"""
import hashlib
import os
import requests


def _bot_token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN")


def webhook_secret() -> str | None:
    """بصمة مشتقة من التوكن نفسه (بند إضافي 160) — تُستخدم للتحقق من إن
    كل نبضة واردة لـ`/telegram/webhook` جاية من تيليجرام فعلاً، بدون
    الحاجة لمتغير بيئة إضافي يُضبط يدوياً بلوحة Render."""
    token = _bot_token()
    if not token:
        return None
    return hashlib.sha256(token.encode()).hexdigest()[:32]


def set_webhook(url: str) -> bool:
    token = _bot_token()
    secret = webhook_secret()
    if not token or not secret:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": url, "secret_token": secret},
            timeout=5,
        )
        if not resp.ok:
            _log_failure(f"set_webhook failed url={url} status={resp.status_code} body={resp.text[:200]}")
        return resp.ok
    except requests.RequestException as e:
        _log_failure(f"set_webhook network error url={url}: {e}")
        return False


def inline_keyboard(buttons: list[tuple[str, str]]) -> dict:
    """يبني `reply_markup` لأزرار رابط (URL) تحت الرسالة (بند إضافي
    304) — زر وحد بكل صف (أوضح على شاشة الجوال من صفوف متعددة الأعمدة).
    كل زر رابط مباشر (مو callback_data)، فما يحتاج أي معالجة webhook
    إضافية — تيليجرام يفتح الرابط بمتصفح الجوال مباشرة."""
    return {"inline_keyboard": [[{"text": label, "url": url}] for label, url in buttons]}


def send_message(chat_id: str | None, text: str, reply_markup: dict | None = None) -> bool:
    """يرجّع True لو نجح الإرسال فعلياً، False لأي سبب (بدون توكن، بدون
    chat_id، أو خطأ شبكة/API) — العملية الأساسية (توزيع مهمة، تنبيه
    طوارئ...) ما تتوقف أبداً بسبب فشل إشعار. بس صار يسجّل السبب بالـlog
    (بند إضافي 232) بدل الصمت الكامل — قبل كذا ما فيه أي أثر لو التوكن
    انسحب أو فشل الإرسال فعلياً، تكتشفه بالصدفة بس. ``reply_markup``
    اختياري (بند إضافي 304) — أزرار تفاعلية تحت الرسالة، ابنها بـ
    `inline_keyboard()`؛ بدونها نفس السلوك القديم حرفياً."""
    token = _bot_token()
    if not token or not chat_id:
        return False
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=5,
        )
        if not resp.ok:
            _log_failure(f"send_message failed chat_id={chat_id} status={resp.status_code} body={resp.text[:200]}")
        return resp.ok
    except requests.RequestException as e:
        _log_failure(f"send_message network error chat_id={chat_id}: {e}")
        return False


def _log_failure(message: str) -> None:
    try:
        from flask import current_app
        current_app.logger.warning("telegram_service: %s", message)
    except RuntimeError:
        pass  # خارج سياق تطبيق (سكربت CLI مستقل) — ما فيه logger نشغّله عليه


def notify_user(user, text: str, reply_markup: dict | None = None) -> bool:
    if not user:
        return False
    return send_message(getattr(user, "telegram_chat_id", None), text, reply_markup=reply_markup)


def diagnose() -> dict:
    """تشخيص حالة بوت تيليجرام (بند إضافي 232) — طلبك: "ما سبب توقف
    رسايل تيليجرام؟". قبل هذا، `send_message`/`set_webhook` يفشلون
    بصمت دائماً (عمداً، عشان فشل إشعار ما يوقف عملية أساسية زي توزيع
    مهمة) — هذا يعني صفر أثر مرئي لو التوكن انسحب أو الـwebhook انكسر،
    وما فيه طريقة تعرف السبب الحقيقي غير هذا الفحص المباشر. يستخدم
    `getMe` (هل التوكن صالح؟) و`getWebhookInfo` (تيليجرام نفسه يرجّع
    `last_error_message` — آخر خطأ واجهه وهو يحاول يوصلنا، أدق مصدر
    ممكن لتشخيص "توقف الإرسال من تاريخ معيّن")."""
    token = _bot_token()
    result = {"token_set": bool(token)}
    if not token:
        result["diagnosis"] = "TELEGRAM_BOT_TOKEN غير مضبوط بمتغيرات البيئة — هذا سبب التوقف الأرجح."
        return result

    try:
        me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5).json()
    except requests.RequestException as e:
        result["token_valid"] = False
        result["diagnosis"] = f"فشل الاتصال بـtelegram API أصلاً: {e}"
        return result

    result["token_valid"] = bool(me.get("ok"))
    if not result["token_valid"]:
        result["diagnosis"] = f"التوكن غير صالح (تيليجرام رد: {me.get('description')}) — غالباً انسحب/اتغيّر من BotFather."
        return result
    result["bot_username"] = me.get("result", {}).get("username")

    try:
        wh = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=5).json().get("result", {})
    except requests.RequestException as e:
        result["diagnosis"] = f"التوكن سليم بس تعذّر فحص الـwebhook: {e}"
        return result

    result["webhook_url"] = wh.get("url") or None
    result["pending_update_count"] = wh.get("pending_update_count")
    result["last_error_message"] = wh.get("last_error_message")
    result["last_error_date"] = wh.get("last_error_date")

    if not wh.get("url"):
        result["diagnosis"] = "التوكن سليم بس ما فيه webhook مسجَّل حالياً — الأوامر التفاعلية (قبول/إغلاق مهمة) بس تتأثر، الإرسال (send_message) يبقى شغّال."
    elif wh.get("last_error_message"):
        result["diagnosis"] = f"webhook مسجَّل، بس آخر محاولة وصول لنا فشلت: {wh['last_error_message']}"
    else:
        result["diagnosis"] = "التوكن سليم والـwebhook شغّال بدون أخطاء مسجَّلة — لو الرسائل لسا متوقفة، السبب على الأغلب Chat ID فردي (عضو حظر البوت أو بدّل حسابه)، مو مشكلة عامة."
    return result


def fetch_recent_chats() -> list[dict]:
    """يرجّع قائمة {name, chat_id} من آخر رسائل وصلت للبوت (Telegram
    `getUpdates`) — يستخدمها أمر `flask telegram-updates` بس، عشان
    صاحب المزرعة يلقط Chat ID كل عضو بسهولة بدون أي إعداد Webhook
    معقّد (غير عملي لمزرعة صغيرة)."""
    token = _bot_token()
    if not token:
        return []
    try:
        resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    seen = {}
    for update in data.get("result", []):
        msg = update.get("message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        name = chat.get("first_name") or chat.get("username") or str(chat_id)
        if chat.get("last_name"):
            name = f"{name} {chat['last_name']}"
        seen[chat_id] = name
    return [{"name": name, "chat_id": str(chat_id)} for chat_id, name in seen.items()]
