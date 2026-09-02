"""طلب صريح: "حاول تدخل على كل زر وبعدها أضف" — استكمال فقعات الشرح
لشاشة تفاصيل المهمة (زر "بدء" وزر "تأكيد التنفيذ")."""
from tests.factories import make_animal
from app.extensions import db
from app.models import Task


def test_task_detail_has_start_button_tip(app, logged_in_client, owner):
    t = Task(title="مهمة اختبار الفقعات", task_type="custom", status="pending", assignee_id=owner.id)
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get(f"/team/tasks/{t.id}")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert 'class="info-tip"' in body
