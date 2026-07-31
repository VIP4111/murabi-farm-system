"""بند إضافي 74 — أول اختبار آلي حقيقي يتأكد إن شاشات العامل (المهام،
البلاغات، التنبيهات) فعلاً تترجم للأمهرية بدل ما تطلع عربي دايماً. قبل
هذا البند ما كان فيه أي اختبار يتحقق من الترجمة الفعلية بالمتصفح —
بند 44 اتّكل على تحقق يدوي بس، وهذا بالضبط سبب تسرّب النصوص العربية
اللي لاحظها المستخدم."""
from app.extensions import db
from app.models import Role, User


def _make_worker_with_language(lang):
    role = Role.query.filter_by(name="worker").first()
    user = User(name="عامل أمهري", phone="0500000099", role_id=role.id, language=lang)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def _make_doctor_with_language(lang):
    role = Role.query.filter_by(name="doctor").first()
    user = User(name="دكتور أمهري", phone="0500000098", role_id=role.id, language=lang)
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_tasks_list_translated_for_amharic_worker(app, client):
    worker = _make_worker_with_language("am")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/team/tasks")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "ተግባራት" in body  # المهام
    assert "ተግባሮቼ" in body  # مهامي


def test_tasks_list_translated_for_hindi_worker(app, client):
    worker = _make_worker_with_language("hi")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/team/tasks")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "कार्य" in body
    assert "मेरे कार्य" in body


def test_reports_list_translated_for_amharic_worker(app, client):
    worker = _make_worker_with_language("am")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/team/reports")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "ሪፖርቶች" in body  # البلاغات


def test_alerts_mine_translated_for_amharic_worker(app, client):
    worker = _make_worker_with_language("am")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/alerts/mine")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "ማንቂያዎቼ" in body  # تنبيهاتي


def test_task_type_and_status_labels_translate_with_locale(app, client):
    """STATUS_LABELS_AR/TASK_TYPE_LABELS_AR بند 74 صارت _l() — يجب
    تترجم فعلياً لما تُعرض بصفحة بلغة غير عربية، مو بس تبقى عربي دايماً.
    المهام اليومية تولّد "مقترحة" بدون تعيين — قسم "مهام مقترحة" يحتاج
    صلاحية tasks.review_daily، فمستخدم الاختبار دكتور مو عامل."""
    from app.core import daily_task_service
    doctor = _make_doctor_with_language("am")
    daily_task_service.generate_daily_husbandry_tasks()
    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.get("/team/tasks")
    body = resp.data.decode()
    assert "daily_husbandry" not in body
    assert "ዕለታዊ እንክብካቤ" in body  # رعاية يومية بالأمهرية


def test_report_form_english_still_carries_arabic_report_type_value(app, client):
    """قيمة report_type المخزّنة تبقى عربي دايماً (سبب الفلترة/البحث)،
    الترجمة تطال العرض بس — تأكيد إن select option value ما تغيّر."""
    worker = _make_worker_with_language("en")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.get("/team/reports/new")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert 'value="مرض"' in body
    assert ">Disease<" in body
