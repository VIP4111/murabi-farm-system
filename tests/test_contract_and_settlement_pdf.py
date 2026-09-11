"""بند إضافي — طلبك: "1- طباعة اتفاقية عمل  2- مخالصه في حال اختيار
السفر بشكل نهائي"، ثم "كل مسمى وظيفي له بنود تختلف... ابيك تبنيها
وتعطيني صلاحيه في تعديل على البنود فيما بعد".

يغطي:
- نماذج بنود العقد (CRUD) قابلة للتعديل من الإعدادات، مبذورة بـ4
  مسميات افتراضية (عامل زراعي/راعي، سائق، عامل منزلي، عامل مقاولات).
- طباعة اتفاقية عمل PDF فعلية تستخدم بنود النموذج المختار.
- طباعة إقرار مخالصة نهائية PDF فيه تعهد باستلام المستحقات + الموافقة
  على تنظيف البيانات، بمبالغ تُدخَل يدوياً وقت الطباعة."""
from app.extensions import db
from app.models import ContractTemplate, Role, User


def _new_worker(job_title=None):
    role = Role.query.filter_by(name="worker").first()
    u = User(name="عامل تجريبي", phone="0500055501", role_id=role.id, job_title=job_title)
    u.set_password("pass1234")
    db.session.add(u)
    db.session.commit()
    return u


def test_contract_templates_seeded_with_four_default_job_titles(app, logged_in_client):
    resp = logged_in_client.get("/settings/contract-templates")
    assert resp.status_code == 200
    templates = ContractTemplate.query.all()
    job_titles = {t.job_title for t in templates}
    assert "سائق" in job_titles
    assert "عامل منزلي" in job_titles


def test_contract_templates_crud(app, logged_in_client):
    resp = logged_in_client.post("/settings/contract-templates/new", data={
        "job_title": "عامل مخازن",
        "clauses_text": "بند تجريبي أول.\nبند تجريبي ثاني.",
    }, follow_redirects=True)
    assert resp.status_code == 200
    tmpl = ContractTemplate.query.filter_by(job_title="عامل مخازن").first()
    assert tmpl is not None

    resp = logged_in_client.post(f"/settings/contract-templates/{tmpl.id}/edit", data={
        "job_title": "عامل مخازن",
        "clauses_text": "بند معدَّل.",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(tmpl)
    assert tmpl.clauses_text == "بند معدَّل."

    resp = logged_in_client.post(f"/settings/contract-templates/{tmpl.id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert ContractTemplate.query.filter_by(job_title="عامل مخازن").first() is None


def test_contract_print_generates_real_pdf(app, logged_in_client):
    worker = _new_worker(job_title="سائق")
    logged_in_client.get("/settings/contract-templates")  # يبذر النماذج الافتراضية
    tmpl = ContractTemplate.query.filter_by(job_title="سائق").first()

    resp = logged_in_client.get(f"/team/members/{worker.id}/contract/print?template_id={tmpl.id}")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:4] == b"%PDF"


def test_contract_print_without_template_id_shows_selection_page(app, logged_in_client):
    worker = _new_worker()
    resp = logged_in_client.get(f"/team/members/{worker.id}/contract/print")
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"


def test_settlement_form_page_loads(app, logged_in_client):
    worker = _new_worker()
    resp = logged_in_client.get(f"/team/members/{worker.id}/settlement/print")
    assert resp.status_code == 200
    assert "المخالصة" in resp.get_data(as_text=True)


def test_settlement_print_generates_real_pdf_with_pledge_amounts(app, logged_in_client):
    worker = _new_worker()
    resp = logged_in_client.post(f"/team/members/{worker.id}/settlement/print", data={
        "last_work_day": "2026-09-10",
        "reason": "سفر نهائي",
        "final_salary": "1500",
        "end_of_service": "800",
        "leave_balance": "0",
        "deductions": "0",
    })
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:4] == b"%PDF"


def test_employer_identity_prefers_external_sponsor_over_farm_owner(app, logged_in_client):
    """بند إصلاح (طلبك: "هل مسجّل تحت كفالة صاحب الحلال... ولا عنده
    كفيل خارجي") — نفس منطق `resolve_payslip_employer` الموجود أصلاً
    لمسير الراتب، مطبَّق هنا أيضاً على اتفاقية العمل ومستند المخالصة."""
    worker = _new_worker(job_title="سائق")
    worker.sponsor_name = "عبدالله الحربي"
    db.session.commit()
    logged_in_client.get("/settings/contract-templates")
    tmpl = ContractTemplate.query.filter_by(job_title="سائق").first()

    from app.reports.export_service import resolve_payslip_employer
    from app.models import FarmSettings
    with app.app_context():
        name, _nid, _phone = resolve_payslip_employer(worker, FarmSettings.get())
        assert name == "عبدالله الحربي"

    resp = logged_in_client.get(f"/team/members/{worker.id}/contract/print?template_id={tmpl.id}")
    assert resp.status_code == 200
    assert resp.data[:4] == b"%PDF"
