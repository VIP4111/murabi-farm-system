"""تقارير دورية عبر البريد الإلكتروني (بند إضافي 160، المرحلة ج) —
مجاني بالكامل عبر SMTP عادي (Gmail، Outlook، أو أي مزوّد بريد مجاني
يدعم "App Password")، نفس فلسفة `telegram_service.py` بالضبط: صفر
متغيرات بيئة = صفر إرسال، بدون أي كسر بالنظام.

**الإعداد المطلوب منك مرة وحدة** (اختياري تماماً):
1. لو عندك Gmail: فعّل "التحقق بخطوتين" بحسابك، وأنشئ "App Password"
   من إعدادات الأمان (myaccount.google.com/apppasswords).
2. حط 4 متغيرات بيئة بلوحة Render:
   `SMTP_HOST` (مثال: smtp.gmail.com)
   `SMTP_PORT` (مثال: 587)
   `SMTP_USER` (بريدك الإلكتروني)
   `SMTP_PASSWORD` (App Password من فوق، مو كلمة مرور حسابك العادية)
3. حط بريدك الإلكتروني بشاشة "تعديل عضو الفريق" لحسابك.

بدون هذا الإعداد، لا يصير أي شي — التقرير التلقائي يتجاهَل نفسه بصمت.
"""
import os
import smtplib
import ssl
from email.mime.text import MIMEText


def _smtp_config() -> dict | None:
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    if not host or not user or not password:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": user,
        "password": password,
        "from_addr": os.environ.get("SMTP_FROM", user),
    }


def send_email(to_email: str | None, subject: str, body: str) -> bool:
    """يرجّع True لو نجح الإرسال فعلياً، False لأي سبب (بدون إعداد
    SMTP، بدون بريد للمستقبل، أو خطأ اتصال/مصادقة) — بصمت دائماً، نفس
    فلسفة `telegram_service.send_message`."""
    cfg = _smtp_config()
    if not cfg or not to_email:
        return False
    try:
        msg = MIMEText(body, _charset="utf-8")
        msg["Subject"] = subject
        msg["From"] = cfg["from_addr"]
        msg["To"] = to_email
        context = ssl.create_default_context()
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
            server.starttls(context=context)
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["from_addr"], [to_email], msg.as_string())
        return True
    except (smtplib.SMTPException, OSError):
        return False


def notify_user(user, subject: str, body: str) -> bool:
    if not user:
        return False
    return send_email(getattr(user, "email", None), subject, body)
