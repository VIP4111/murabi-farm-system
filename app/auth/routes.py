from flask import render_template, redirect, url_for, request, flash, session, current_app, abort, make_response
from flask_login import login_user, logout_user, login_required, current_user
from flask_babel import gettext as _

from app.auth import auth_bp
from app.extensions import db
from app.models import User, ServiceToggle


def _quick_login_enabled() -> bool:
    toggle = ServiceToggle.query.filter_by(key="dev_quick_login").first()
    return bool(toggle and toggle.is_enabled)


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
            # بند إضافي (2026-08-30) — كانت "15 دقيقة" نص ثابت بالرسالة
            # بغض النظر عن قيمة User.LOCKOUT_MINUTES الفعلية، فلو غيّرت
            # المدة (زي طلبك: صارت دقيقة وحدة) تبقى الرسالة تقول رقماً
            # غلطاً. صارت تقرأ القيمة الحقيقية من الثابت نفسه.
            flash(_("الحساب مقفل مؤقتاً بسبب محاولات دخول فاشلة متكررة — حاول بعد %(n)s دقيقة.", n=User.LOCKOUT_MINUTES), "error")
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

    quick_login_accounts = []
    if _quick_login_enabled():
        quick_login_accounts = (User.query.filter_by(is_active_account=True)
                                 .order_by(User.name).all())
    return _no_cache_response(render_template("login.html", quick_login_accounts=quick_login_accounts))


@auth_bp.route("/login/quick", methods=["POST"])
def quick_login():
    """دخول سريع بلا كلمة مرور (بند إضافي 123) — للتجربة/التطوير بس.
    الفحص الحاسم هنا خادمي (`_quick_login_enabled()`)، مو مجرد إخفاء
    الزر بالواجهة — حتى لو حد عرف الرابط مباشرة، يُرفض لو الخدمة موقوفة
    من الإعدادات (موقوفة افتراضياً)."""
    if current_user.is_authenticated:
        return redirect(url_for("core.home"))
    if not _quick_login_enabled():
        abort(403)
    user = User.query.get_or_404(request.form.get("user_id", type=int))
    if not user.is_active_account:
        abort(403)
    user.register_successful_login()
    db.session.commit()
    login_user(user, remember=True)
    return redirect(url_for("core.home"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    # بند إصلاح — بلاغ مستخدم: أحياناً بعد تسجيل خروج ودخول برقم/كلمة
    # مرور حساب ثاني فعلياً، يفتح النظام حساب المستخدم السابق. السبب
    # الأرجح على أجهزة/شبكات المزرعة الضعيفة: صفحة "تسجيل الدخول" تُخزَّن
    # بذاكرة المتصفح (bfcache) مع الجلسة القديمة، وبعض المتصفحات تعيد
    # عرضها من الذاكرة بدل طلب نسخة جديدة فعلياً من السيرفر. `session.clear()`
    # هنا طبقة حماية إضافية فوق تنظيف Flask-Login التلقائي (يغطي أي
    # مفتاح جلسة ثاني)، والرؤوس تحت (`no_cache_response`) تمنع أي طبقة
    # تخزين (متصفح/بروكسي) من عرض نسخة قديمة من شاشة الدخول بعد الخروج.
    #
    # إصلاح خطير — بلاغ مستخدم حقيقي: "أسوي خروج من حساب الدكتور ما
    # يطلع" (يرجعه للرئيسية وهو لسا داخل بالحساب). السبب: تسجيل الدخول
    # دايماً يستخدم `remember=True` (كوكي "تذكّرني" منفصلة عن كوكي
    # الجلسة). `logout_user()` بالسطر فوق يعلّم `session['_remember'] =
    # 'clear'` — هذي هي الإشارة اللي يعتمد عليها Flask-Login بعد
    # الطلب (`after_request` الخاص فيه) عشان فعلياً يحذف كوكي "تذكّرني"
    # من المتصفح. لكن `session.clear()` تحت كانت تمسح هذا العلم بالذات
    # *قبل* ما يوصل دوره — يعني كوكي "تذكّرني" تبقى صالحة بالمتصفح رغم
    # الخروج! أول طلب بعدها لأي صفحة (بما فيها /login نفسها) يعيد
    # تسجيل الدخول تلقائياً وبصمت عبر تلك الكوكي — و`login()` نفسها
    # عندها "لو مسجّل دخول، ودّيه الرئيسية" — فيبان تماماً وكإن "خروج"
    # ما سوى شي. الحل: نمسح كوكي "تذكّرني" صراحة بأنفسنا هنا (نفس
    # الاسم والإعدادات اللي يستخدمها Flask-Login) قبل `session.clear()`،
    # عشان ما نعتمد على ترتيب تنفيذ داخلي حسّاس كذا مرة ثانية.
    response = _no_cache_response(redirect(url_for("auth.login")))
    remember_cookie_name = current_app.config.get("REMEMBER_COOKIE_NAME", "remember_token")
    response.delete_cookie(remember_cookie_name)
    session.clear()
    return response


def _no_cache_response(response):
    response = make_response(response)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response
