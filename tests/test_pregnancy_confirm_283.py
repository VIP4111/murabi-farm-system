"""بند إضافي 283 — سؤالك الصريح عن النعاج "المشكوك في حملها": قبل هذا
البند، تسجيل حمل بخانة 'مؤكّد' فاضية كان يبقى بلا رجعة — ما فيه أي زر
يأكّده لاحقاً غير حذف السجل وإعادة تسجيله، ومادام غير مؤكَّد فهو غايب
تماماً عن عدّاد 'كم رأس حوامل لدينا' (context_service.pregnant_summary
تفحص confirmed=True حصراً)."""
from datetime import date

from app.extensions import db
from app.assistant import context_service
from app.models import Pregnancy
from factories import make_animal


def _unconfirmed_pregnancy(animal):
    p = Pregnancy(female_id=animal.id, date=date.today(), confirmed=False,
                  notes="مشكوك فيه — بانتظار تأكيد.")
    db.session.add(p)
    db.session.commit()
    return p


def test_unconfirmed_pregnancy_absent_from_pregnant_summary(app):
    ewe = make_animal(animal_no="PC-01", gender="أنثى")
    _unconfirmed_pregnancy(ewe)
    summary = context_service.pregnant_summary()
    assert summary["count"] == 0


def test_confirm_route_flips_status_and_enters_summary(app, logged_in_client):
    ewe = make_animal(animal_no="PC-02", gender="أنثى")
    p = _unconfirmed_pregnancy(ewe)

    resp = logged_in_client.post(f"/repro/pregnancies/{p.id}/confirm")
    assert resp.status_code == 302
    db.session.refresh(p)
    assert p.confirmed is True

    summary = context_service.pregnant_summary()
    assert summary["count"] == 1


def test_confirming_already_confirmed_pregnancy_rejected(app, logged_in_client):
    ewe = make_animal(animal_no="PC-03", gender="أنثى")
    p = Pregnancy(female_id=ewe.id, date=date.today(), confirmed=True)
    db.session.add(p)
    db.session.commit()

    resp = logged_in_client.post(f"/repro/pregnancies/{p.id}/confirm", follow_redirects=True)
    assert resp.status_code == 200
    assert "مؤكَّد أصلاً".encode() in resp.data


def test_confirm_button_shown_only_for_unconfirmed_rows(app, logged_in_client):
    ewe1 = make_animal(animal_no="PC-04", gender="أنثى")
    ewe2 = make_animal(animal_no="PC-05", gender="أنثى")
    unconfirmed = _unconfirmed_pregnancy(ewe1)
    confirmed = Pregnancy(female_id=ewe2.id, date=date.today(), confirmed=True)
    db.session.add(confirmed)
    db.session.commit()

    resp = logged_in_client.get("/repro/pregnancies")
    body = resp.data.decode()
    assert f'/repro/pregnancies/{unconfirmed.id}/confirm' in body
    assert f'/repro/pregnancies/{confirmed.id}/confirm' not in body
