"""بند إصلاح — نفس فئة فجوات الترجمة الأصلية بهذي الجلسة: شاشة 'دفعات
البيع' (finance/lots_list.html) كانت تطبع `lot.status` الخام
("open"/"sold"/"archived") مباشرة بالإنجليزي بدون فلتر `ar_status`،
بغض النظر عن لغة المستخدم — كل دفعة بيع جديدة تُنشأ بحالة "open"
افتراضياً (SaleLot.status)، وهذا مسار حي فعلياً مو نظري."""


def test_lots_list_uses_ar_status_filter_not_raw_status(app, logged_in_client):
    from tests.factories import make_animal

    a = make_animal(animal_no="LOT-TR-01")
    with app.app_context():
        from app.extensions import db
        from app.models import Animal
        animal = Animal.query.get(a.id)
        animal.purpose = "بيع"
        db.session.commit()

    resp = logged_in_client.post("/finance/lots/new", data={
        "name": "دفعة اختبار الترجمة", "target_amount": "", "notes": "",
        "animal_ids": [a.id],
    })
    assert resp.status_code in (302, 200)

    resp = logged_in_client.get("/finance/lots")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert ">open<" not in body
    assert "مفتوحة" in body


def test_open_and_archived_status_labels_registered():
    from app import create_app
    app = create_app()
    with app.app_context():
        ar_status = app.jinja_env.filters["ar_status"]
        assert str(ar_status("open")) == "مفتوحة"
        assert str(ar_status("archived")) == "مؤرشفة"
