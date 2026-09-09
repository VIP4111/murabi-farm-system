"""بند إصلاح (فحص عميق — طلبك: "ابدأ بند") — `Finance.category` كان يُخزَّن
عربي بحت وقت الكتابة بعشرات المواضع بالكود (بيع، شراء، علاج، صيانة،
رواتب، هالك، فواتير كهرباء/ماء، شراء مخزون أعلاف/معدات/أدوية...)، وأي
عرض له للمستخدم كان يظهر عربي دايماً بغض النظر عن لغة المستخدم الحالية.

القيمة الخام المخزَّنة بقاعدة البيانات ما تتغيّر أبداً (صفر هجرة بيانات،
صفر تغيير بمنطق التجميع اللي يعتمد على القيمة الخام بـ loss_diagnosis_service) —
`display_category()`/`display_category_value()` يترجمون بس وقت العرض،
بنفس مبدأ `Role.display_label()`. أي فئة حرة يكتبها المستخدم يدوياً
بشاشة "عملية جديدة" ترجع كما هي (fallback آمن)."""
from flask_babel import force_locale

from app.models.finance import Finance


def test_display_category_value_translates_known_categories_to_english(app):
    with app.app_context(), force_locale("en"):
        assert Finance.display_category_value("بيع رأس") != "بيع رأس"
        assert Finance.display_category_value("شراء حيوان") != "شراء حيوان"
        assert Finance.display_category_value("علاج مرض") != "علاج مرض"
        assert Finance.display_category_value("صيانة معدات") != "صيانة معدات"
        assert Finance.display_category_value("راتب موظف") != "راتب موظف"
        assert Finance.display_category_value("هالك") != "هالك"
        assert Finance.display_category_value("خسارة أصل") != "خسارة أصل"
        assert Finance.display_category_value("فاتورة كهرباء") != "فاتورة كهرباء"
        assert Finance.display_category_value("فاتورة ماء") != "فاتورة ماء"
        assert Finance.display_category_value("بدون تصنيف") != "بدون تصنيف"
        assert Finance.display_category_value("أعلاف") != "أعلاف"
        assert Finance.display_category_value("معدات") != "معدات"
        assert Finance.display_category_value("أدوية") != "أدوية"


def test_display_category_value_stays_arabic_by_default_locale(app):
    # بدون تغيير اللغة، القيمة تبقى عربي (نفس القيمة الخام) — يثبت
    # إن الترجمة تصير وقت العرض بس، مو تخزين قيمة مختلفة.
    with app.app_context():
        assert Finance.display_category_value("بيع رأس") == "بيع رأس"


def test_display_category_value_falls_back_to_raw_value_for_free_text(app):
    # فئة حرة كتبها المستخدم يدوياً بشاشة "عملية جديدة" (غير موجودة
    # بالقاموس) ترجع كما هي بدل ما تنكسر أو تختفي.
    with app.app_context(), force_locale("en"):
        assert Finance.display_category_value("شي غريب كتبه المستخدم") == "شي غريب كتبه المستخدم"


def test_display_category_value_handles_none():
    assert Finance.display_category_value(None) is None


def test_finance_instance_display_category_uses_its_own_category_field(app):
    from datetime import date
    from app.extensions import db
    fin = Finance(date=date.today(), operation_type="expense", category="هالك", amount=10)
    db.session.add(fin)
    db.session.commit()
    with force_locale("en"):
        assert fin.display_category() != "هالك"
    assert fin.display_category() == "هالك"
