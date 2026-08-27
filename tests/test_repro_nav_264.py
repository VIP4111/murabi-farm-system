"""بند إضافي 264 — بمتابعة المراجعة المنهجية (نفس خلل بند 252/258/
262/263) بقسم "التكاثر". راجعت الجانب المالي كمان (لا يوجد تكلفة/سعر
بالتكاثر إطلاقاً — لا فجوة مشابهة لبند 259/261/263 ممكنة هنا)."""
from datetime import date

from app.extensions import db
from factories import make_animal


def _drawer_open(html: str) -> bool:
    idx = html.find(">الحيوانات<")
    assert idx != -1
    details_idx = html.rfind("<details", 0, idx)
    return " open" in html[details_idx:idx]


def test_animals_drawer_stays_open_on_sires_list(app, logged_in_client):
    resp = logged_in_client.get("/repro/sires")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_matings_new(app, logged_in_client):
    resp = logged_in_client.get("/repro/matings/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_pregnancies_new(app, logged_in_client):
    resp = logged_in_client.get("/repro/pregnancies/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_sonar_new(app, logged_in_client):
    resp = logged_in_client.get("/repro/sonar/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_programs_new(app, logged_in_client):
    resp = logged_in_client.get("/repro/programs/new")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())


def test_animals_drawer_stays_open_on_program_detail(app, logged_in_client):
    from app.models import TwinEstrusProgram
    ewe = make_animal(animal_no="RP-01", gender="أنثى")
    program = TwinEstrusProgram(ewe_id=ewe.id, start_date=date.today())
    db.session.add(program)
    db.session.commit()
    resp = logged_in_client.get(f"/repro/programs/{program.id}")
    assert resp.status_code == 200
    assert _drawer_open(resp.data.decode())
