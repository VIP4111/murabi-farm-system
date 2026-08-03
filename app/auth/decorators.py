from functools import wraps
from flask import abort, flash, redirect, request, jsonify
from flask_login import current_user


def require_permission(code: str):
    """
    ديكوريتر يحمي أي route بصلاحية محددة (من permissions_registry.py).
    الفحص يصير على صلاحيات "الدور" (Role) الحالي للمستخدم، مو على اسمه —
    فلو صاحب الحلال غيّر صلاحيات دور معيّن من الإعدادات، التأثير يصير
    فوري على كل مستخدم مرتبط بهذا الدور بدون أي تعديل كود.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_permission(code):
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def rate_limited(key: str, max_calls: int, window_seconds: int):
    """ديكوريتر تحديد معدل الطلبات (بند إضافي 119) — يحمي مسارات معرَّضة
    للإغراق (بلاغات، رفع ملفات) بحد أقصى لكل مستخدم خلال نافذة زمنية.
    مبني على قاعدة البيانات عمداً (راجع `RateLimitHit`) عشان يشتغل صح
    مع أكثر من عملية worker بالسيرفر الفعلي، نفس سبب قفل الدخول ببند 86."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            from app.core.rate_limit_service import check_and_record, RateLimitExceeded
            try:
                check_and_record(user_id=current_user.id, key=key,
                                  max_calls=max_calls, window_seconds=window_seconds)
            except RateLimitExceeded as e:
                message = f"طلبات كثيرة بوقت قصير — حاول بعد {e.retry_after_seconds} ثانية."
                if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify(ok=False, error=message), 429
                flash(message, "error")
                return redirect(request.referrer or "/")
            return view_func(*args, **kwargs)
        return wrapped
    return decorator
