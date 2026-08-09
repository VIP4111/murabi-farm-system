"""تقارير دورية عبر البريد الإلكتروني (بند إضافي 160، المرحلة ج) —
عبر HTTPS API (Brevo، مجاني حتى 300 إيميل/يوم بدون بطاقة) بدل SMTP
التقليدي، نفس فلسفة `telegram_service.py` بالضبط: صفر متغيرات بيئة
= صفر إرسال، بدون أي كسر بالنظام.

**السبب التقني لاستخدام API بدل SMTP مباشر** (بند إضافي 160.3): أول
تجربة حقيقية على Render كشفت إن منافذ SMTP الصادرة (587/25/465)
محظورة على الخطة المجانية — الاتصال يعلّق بدون أي رد (لا نجاح ولا
فشل سريع)، لدرجة إنه يتجاوز حتى مهلة gunicorn الداخلية ويطيح
بالعملية كلها. طلبات HTTPS العادية (نفس النوع اللي يستخدمه تيليجرام
بالفعل بنجاح) ما فيها هذي المشكلة.

**الإعداد المطلوب منك مرة وحدة** (اختياري تماماً):
1. أنشئ حساب مجاني على brevo.com.
2. أكّد بريدك كـ"مُرسل" (Sender) من إعدادات Brevo.
3. جيب مفتاح API من إعدادات Brevo (SMTP & API ← API Keys).
4. حط 3 متغيرات بيئة بلوحة Render: `BREVO_API_KEY`،
   `EMAIL_FROM_ADDRESS` (نفس البريد المؤكَّد كمُرسل)، و `EMAIL_FROM_NAME`
   (اختياري، افتراضياً "مراح بو علي").

بدون هذا الإعداد، لا يصير أي شي — التقرير التلقائي يتجاهَل نفسه بصمت.
"""
import os
import requests


def _config() -> dict | None:
    api_key = os.environ.get("BREVO_API_KEY")
    from_addr = os.environ.get("EMAIL_FROM_ADDRESS")
    if not api_key or not from_addr:
        return None
    return {
        "api_key": api_key,
        "from_addr": from_addr,
        "from_name": os.environ.get("EMAIL_FROM_NAME", "مراح بو علي"),
    }


def send_email(to_email: str | None, subject: str, body: str) -> bool:
    """يرجّع True لو نجح الإرسال فعلياً، False لأي سبب (بدون إعداد
    Brevo، بدون بريد للمستقبل، أو خطأ اتصال/مصادقة) — بصمت دائماً، نفس
    فلسفة `telegram_service.send_message`."""
    cfg = _config()
    if not cfg or not to_email:
        return False
    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": cfg["api_key"], "Content-Type": "application/json"},
            json={
                "sender": {"email": cfg["from_addr"], "name": cfg["from_name"]},
                "to": [{"email": to_email}],
                "subject": subject,
                "textContent": body,
            },
            timeout=10,
        )
        return resp.ok
    except requests.RequestException:
        return False


def notify_user(user, subject: str, body: str) -> bool:
    if not user:
        return False
    return send_email(getattr(user, "email", None), subject, body)
