"""بند إضافي 291 — طلبك الصريح "ابدأ" بعد فحص صريح لقينا فيه فجوة
حقيقية: شاشة "استقبال دفعة" كانت تعرض قائمة سلالات ثابتة بالكود
(`Animal.BREEDS` القديمة)، منفصلة تماماً عن جدول `Breed` الحقيقي اللي
تضيف له سلالات جديدة من شاشة "+ حيوان جديد" — أي سلالة تُضاف هناك ما
كانت تظهر بشاشة الدفعة إطلاقاً. صارت الشاشتان تقرآن من نفس المصدر."""
from app.extensions import db
from app.models.animal_options import Breed


def test_batches_new_shows_custom_breed_added_from_animal_form(app, logged_in_client):
    """المحاكاة الأهم: سلالة تُضاف بزر "+" من شاشة الحيوان الفردي —
    لازم تظهر بشاشة استقبال الدفعة كمان بدون أي تعديل كود إضافي."""
    resp = logged_in_client.post("/animals/breeds/new", data={"name": "سلالة مخصّصة 291"})
    assert resp.status_code == 302
    db.session.commit()

    resp = logged_in_client.get("/batches/new")
    assert "سلالة مخصّصة 291".encode() in resp.data


def test_batches_new_seeds_default_breeds_on_fresh_farm(app, logged_in_client):
    assert Breed.query.count() == 0
    resp = logged_in_client.get("/batches/new")
    assert resp.status_code == 200
    assert Breed.query.count() > 0
    assert "نعيمي".encode() in resp.data
