"""بند إضافي 206 — طلبك: (1) بطاقة "صفحة اليوم" بالرئيسية تعرض عدد
المهام المطلوبة وعدد التنبيهات كأرقام بدل وصف عام، و(2) ألوان المساعد
الذكي بالوضع الداكن غير مقروءة — سببها الحقيقي إن `.bubble.assistant`
و`.chat-foot` و`.chat-suggestions button` استخدمت خلفية بيضاء ثابتة
(#fff/#fbf8f1) مع `color:var(--text)`/`var(--primary)` اللي تتحوّل
لألوان فاتحة بالوضع الداكن (مخصَّصة أصلاً للكتابة فوق خلفيات داكنة)
— نص فاتح فوق خلفية بيضاء ثابتة يصير شبه غير مرئي. الحل: استبدال
الخلفيات الثابتة بـ`var(--card)` اللي تتحوّل صح مع الثيم."""
from app.extensions import db
from app.models import Role, User, Task


def _make_owner(phone="0599999190"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك اختبار لوحة اليوم", phone=phone, role_id=role.id, language="ar")
    user.set_password("test1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_home_shows_zero_tasks_badge_when_nothing_pending(app, client):
    owner = _make_owner()
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/")
    body = resp.data.decode()
    assert "كل شي مضبوط اليوم" in body


def test_home_shows_task_count_badge_when_tasks_pending(app, client):
    owner = _make_owner(phone="0599999191")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    db.session.add(Task(title="مهمة اختبار لوحة اليوم", status="pending",
                         target_role="owner", assignee_id=owner.id))
    db.session.commit()
    resp = client.get("/")
    body = resp.data.decode()
    assert "1 مهمة مطلوبة" in body


def test_home_tasks_badge_is_a_shortcut_button(app, client):
    """بند إضافي 279 — طلبك الصريح: "المهام والتنبيهات ابيها تكون
    تفاعلية حولها الى زر" — البطاقة بالرئيسية، مو بس شاشة /today."""
    owner = _make_owner(phone="0599999192")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    db.session.add(Task(title="مهمة اختبار زر الرئيسية", status="pending",
                         target_role="owner", assignee_id=owner.id))
    db.session.commit()
    resp = client.get("/")
    body = resp.data.decode()
    assert 'href="/team/tasks"' in body


def test_chat_page_does_not_use_hardcoded_white_backgrounds(app, client):
    """التأكد إن الإصلاح فعلي بالملف الحي، مو بس بالنية — hardcoded
    #fff/#fbf8f1 كانت السبب المباشر لعدم وضوح الألوان بالوضع الداكن."""
    owner = _make_owner(phone="0599999192")
    client.post("/login", data={"phone": owner.phone, "password": "test1234"})
    resp = client.get("/assistant/")
    body = resp.data.decode()
    assert "background:#fff; border:1px solid var(--line); color:var(--text)" not in body
    assert "border-top:1px solid var(--line); background:#fbf8f1" not in body
    assert 'background:var(--card); border:1px solid var(--line); color:var(--text)' in body
    assert 'border-top:1px solid var(--line); background:var(--card)' in body
