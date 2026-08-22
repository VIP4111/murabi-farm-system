"""بند إضافي 234 — سبب حقيقي لتقرير "الوضع الليلي غير متناسق، طالع
أبيض": صفحة "اليوم" (وقوالب ثانية) كانت تستخدم style="..." مباشر بشرط
Jinja لتلوين الصف المتأخر/التحذير — الـinline style يتغلّب على أي قاعدة
CSS مهما كانت، حتى لو الوضع الليلي مفعَّل صح وقاعدة CSS الليلية موجودة
وصحيحة. الإصلاح: كلاسات ثابتة (notice-danger/notice-success/row-danger)
لها نسخة نهارية وليلية بـbase.html، بدل تكرار اللون كـstyle مباشر."""
from datetime import date, timedelta

from app.extensions import db
from tests.factories import make_animal, make_barn
from app.models import Task


def test_today_overdue_task_uses_css_class_not_inline_color(app, logged_in_client, owner):
    barn = make_barn()
    task = Task(title="مهمة متأخرة", task_type="custom", status="pending",
                assignee_id=owner.id, barn_id=barn.id,
                due_date=date.today() - timedelta(days=3))
    db.session.add(task)
    db.session.commit()

    resp = logged_in_client.get("/today")
    body = resp.data.decode()
    assert "timeline-row urgent" in body
    row_start = body.index("مهمة متأخرة")
    row_snippet = body[max(0, row_start - 200):row_start]
    assert "background:#fff5f2" not in row_snippet, "لازم الصف يستخدم كلاس urgent بدل تلوين مباشر يكسر الوضع الليلي"


def test_today_non_overdue_task_has_no_urgent_class(app, logged_in_client, owner):
    barn = make_barn()
    task = Task(title="مهمة عادية", task_type="custom", status="pending",
                assignee_id=owner.id, barn_id=barn.id,
                due_date=date.today() + timedelta(days=3))
    db.session.add(task)
    db.session.commit()

    resp = logged_in_client.get("/today")
    body = resp.data.decode()
    assert "مهمة عادية" in body
    assert "timeline-row urgent" not in body


def test_no_inline_theme_breaking_colors_left_in_templates():
    """فحص وقائي — أي إضافة مستقبلية بنفس نمط الخطأ تفشل هذا الاختبار
    فوراً بدل ما تنتظر بلاغ مستخدم بعد أسابيع."""
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parent.parent / "app" / "templates"
    offenders = []
    pattern = re.compile(r"style=[\"'][^\"']*(#fff5f2|#f0f9f0|#f2fbf5)")
    for path in root.rglob("*.html"):
        if path.name == "base.html":
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"قوالب فيها تلوين مباشر يكسر الوضع الليلي: {offenders}"
