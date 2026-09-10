"""بند إصلاح — طلبك المباشر: "طبّق على الواقع" بعد نموذج "بلاطات مراح"
التجريبي (تصميم بلاطات ملوّنة واضحة زي دكسيف، لكن بهوية مراح بوعلي
وألوان أهدأ). طُبِّق على الصفحة الرئيسية الحقيقية:
- شريط إحصائيات مدمجة (رقم + وصفه جوّا نفس المربع الملوّن) من بيانات
  حقيقية موجودة أصلاً (today_tasks_count/today_alerts_count/
  animals_alerts_count) — صفر رقم مخترع.
- كل بلاطة بقسم "إجراءات سريعة" صار لها لون ثابت مميّز حسب فئتها."""
from app.extensions import db
from app.models import Role, User


def _english_owner():
    role = Role.query.filter_by(name="owner").first()
    u = User(name="EO", phone="0500099955", role_id=role.id, language="en")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_home_shows_merged_stat_chips_and_colored_tiles(app, client):
    owner = _english_owner()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode()
    # شريط الإحصائيات المدمجة — الترجمة الإنجليزية للتسميات الجديدة
    assert "Today's tasks" in html
    assert "Today's alerts" in html
    # الألوان — كل تصنيف له متغيّر CSS ثابت مستخدَم فعلياً بالقالب
    assert "var(--t-animals)" in html
    assert "var(--t-health)" in html
    assert "var(--t-team)" in html
    # صفر تغيير على الروابط الفعلية (السلوك الوظيفي القديم يبقى كما هو)
    assert 'href="/team/tasks"' in html
    assert 'href="/animals"' in html


def test_home_stats_strip_hidden_when_no_data_available(app, client):
    # عامل بلا animals.view/tasks.view_own يشوف worker_home.html منفصلة
    # أصلاً (بند 27) — هذا الاختبار يتأكد إن شريط الإحصائيات الجديد ما
    # يطيح الصفحة لأي حالة صلاحيات ناقصة (كل شرط `is not none`).
    from app.models import Role as R
    role = R.query.filter_by(name="worker").first()
    u = User(name="W", phone="0500099956", role_id=role.id, language="en")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    client.post("/login", data={"phone": u.phone, "password": "pass1234"})
    resp = client.get("/")
    assert resp.status_code == 200
