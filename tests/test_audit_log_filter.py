"""بند إضافي 104 — فلترة شاشة سجل التدقيق (بند 34) بالتاريخ/المستخدم/
النوع. قبل هذا البند، الشاشة كانت تعرض آخر 200 حدث بس بدون أي فلترة."""
import re
from datetime import date, timedelta

from app.extensions import db
from app.models import AuditLog


def _log(action, days_ago=0, actor_user_id=None):
    entry = AuditLog(
        actor_user_id=actor_user_id, action=action, entity_type="Animal", entity_id=1,
        created_at=date.today() - timedelta(days=days_ago),
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def _table_actions(body: str) -> list[str]:
    # الجدول نفسه بس — يستثني قائمة الفلترة المنسدلة اللي تعرض كل
    # القيم الممكنة بغض النظر عن الفلترة الحالية. يلتقط أي نص (بند
    # إضافي 192 — الإجراء صار يُعرض بنص عربي مترجَم عبر `ar_audit_action`
    # بدل مفتاح الكود الخام، فما يبقى مطابقاً لـ`[\w.]+` وحده).
    return re.findall(r"<td>([^<]+)</td>", body)


def test_filter_by_action(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    _log("animal.sell")
    _log("task.delete")

    resp = client.get("/settings/audit?action=animal.sell")
    actions = _table_actions(resp.data.decode())
    assert "بيع حيوان" in actions
    assert "task.delete" not in actions


def test_filter_by_actor(app, client, owner, worker):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    _log("animal.sell", actor_user_id=owner.id)
    _log("task.fail", actor_user_id=worker.id)

    resp = client.get(f"/settings/audit?actor_user_id={worker.id}")
    actions = _table_actions(resp.data.decode())
    assert "تسجيل تعذّر مهمة" in actions
    assert "بيع حيوان" not in actions


def test_filter_by_date_range(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    _log("old.action", days_ago=10)
    _log("recent.action", days_ago=0)

    resp = client.get(f"/settings/audit?start={date.today() - timedelta(days=2)}&end={date.today()}")
    actions = _table_actions(resp.data.decode())
    assert "recent.action" in actions
    assert "old.action" not in actions


def test_no_filters_shows_all(app, client, owner):
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    _log("action.a")
    _log("action.b")

    resp = client.get("/settings/audit")
    actions = _table_actions(resp.data.decode())
    assert "action.a" in actions
    assert "action.b" in actions
