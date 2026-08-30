"""اختبارات تصحيحات شاشة المهام (بند إضافي 66): ترجمة نوع المهمة لعربي
بدل النص الخام، حقل التاريخ RTL، ومحاذاة الأزرار."""
def test_daily_husbandry_type_shows_arabic_label_not_raw_string(app, logged_in_client):
    from app.core import daily_task_service
    daily_task_service.generate_daily_husbandry_tasks()
    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    assert b"daily_husbandry" not in resp.data
    assert "رعاية يومية".encode() in resp.data


def test_ar_task_type_filter_maps_known_values(app):
    # قيم TASK_TYPE_LABELS_AR صارت _l() (بند إضافي 74) — تحتاج سياق طلب
    # حقيقي عشان تُحسم للغة (select_locale يقرأ session/current_user).
    filt = app.jinja_env.filters["ar_task_type"]
    with app.test_request_context():
        assert filt("daily_husbandry") == "رعاية يومية"
        assert filt("move_to_pregnant_barn") == "نقل لحظيرة الحوامل"
        assert filt("batch_spray") == "رش وقائي (دفعة)"


def test_ar_task_type_filter_falls_back_to_raw_value_for_unknown_type(app):
    filt = app.jinja_env.filters["ar_task_type"]
    assert filt("some_future_type_not_mapped_yet") == "some_future_type_not_mapped_yet"


# ---- بند إضافي (2026-08-30) — بلاغك: "التنبيهات والمهام طلعت عند
# الدكتور بالعربي" (الدكتور مسجَّل إنجليزي). السبب الجذري: عنوان
# المهمة (Task.title) نص عربي خام يُخزَّن حرفياً وقت الإنشاء بعشرات
# الأماكن، وما فيه طريقة يترجم لاحقاً. الحل: إعادة بناء العنوان
# المعروض وقت العرض من task_type (له ترجمة جاهزة) + رقم الحيوان/اسم
# الحظيرة (بيانات محايدة لغوياً)، بدل الاعتماد على title الخام.

def test_task_display_title_uses_translatable_type_label_and_animal_no(app):
    from factories import make_animal
    from app.extensions import db
    from app.models import Task

    animal = make_animal(animal_no="TDL-01")
    t = Task(title="🩺 مراجعة الدكتور — TDL-01", task_type="doctor_review",
              status="pending", animal_id=animal.id)
    db.session.add(t)
    db.session.commit()

    task_display_title = app.jinja_env.globals["task_display_title"]
    with app.test_request_context():
        assert task_display_title(t) == "مراجعة الدكتور — TDL-01"


def test_task_display_title_switches_language_with_viewer_setting(app):
    """أهم فحص: نفس المهمة بالضبط، لغتين مختلفتين — العنوان المعروض
    يتغيّر فعلياً، عكس السلوك القديم (title خام ثابت بكل اللغات)."""
    from factories import make_animal
    from app.extensions import db
    from app.models import Task, Role, User

    animal = make_animal(animal_no="TDL-02")
    t = Task(title="أي نص عربي قديم", task_type="doctor_review",
              status="pending", animal_id=animal.id)
    db.session.add(t)
    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="دكتور إنجليزي", phone="0599999280", role_id=role.id, language="en")
    doctor.set_password("pass1234")
    db.session.add(doctor)
    db.session.commit()

    from flask_login import login_user
    task_display_title = app.jinja_env.globals["task_display_title"]
    with app.test_request_context():
        login_user(doctor)
        result_en = task_display_title(t)
    assert result_en == "Doctor review — TDL-02"
    assert result_en != "أي نص عربي قديم"


def test_task_display_title_keeps_raw_title_for_custom_type(app):
    """نوع "custom" نص حر كتبه إنسان بنفسه — يبقى كما هو، بدون أي
    استبدال (نفس منطق عدم ترجمة اسم الحظيرة/الحيوان)."""
    from app.extensions import db
    from app.models import Task

    t = Task(title="اطعم الحيوانات بدري اليوم", task_type="custom", status="pending")
    db.session.add(t)
    db.session.commit()

    task_display_title = app.jinja_env.globals["task_display_title"]
    with app.test_request_context():
        assert task_display_title(t) == "اطعم الحيوانات بدري اليوم"


def test_task_display_title_keeps_raw_title_for_daily_husbandry_type(app):
    """خلل حقيقي لقيناه أثناء الاختبار: كل قواعد المهام اليومية
    (`DailyTaskTemplate`, قابلة للتعديل من الواجهة) تشترك بنفس
    task_type="daily_husbandry" الواحد — التمييز الفعلي بينها (تنظيف
    مقابل سقاية مقابل فحص) موجود بـtitle نفسه بس. استبداله بترجمة
    عامة واحدة "رعاية يومية" يفقد المعلومة الفعلية بدل ما يترجمها،
    فهذا النوع مستثنى عمداً مثل custom بالضبط."""
    from app.extensions import db
    from app.models import Task

    t = Task(title="🧹 تنظيف المعالف والحظائر", task_type="daily_husbandry", status="pending")
    db.session.add(t)
    db.session.commit()

    task_display_title = app.jinja_env.globals["task_display_title"]
    with app.test_request_context():
        assert task_display_title(t) == "🧹 تنظيف المعالف والحظائر"


def test_team_tasks_page_shows_translated_title_for_english_doctor(app, client):
    """فحص طرف-لطرف: دكتور لغته إنجليزي يفتح شاشة المهام — العنوان
    يطلع مترجم فعلياً، مو عربياً خاماً كما كان يحصل قبل الإصلاح."""
    from factories import make_animal
    from app.extensions import db
    from app.models import Task, Role, User

    animal = make_animal(animal_no="TDL-03")
    t = Task(title="عنوان عربي خام قديم", task_type="isolation_check",
              status="pending", assignee_id=None, animal_id=animal.id)
    db.session.add(t)
    role = Role.query.filter_by(name="doctor").first()
    doctor = User(name="Dr English", phone="0599999281", role_id=role.id, language="en")
    doctor.set_password("pass1234")
    db.session.add(doctor)
    db.session.commit()
    t.assignee_id = doctor.id
    db.session.commit()

    client.post("/login", data={"phone": doctor.phone, "password": "pass1234"})
    resp = client.get("/team/tasks")
    assert resp.status_code == 200
    body = resp.data.decode()
    # ملاحظة صادقة: النص العربي الخام لسا يظهر بمكان ثانٍ منفصل تماماً
    # بهذي الصفحة (قائمة "مهمة سابقة" المنسدلة بفورم توزيع مهمة جديدة
    # — تعرض كل المهام بعناوينها الخام لاختيار الترتيب) — خارج نطاق
    # هذا الإصلاح (جدول المهام نفسه)، ما فحصناه هنا عمداً.
    assert "Isolation check" in body


def test_tasks_list_page_has_no_broken_date_input_direction(app, logged_in_client):
    """يتأكد إن قاعدة CSS الجديدة لحقول التاريخ موجودة فعلاً بالصفحة
    (بند 66) — التحقق الفعلي من اتجاه العرض بالمتصفح صار حياً بمتصفح
    فعلي أثناء التطوير، هذا اختبار وجود القاعدة بس."""
    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    assert b'input[type="date"]' in resp.data
    assert b"direction:ltr" in resp.data
