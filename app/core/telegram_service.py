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
import os
import requests


def _bot_token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN")


def send_message(chat_id: str | None, text: str) -> bool:
    """يرجّع True لو نجح الإرسال فعلياً، False لأي سبب (بدون توكن، بدون
    chat_id، أو خطأ شبكة/API) — بصمت دائماً، إشعار فاشل ما يوقف العملية
    الأساسية (توزيع مهمة، تنبيه طوارئ...) أبداً."""
    token = _bot_token()
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5,
        )
        return resp.ok
    except requests.RequestException:
        return False


def notify_user(user, text: str) -> bool:
    if not user:
        return False
    return send_message(getattr(user, "telegram_chat_id", None), text)


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
