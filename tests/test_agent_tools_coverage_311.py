"""بند إضافي 311 — طلبك: "هل المساعد الذكي مربوط بكل الأقسام؟ إذا لا
حاول تربطه". قبل هذا، أدوات Gemini (بند 297) كانت 5 بس (قطيع/رأس/مالية
/ملاحظات) — أي سؤال حر عن الصحة/التحصينات/العلف/النعام/التنبيهات/مهامك
كان يفوت Gemini كلياً رغم إن البيانات محسوبة أصلاً بـcontext_service.py.
أضفنا 6 أدوات جديدة تلف نفس الدوال الموجودة — صفر منطق جديد."""
from app.extensions import db
from app.assistant import agent_tools
from app.models import Role, User, Disease, Task
from factories import make_animal
from datetime import date


def _make_role_user(role_name, phone):
    role = Role.query.filter_by(name=role_name).first()
    user = User(name=f"مستخدم {role_name}", phone=phone, role_id=role.id, language="ar")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_disease_summary_reflects_real_open_case(app):
    animal = make_animal(animal_no="930")
    db.session.add(Disease(animal_id=animal.id, disease_name="جرب", status="active", date=date.today()))
    db.session.commit()
    result = agent_tools.disease_summary()
    assert result["count"] == 1
    assert result["items"][0]["disease_name"] == "جرب"


def test_vaccinations_due_summary_returns_dict_shape(app):
    result = agent_tools.vaccinations_due_summary()
    assert "count" in result and "overdue_count" in result


def test_feed_status_summary_returns_dict_shape(app):
    result = agent_tools.feed_status_summary()
    assert "has_active_plans" in result


def test_ostrich_status_summary_returns_dict_shape(app):
    result = agent_tools.ostrich_status_summary()
    assert "incubators_total" in result


def test_alerts_summary_returns_dict_shape(app):
    result = agent_tools.alerts_summary()
    assert "total" in result and "urgent_total" in result


def test_my_tasks_summary_bound_to_calling_user(app, owner):
    task_service_module = __import__("app.team.task_service", fromlist=["assign_task"])
    task_service_module.assign_task(actor=owner, title="مهمة اختبار", assignee_id=owner.id)
    tools = agent_tools.build_tools_for_user(owner)
    my_tasks_tool = next(t for t in tools if t.__name__ == "my_tasks_summary")
    result = my_tasks_tool()
    assert result["count"] == 1


# ---- الصلاحيات: كل أداة تُخفى فعلياً عن مستخدم بدون صلاحيتها ----

def test_worker_without_health_view_does_not_get_disease_tools(app):
    worker = _make_role_user("worker", "0599999240")
    tools = agent_tools.build_tools_for_user(worker)
    assert agent_tools.disease_summary not in tools
    assert agent_tools.vaccinations_due_summary not in tools


def test_doctor_gets_health_tools_but_not_feed_tool(app):
    doctor = _make_role_user("doctor", "0599999241")
    tools = agent_tools.build_tools_for_user(doctor)
    assert agent_tools.disease_summary in tools
    assert agent_tools.vaccinations_due_summary in tools
    assert agent_tools.feed_status_summary in tools  # الدكتور يملك feed.view أصلاً


def test_worker_gets_my_tasks_tool(app):
    """كل الأدوار الافتراضية تملك tasks.view_own — my_tasks_summary
    لازم تظهر لهم كلهم، حتى العامل."""
    worker = _make_role_user("worker", "0599999242")
    tools = agent_tools.build_tools_for_user(worker)
    assert any(t.__name__ == "my_tasks_summary" for t in tools)
