"""اختبار بند الفحص العميق (دفعة ثانية): نتيجة فحص السونار
(SonarResult.result) تُخزَّن كنص عربي خام ("حامل"/"غير حامل"/
"غير مؤكد") وما كانت تمر على gettext بشاشتي عرضها (تفاصيل الحيوان
وتفاصيل برنامج الشياع التوأمي)، فتبقى عربي دائماً حتى لمستخدم لغته
إنجليزي — نفس فئة خلل Egg.quality المُصلَح سابقاً بالكوميت 347884c.
الاختبار يفعّل مستخدم بلغة إنجليزية عشان يتأكد إن الترجمة تشتغل
فعلياً (مو بس النص العربي الخام يطلع صدفة بأي لغة)."""
from datetime import date

from app.extensions import db
from app.models import Role, User
from app.models.repro import SonarResult, TwinEstrusProgram
from tests.factories import make_animal, make_barn


def _make_english_client(client, app):
    role = Role.query.filter_by(name="owner").first()
    user = User(name="English Owner", phone="0500000099", role_id=role.id, language="en")
    user.set_password("pass1234")
    db.session.add(user)
    db.session.commit()
    client.post("/login", data={"phone": user.phone, "password": "pass1234"})
    return client


def test_animal_detail_translates_sonar_result_to_english(client, app):
    en_client = _make_english_client(client, app)
    barn = make_barn()
    ewe = make_animal(animal_no="E-01", gender="أنثى", barn_id=barn.id)
    sonar = SonarResult(ewe_id=ewe.id, exam_date=date(2026, 1, 1), result="حامل")
    db.session.add(sonar)
    db.session.commit()

    resp = en_client.get(f"/animals/{ewe.id}")
    assert resp.status_code == 200
    assert b"Pregnant" in resp.data
    assert "حامل".encode() not in resp.data


def test_program_detail_translates_sonar_result_to_english(client, app):
    en_client = _make_english_client(client, app)
    barn = make_barn()
    ewe = make_animal(animal_no="E-02", gender="أنثى", barn_id=barn.id)
    program = TwinEstrusProgram(ewe_id=ewe.id, protocol_name="بروتوكول اختبار", start_date=date(2026, 1, 1))
    db.session.add(program)
    db.session.commit()
    sonar = SonarResult(program_id=program.id, ewe_id=ewe.id, exam_date=date(2026, 1, 1), result="غير مؤكد")
    db.session.add(sonar)
    db.session.commit()

    resp = en_client.get(f"/repro/programs/{program.id}")
    assert resp.status_code == 200
    assert b"Unconfirmed" in resp.data
    assert "غير مؤكد".encode() not in resp.data


def test_sonar_list_translates_sonar_result_to_english(client, app):
    en_client = _make_english_client(client, app)
    barn = make_barn()
    ewe = make_animal(animal_no="E-03", gender="أنثى", barn_id=barn.id)
    sonar = SonarResult(ewe_id=ewe.id, exam_date=date(2026, 1, 1), result="غير حامل")
    db.session.add(sonar)
    db.session.commit()

    resp = en_client.get("/repro/sonar")
    assert resp.status_code == 200
    assert b"Not pregnant" in resp.data
    assert "غير حامل".encode() not in resp.data
