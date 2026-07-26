from functools import wraps
from flask import abort
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
