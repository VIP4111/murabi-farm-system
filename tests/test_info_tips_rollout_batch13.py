"""طلب "اكمل بنفس الطريقه" — دفعة سادسة (أصغر، لأن معظم النماذج
المتبقية موثَّقة أصلاً بفقرات شرح مضمَّنة) تغطي: حركة مخزون المعدات،
تسجيل نتيجة فقس بيض النعام."""
from datetime import date

from app.extensions import db
from tests.factories import make_equipment


def test_equipment_item_movement_has_tip(app, logged_in_client):
    with app.app_context():
        eq = make_equipment(name="أداة اختبار الحركة")
        item_id = eq.id
    resp = logged_in_client.get(f"/equipment/items/{item_id}/movement")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1


def test_egg_hatch_form_has_tip(app, logged_in_client):
    with app.app_context():
        from tests.factories import make_animal
        from app.models.ostrich import OstrichEgg
        mother = make_animal(animal_no="TIP-OST-01", gender="أنثى")
        egg = OstrichEgg(mother_id=mother.id, lay_date=date.today())
        db.session.add(egg)
        db.session.commit()
        egg_id = egg.id
    resp = logged_in_client.get(f"/ostrich/eggs/{egg_id}/hatch")
    body = resp.data.decode()
    assert resp.status_code == 200
    assert body.count('class="info-tip"') >= 1
