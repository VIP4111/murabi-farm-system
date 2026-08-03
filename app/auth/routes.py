from flask import render_template, redirect, url_for, request, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_babel import gettext as _

from app.auth import auth_bp
from app.extensions import db
from app.models import User


@auth_bp.route("/login/language", methods=["POST"])
def set_pre_login_language():
    """
    اختيار لغة شاشة الدخول نفسها قبل تسجيل الدخول (بند إضافي، 2026-07-23)
    — يُخزَّن بالجلسة المؤقتة (`session['lang']`) ويغيّر شكل شاشة الدخول
    فوراً. **بند إضافي 113**: صار يُحفَظ تلقائياً كلغة دائمة للحساب
    (`User.language`) أول ما يسجّل المستخدم دخول بنجاح — قبل هذا كان
    يُتجاهَل بصمت بعد الدخول (راجع `login()`).
    """
    lang = request.form.get("language")
    if lang in current_app.config["SUPPORTED_LANGUAGES"]:
        session["lang"] = lang
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("core.home"))

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(phone=phone).first()

        # قفل بعد محاولات فاشلة متكررة (بند إضافي 86) — ما كان فيه أي حد
        # سابق، يعني بروت-فورس بلا نهاية على أي رقم جوال معروف. نتحقق من
        # القفل قبل حتى فحص كلمة المرور، عشان محاولة صحيحة أثناء القفل
        # ما تمرّ سهواً.
        if user and user.is_locked():
            flash(_("الحساب مقفل مؤقتاً بسبب محاولات دخول فاشلة متكررة — حاول بعد 15 دقيقة."), "error")
            return render_template("login.html")

        if user and user.is_active_account and user.check_password(password):
            user.register_successful_login()
            # بند إضافي 113 — قبل هذا، اختيار اللغة بشاشة الدخول
            # (`session['lang']`) كان يتغيّر شكل شاشة الدخول نفسها بس،
            # ويُتجاهَل بصمت بعد الدخول الفعلي (select_locale يعطي
            # الأولوية لـUser.language المحفوظة، "ar" افتراضياً لأي
            # حساب ما غيّرها من قبل عبر مبدّل اللغة بالقائمة الجانبية —
            # مبدّل حقيقي لكنه غير معروف لأغلب المستخدمين). صار الاختيار
            # الصريح قبل الدخول يُحفَظ تلقائياً لحساب المستخدم نفسه.
            picked_lang = session.pop("lang", None)
            if picked_lang and picked_lang in current_app.config["SUPPORTED_LANGUAGES"]:
                user.language = picked_lang
            db.session.commit()
            # remember=True (كوكي دخول طويل الأمد) — ضروري لدعم العمل بدون
            # إنترنت (عامل/دكتور/ممرض): لو تطبيق الـPWA أُغلق تماماً بالجوال
            # وهو أوف لاين، لازم الجلسة تبقى صالحة لما يرجع الاتصال عشان
            # تكتمل مزامنة البيانات المحفوظة محلياً بدون ما يحتاج يسجّل
            # دخول من جديد. مقبول أمنياً هنا (أجهزة شخصية لفريق مزرعة واحدة،
            # مو تطبيق عام لمستخدمين غرباء).
            login_user(user, remember=True)
            return redirect(url_for("core.home"))

        if user and user.is_active_account:
            user.register_failed_login()
            db.session.commit()

        flash(_("رقم الجوال أو كلمة المرور غير صحيحة"), "error")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
