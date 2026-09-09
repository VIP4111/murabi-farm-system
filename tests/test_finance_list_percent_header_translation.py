"""بند إصلاح (فحص عميق فعلي — طلبك: "ارجع افحص التحجيم"، لقيته أثناء
تشغيل التطبيق حقيقي بالمتصفح وفحص شاشة المالية) — ترجمة عمود "% من
إجمالي الخارج" بكارت "ليش أنا بخسارة؟" كانت مكتوبة بملف .po الإنجليزي/
الأمهري/الهندي كعلامة `%` وحيدة غير مهروبة (`% of Total Outflow` بدل
`%% of Total Outflow`) — msgid الأصلي `"%% من إجمالي الخارج"` مُعلَّم
`#, python-format`، فـflask_babel/jinja2 يطبّق `rv % variables` على أي
ترجمة له بغض النظر عن وجود متغيرات فعلية. تسلسل " of" بعد `%` وحيدة
يتفسَّر بايثون كـflag مسافة + محول octal (`o`)، فيرمي
`TypeError: %o format: an integer is required` ويكسر الصفحة كاملة
(خطأ 500) لأي مستخدم لغته غير عربية يفتح شاشة المالية ووضع خسارة نشط."""
from datetime import date, timedelta

from app.extensions import db
from app.models import Role, User, Finance


def _english_owner():
    role = Role.query.filter_by(name="owner").first()
    u = User(name="EO", phone="0500099933", role_id=role.id, language="en")
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_finance_list_renders_without_error_for_english_user_with_loss(app, client):
    owner = _english_owner()
    # نخلق وضع خسارة حقيقي (خارج > داخل بآخر 30 يوم) عشان كارت "ليش أنا
    # بخسارة؟" يظهر فعلياً ويستدعي الترجمة المكسورة.
    today = date.today()
    db.session.add(Finance(date=today - timedelta(days=1), operation_type="expense",
                            category="راتب موظف", amount=5000))
    db.session.add(Finance(date=today - timedelta(days=2), operation_type="sale", amount=100))
    db.session.commit()
    _login = client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/finance/")
    assert resp.status_code == 200
    assert b"Total Outflow" in resp.data
