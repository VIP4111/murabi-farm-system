"""بند إضافي 123 — تبسيط لوحة صاحب الحلال/الدكتور/الممرض/المحاسب
(home.html): مجموعات مصنَّفة بدل شبكة إجراءات سريعة واحدة مسطّحة، وبطاقة
"صفحة اليوم" وحيدة بدل بطاقتي "مهامي"/"التنبيهات" المكرّرتين."""
from app.extensions import db
from app.models import Role, User


def _login_as(client, phone, password="pass1234"):
    return client.post("/login", data={"phone": phone, "password": password})


def _make_owner():
    role = Role.query.filter_by(name="owner").first()
    user = User(name="مالك اختبار الواجهة", phone="0599999124", role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_owner_home_shows_grouped_quick_actions_not_flat_list(app, client):
    owner = _make_owner()
    _login_as(client, owner.phone)
    resp = client.get("/")
    body = resp.data.decode()
    assert "quick-group-title" in body
    assert "الأكثر استخدامًا" in body
    assert "الصحة" in body
    assert "النظام" in body


def test_owner_home_has_single_today_card_not_duplicate_tasks_alerts_cards(app, client):
    owner = _make_owner()
    _login_as(client, owner.phone)
    resp = client.get("/")
    body = resp.data.decode()
    assert 'href="/today"' in body
    # القسمين القديمين "مهامي" و"التنبيهات" المستقلين اختفيا لصالح بطاقة واحدة
    assert "فتح صفحة المهام" not in body
    assert "فتح كل التنبيهات" not in body
