"""تنبيهات فورية سياقية (Contextual Triggered Notifications) — بند
إضافي 230: بعد إتمام إجراء بصفحة معيّنة، لو فيه إجراء تابع يستاهل
المراجعة بصفحة ثانية، نطلع Toast فوري فيه زر ينقل المستخدم مباشرة،
بدل ما ينتظره يوصله عن طريق شاشة "التنبيهات" العامة لاحقاً.

آلية النقل: نفس `flash()` القياسية بفلاسك (نفس القناة المستخدمة أصلاً
بكل المشروع)، بس بفئة خاصة "toast" ورسالة بصيغة JSON (نص + رابط + نص
الزر) بدل نص عادي. `base.html` يتعرف على فئة "toast" ويبني منها مكوّن
منبثق بدل سطر Flash العادي. تُستخدم مع أي مسار ينتهي بـ Redirect
(الحالة الشائعة بهذا المشروع بعد كل حفظ). لمسار AJAX بدون Redirect،
رجّع نفس القاموس مباشرة بجسم استجابة JSON بدل استدعاء هذي الدالة.

مصدر شرط الإطلاق نفسه (هل فعلاً فيه شي يستاهل التنبيه؟) يُفترض دائماً
يُبنى فوق نفس منطق/معايير `app/core/alerts_service.py` (نافذة
`alert_before_days` مثلاً) بدل شروط مستقلة مكررة — مصدر واحد للحقيقة."""
import json
from flask import flash, url_for


def flash_toast(payload: dict | None) -> None:
    """payload لازم يحتوي message / url_endpoint / button_text
    (و url_kwargs اختياري). لو None (يعني ما فيه شي يستاهل التنبيه)،
    ما يسوي شي — استدعِها دايماً بدون شرط قبلها بالراوت."""
    if not payload:
        return
    url = url_for(payload["url_endpoint"], **payload.get("url_kwargs", {}))
    flash(
        json.dumps({
            "message": payload["message"],
            "url": url,
            "button_text": payload["button_text"],
        }, ensure_ascii=False),
        "toast",
    )
