"""بند إضافي 289 — طلبك الصريح: "ضيف ماعز، اهم شي تتم الأتمتة نفس
النعيمي". أضيفت كسلالة (Breed) لا فصيلة (SpeciesType) — الفصيلة تُستثنى
تلقائياً من محرك دورة الإنتاج (نفس معاملة النعام)، أما السلالة فوصف
بس، ما تؤثر على الأتمتة إطلاقاً — فرأس بسلالة "ماعز" يشتغل بنفس
الأتمتة الكاملة اللي يشتغل بيها رأس بسلالة "نعيمي" أو أي سلالة ثانية،
بدون أي قاعدة طبية مختلقة له."""
from app.extensions import db
from app.models.animal import Animal
from app.models.animal_options import Breed
from app.core.animal_service import create_animal
from app.models.animal import AnimalSource
from app.models import ProductionWorkflow
from factories import make_barn


def test_goat_in_breeds_constant():
    assert "ماعز" in Animal.BREEDS


def test_seed_defaults_adds_goat_even_when_other_breeds_exist(app):
    """المحاكاة الأهم: مزرعة شغّالة أصلاً وعندها سلالات مسجَّلة —
    الحارس القديم (`count() > 0`) كان يمنع أي إضافة مستقبلية بمجرد
    وجود سلالة واحدة، حتى لو كانت غير "ماعز" بالاسم."""
    db.session.add(Breed(name="نعيمي"))
    db.session.commit()
    assert Breed.query.count() == 1

    Breed.seed_defaults()

    names = {b.name for b in Breed.query.all()}
    assert "ماعز" in names
    assert "نعيمي" in names


def test_seed_defaults_idempotent_does_not_duplicate(app):
    Breed.seed_defaults()
    Breed.seed_defaults()
    assert Breed.query.filter_by(name="ماعز").count() == 1


def test_animal_with_goat_breed_still_enters_full_cycle_engine(app):
    """أهم فحص: رأس بسلالة "ماعز" يدخل محرك دورة الإنتاج بنفس طريقة أي
    رأس ثانٍ — السلالة ما تغيّر شي بالأتمتة، خلافاً للفصيلة."""
    barn = make_barn(barn_no="GB-289")
    animal = create_animal(
        animal_no="GOAT-01", source=AnimalSource.PURCHASE, gender="أنثى",
        species="sheep_goat", barn_id=barn.id, breed="ماعز",
    )
    assert animal.breed == "ماعز"
    wf = ProductionWorkflow.query.filter_by(animal_id=animal.id).first()
    assert wf is not None


def test_animal_form_offers_goat_breed_option(app, logged_in_client):
    resp = logged_in_client.get("/animals/new")
    assert "ماعز".encode() in resp.data
