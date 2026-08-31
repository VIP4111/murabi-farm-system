"""بند إضافي (2026-08-30) — استكمال جولة الترجمة: رسائل ValueError
اللي ترتفع من خدمات النظام (validation_service وغيرها) وتُعرض عبر
`flash(str(e), "error")` بالراوتات — الترجمة الصحيحة تصير عند مصدر
الرفع (`raise ValueError(_("..."))`) مو عند نقطة العرض، لأن `str(e)`
يجمّد النص وقت الرفع."""
from datetime import date

from app.extensions import db
from app.models import Role, User
from factories import make_barn


def _make_owner_en(phone="0599999270"):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="Owner EN Test", phone=phone, role_id=role.id, language="en")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    return user


def test_animal_creation_negative_price_error_translates_for_english_user(app, client):
    barn = make_barn(barn_no="VAL-01")
    owner = _make_owner_en()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.post("/animals/new", data={
        "animal_no": "VAL-ANIMAL-1", "source": "purchase", "gender": "أنثى",
        "barn_id": str(barn.id), "color": "أبيض", "price": "-50",
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "ما يقدر يكون رقماً سالباً" not in body
    assert "Price can" in body and "negative number" in body


def test_unrealistic_weight_error_translates_for_english_user(app, client):
    barn = make_barn(barn_no="VAL-02")
    owner = _make_owner_en(phone="0599999271")
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.post("/animals/new", data={
        "animal_no": "VAL-ANIMAL-2", "source": "purchase", "gender": "أنثى",
        "barn_id": str(barn.id), "color": "أبيض", "weight": "9999",
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "غير منطقي" not in body
    assert "unrealistic" in body


def test_report_accept_permission_error_translates_for_english_user(app, client):
    """بند إضافي (2026-08-31) — فئة سابعة: raise ReportPermissionError/
    ReportStateError (app/team/report_service.py) — نفس فئة ValueError
    فوق بالضبط، بس باستثناءات مخصَّصة ما كانت مغطاة بالبحث السابق."""
    from app.models import Report, Role
    from factories import make_animal

    role = Role.query.filter_by(name="worker").first()  # بدون reports.manage
    worker = User(name="Worker EN", phone="0599999272", role_id=role.id, language="en")
    worker.set_password("pass1234")
    db.session.add(worker)
    animal = make_animal(animal_no="RPT-EN-1")
    db.session.commit()
    report = Report(reporter_id=worker.id, description="test", animal_id=animal.id, status="new")
    db.session.add(report)
    db.session.commit()

    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})
    resp = client.post(f"/team/reports/{report.id}/accept", follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "ما تملك صلاحية إدارة البلاغات" not in body
    assert "manage-reports permission" in body


def test_sale_blocked_by_early_lifecycle_stage_translates_for_english_user(app, client):
    """بند إضافي (2026-08-31) — فحص أوسع لشاشة الدكتور: CycleExitBlocked
    (app/core/cycle_engine.py) كان استثناءً مخصَّصاً ثالثاً ما شمله أي
    بحث سابق (بعد ValueError وTaskStateError/ReportStateError) — يحجب
    بيع رأس لسا بمرحلة مبكرة من دورة الإنتاج."""
    from factories import make_animal

    owner = _make_owner_en(phone="0599999275")
    animal = make_animal(animal_no="VAL-SALE-1", price=500)
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})

    resp = client.post(f"/animals/{animal.id}/sell", data={
        "sale_price": "600", "sale_date": "", "notes": "",
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "لازم يوصل لمرحلة" not in body
    assert "must reach" in body or "before selling" in body


def test_isolation_exit_blocked_translates_for_english_user(app, client):
    """نفس الفئة، بس IsolationExitBlocked (app/core/isolation_service.py)."""
    from factories import make_animal, make_barn
    from app.core import isolation_service

    owner = _make_owner_en(phone="0599999276")
    isolation_barn = make_barn(barn_no="ISO-EN-1", barn_name="حظيرة عزل", barn_type="عزل")
    target_barn = make_barn(barn_no="TGT-EN-1", barn_name="حظيرة عادية")
    animal = make_animal(animal_no="VAL-ISO-1", barn_id=isolation_barn.id)
    animal.isolation_started_at = date.today()
    db.session.commit()

    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.post(f"/animals/{animal.id}/isolation/exit", data={
        "barn_id": str(target_barn.id), "date": date.today().isoformat(),
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "خروج مبكر من العزل" not in body
    assert "Early exit from isolation" in body or "early exit" in body.lower()


def test_task_start_not_assigned_error_translates_for_english_user(app, client, owner):
    """نفس الفئة، بس TaskPermissionError (app/team/task_service.py)."""
    from app.models import Role, Task
    from app.team import task_service

    role = Role.query.filter_by(name="worker").first()
    worker_a = User(name="Worker A", phone="0599999273", role_id=role.id, language="ar")
    worker_a.set_password("pass1234")
    worker_b = User(name="Worker B EN", phone="0599999274", role_id=role.id, language="en")
    worker_b.set_password("pass1234")
    db.session.add_all([worker_a, worker_b])
    db.session.commit()

    task = task_service.assign_task(actor=owner, title="مهمة اختبار", assignee_id=worker_a.id)

    client.post("/login", data={"phone": worker_b.phone, "password": "pass1234"})
    resp = client.post(f"/team/tasks/{task.id}/start", follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "هذي المهمة مو معيّنة لك" not in body
    assert "not assigned to you" in body
