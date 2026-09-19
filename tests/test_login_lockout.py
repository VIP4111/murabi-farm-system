"""بند إضافي 86 — قفل بعد محاولات دخول فاشلة متكررة (نقطة أمنية جديدة
من التحليل الثاني). قبل هذا البند ما كان فيه أي حد لعدد المحاولات."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import User, ServiceToggle


def _fail_login(client, phone, password="wrong-password"):
    return client.post("/login", data={"phone": phone, "password": password})


def test_account_locks_after_five_failed_attempts(client, owner):
    for _ in range(User.LOCKOUT_THRESHOLD):
        _fail_login(client, owner.phone)

    db.session.refresh(owner)
    assert owner.failed_login_attempts == User.LOCKOUT_THRESHOLD
    assert owner.is_locked() is True


def test_locked_account_rejects_even_correct_password(client, owner):
    for _ in range(User.LOCKOUT_THRESHOLD):
        _fail_login(client, owner.phone)

    resp = client.post("/login", data={"phone": owner.phone, "password": "pass1234"}, follow_redirects=True)
    assert "مقفل مؤقتاً".encode() in resp.data
    # ما سُجّل دخول فعلياً
    resp2 = client.get("/team/members")
    assert resp2.status_code in (302, 403)


def test_successful_login_resets_failed_counter(client, owner):
    _fail_login(client, owner.phone)
    _fail_login(client, owner.phone)
    db.session.refresh(owner)
    assert owner.failed_login_attempts == 2

    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    db.session.refresh(owner)
    assert owner.failed_login_attempts == 0
    assert owner.locked_until is None


def test_lockout_expires_after_window(client, owner):
    owner.failed_login_attempts = User.LOCKOUT_THRESHOLD
    owner.locked_until = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)  # القفل انتهى فعلاً
    db.session.commit()

    resp = client.post("/login", data={"phone": owner.phone, "password": "pass1234"}, follow_redirects=False)
    assert resp.status_code == 302  # دخول ناجح


def test_lockout_message_reflects_actual_configured_minutes(client, owner):
    """بند إضافي (2026-08-30) — طلبك الصريح: "طلب منه الانتظار ١٥ دقيقه
    اريد جعلها دقيقه واحده". الرسالة كانت تقول "15 دقيقة" ثابتة بغض
    النظر عن LOCKOUT_MINUTES الفعلية — صارت تقرأ القيمة الحقيقية."""
    for _ in range(User.LOCKOUT_THRESHOLD):
        _fail_login(client, owner.phone)

    resp = client.post("/login", data={"phone": owner.phone, "password": "pass1234"}, follow_redirects=True)
    assert f"بعد {User.LOCKOUT_MINUTES} دقيقة".encode() in resp.data
    assert User.LOCKOUT_MINUTES == 1


def test_unknown_phone_number_does_not_error(client):
    resp = _fail_login(client, "0599999999")
    assert resp.status_code == 200


def test_attempt_on_locked_account_does_not_extend_failed_counter(client, owner):
    """بند إصلاح (فحص شامل لصفحة الدخول 2026-09) — إصلاح فرع "الحساب
    مقفل" (راجع الاختبار التالي) استلزم تحويله من `return` مبكّر إلى
    تكملة نفس تدفق الدالة (عشان يوصل لتذييل عرض خيارات الدخول السريع
    بالأسفل). هذا الاختبار يمنع رجوع خلل مستقبلي مرتبط بنفس التعديل:
    التأكد إن محاولة إضافية على حساب مقفل أصلاً (حتى بكلمة مرور صحيحة)
    ما تُسجَّل "فشل" جديد فوق القفل ولا تظهر رسالتان متعارضتان معاً."""
    for _ in range(User.LOCKOUT_THRESHOLD):
        _fail_login(client, owner.phone)
    db.session.refresh(owner)
    assert owner.failed_login_attempts == User.LOCKOUT_THRESHOLD

    # محاولة إضافية بكلمة مرور صحيحة أثناء القفل — يُفترض تُرفض بدون
    # ما تزيد عدّاد المحاولات الفاشلة.
    resp = client.post("/login", data={"phone": owner.phone, "password": "pass1234"}, follow_redirects=True)
    db.session.refresh(owner)
    assert owner.failed_login_attempts == User.LOCKOUT_THRESHOLD, \
        "محاولة على حساب مقفل ما لازم تزيد عدّاد المحاولات الفاشلة"

    # رسالة القفل فقط تظهر، مو رسالة "كلمة المرور غير صحيحة" معها
    assert "مقفل مؤقتاً".encode() in resp.data
    assert resp.data.count("رقم الجوال أو كلمة المرور غير صحيحة".encode()) == 0


def test_quick_login_box_still_shows_when_account_is_locked(client, owner):
    """بند إصلاح (فحص شامل لصفحة الدخول 2026-09) — كان فرع "الحساب
    مقفل" يرجّع `render_template("login.html")` مباشرة بدون تمرير
    `quick_login_accounts`، فلو وضع "الدخول السريع" مفعَّل من الإعدادات،
    صندوقه يختفي بصمت بالضبط باللحظة اللي فيها القفل — تناقض مع كل
    مسار ثاني بنفس الصفحة اللي يعرضه دايماً. صار الفرع يكمل لنفس تذييل
    الدالة اللي يجهّز `quick_login_accounts` بدل الرجوع المبكر."""
    toggle = ServiceToggle(key="dev_quick_login", name="تسجيل دخول سريع (وضع تجربة)", is_enabled=True)
    db.session.add(toggle)
    db.session.commit()

    for _ in range(User.LOCKOUT_THRESHOLD):
        _fail_login(client, owner.phone)

    resp = client.post("/login", data={"phone": owner.phone, "password": "pass1234"}, follow_redirects=True)
    assert "مقفل مؤقتاً".encode() in resp.data
    assert owner.name.encode() in resp.data, "صندوق الدخول السريع لازم يظل ظاهراً حتى لو الحساب المطلوب مقفل"
