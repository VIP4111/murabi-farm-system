"""اختبارات إعادة تصميم جداول شاشة المهام (بند إضافي 71): جدول مدمج،
هيدر واحد ملوّن، وأزرار إجراءات صغيرة أفقية بدل الكروت الضخمة."""
from app.extensions import db
from app.models import Task


def test_tasks_page_uses_compact_table_class(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks")
    assert resp.status_code == 200
    assert b'class="compact-table"' in resp.data


def test_compact_table_css_defines_header_and_row_styles(app, logged_in_client):
    resp = logged_in_client.get("/team/tasks")
    body = resp.data.decode("utf-8")
    assert "table.compact-table thead th" in body
    assert "table.compact-table td.actions-col" in body


def test_suggested_task_row_has_thead_tbody_structure(app, logged_in_client):
    t = Task(title="مهمة تصميم جدول 71", task_type="custom", status="suggested")
    db.session.add(t)
    db.session.commit()

    resp = logged_in_client.get("/team/tasks")
    body = resp.data.decode("utf-8")
    # يتأكد إن الهيدر (thead) يسبق صف المهمة (tbody) بترتيب صحيح بالـHTML
    thead_idx = body.index("مهام مقترحة بانتظار الاعتماد")
    window = body[thead_idx:thead_idx + 1200]
    assert "<thead>" in window
    assert "<tbody>" in window
    assert window.index("<thead>") < window.index("<tbody>")
