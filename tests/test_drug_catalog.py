"""اختبارات كتالوج أسماء الأدوية + إعادة ترتيب فورم الدواء (بند إضافي 62)."""
from app.extensions import db
from app.models import DrugCatalogEntry, Pharmacy
from factories import make_pharmacy


def test_drug_catalog_new_adds_entry_with_class(app, logged_in_client):
    resp = logged_in_client.post("/health/drug-catalog/new", data={
        "name": "أوكسيتتراسيكلين 20%", "medicine_class": "antibiotic",
    }, follow_redirects=True)
    assert resp.status_code == 200
    entry = DrugCatalogEntry.query.filter_by(name="أوكسيتتراسيكلين 20%").one()
    assert entry.medicine_class == "antibiotic"


def test_drug_catalog_new_rejects_duplicate(app, logged_in_client):
    db.session.add(DrugCatalogEntry(name="سيلينيوم", medicine_class="supplement"))
    db.session.commit()
    resp = logged_in_client.post("/health/drug-catalog/new", data={
        "name": "سيلينيوم", "medicine_class": "supplement",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "موجود بالكتالوج أصلاً".encode() in resp.data
    assert DrugCatalogEntry.query.filter_by(name="سيلينيوم").count() == 1


def test_pharmacy_form_no_longer_has_free_text_category_field(app, logged_in_client):
    resp = logged_in_client.get("/health/pharmacy/new")
    assert resp.status_code == 200
    assert b'name="category"' not in resp.data


def test_pharmacy_new_ignores_category_even_if_posted(app, logged_in_client):
    """أي POST قديم لسا يرسل category (كاش متصفح قديم مثلاً) ما ينكسر —
    بس القيمة تُتجاهَل بصمت، ما تُحفظ."""
    resp = logged_in_client.post("/health/pharmacy/new", data={
        "name": "دواء 62 اختبار", "category": "قيمة قديمة",
    }, follow_redirects=True)
    assert resp.status_code == 200
    item = Pharmacy.query.filter_by(name="دواء 62 اختبار").one()
    assert item.category is None


def test_pharmacy_form_has_copper_checkbox(app, logged_in_client):
    """حرِج (بند 51 + بند 62): مربع "يحتوي نحاساً مرتفعاً" لازم يبقى
    بالفورم — هو الوسيلة الوحيدة لتفعيل حظر النعيمي لأي دواء جديد."""
    resp = logged_in_client.get("/health/pharmacy/new")
    assert resp.status_code == 200
    assert b'name="contains_high_copper"' in resp.data


def test_new_pharmacy_item_can_be_marked_high_copper(app, logged_in_client):
    resp = logged_in_client.post("/health/pharmacy/new", data={
        "name": "مكمّل نحاسي جديد", "contains_high_copper": "1",
    }, follow_redirects=True)
    assert resp.status_code == 200
    item = Pharmacy.query.filter_by(name="مكمّل نحاسي جديد").one()
    assert item.contains_high_copper is True


def test_editing_with_checkbox_checked_preserves_copper_flag(app, logged_in_client):
    """المربع يُعرض checked تلقائياً لو كان الدواء موسوماً أصلاً — لو
    الطبيب ما لمسه (يبقى checked)، القيمة الحقيقية تُرسَل مع الفورم
    وتبقى True، مو تُصفَّر صامتاً."""
    item = Pharmacy(name="مكمّل نحاسي 62", contains_high_copper=True, status="active")
    db.session.add(item)
    db.session.commit()

    resp = logged_in_client.post(f"/health/pharmacy/{item.id}/edit", data={
        "name": item.name, "unit_price": "9.5", "contains_high_copper": "1",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(item)
    assert item.contains_high_copper is True
    assert item.unit_price == 9.5


def test_unchecking_copper_checkbox_on_edit_clears_flag(app, logged_in_client):
    """تعديل صريح: الطبيب يفكّ التأشير عمداً (مثلاً تصحيح خطأ سابق) —
    القيمة تتصفّر، وهذا سلوك مقصود، مو فقدان بيانات صامت."""
    item = Pharmacy(name="مكمّل نحاسي 62-ب", contains_high_copper=True, status="active")
    db.session.add(item)
    db.session.commit()

    resp = logged_in_client.post(f"/health/pharmacy/{item.id}/edit", data={
        "name": item.name,
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(item)
    assert item.contains_high_copper is False


def test_shortages_alternatives_still_work_after_category_removed_from_form(app, logged_in_client):
    """يتأكد إن بند 61 لما ربط البدائل بـmedicine_class بدل category ما
    كسر الميزة."""
    short_item = make_pharmacy(name="لقاح ناقص", available_qty=0, medicine_class="vaccine")
    short_item.min_stock_qty = 5
    healthy_alt = make_pharmacy(name="لقاح بديل", available_qty=50, medicine_class="vaccine")
    healthy_alt.min_stock_qty = 5
    db.session.commit()
    resp = logged_in_client.get("/health/pharmacy/shortages")
    assert resp.status_code == 200
    assert "لقاح بديل".encode() in resp.data
