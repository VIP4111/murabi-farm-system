"""بند إصلاح (فحص تحجيم حي بالمتصفح — طلبك: "٢" بعد فحص شاشة الأمراض
الشائعة على الجوال) — عمود "ملاحظات" بهذي الشاشة يحمل فقرات دواء طويلة
(جرعة/طريقة إعطاء/فترة سحب)، بخلاف بقية جداول التطبيق. الجدول العادي
كان ينكمش بشدة على الشاشات الضيقة (<640px) ويصير نص عمودي غير قابل
للقراءة. الحل: تحويل كل صف لكارت مستقل (`data-label` + CSS خاص بهذي
الصفحة فقط) تحت 640px، بدون أي تغيير على تصميم سطح المكتب أو على
`.compact-table` العام المستخدم بعشرات الشاشات الثانية."""
from app.extensions import db
from app.models import DiseaseType


def test_disease_types_list_table_has_mobile_card_class_and_data_labels(app, client, owner):
    db.session.add(DiseaseType(name="مرض تجريبي", notes="ملاحظة دواء طويلة للاختبار"))
    db.session.commit()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/health/disease-types")
    assert resp.status_code == 200
    html = resp.data.decode()
    # كلاس CSS الخاص بتحويل الجدول لكروت على الجوال موجود على عنصر
    # الجدول نفسه (مو تغيير عام على .compact-table).
    assert 'disease-types-table' in html
    # كل خلية بيانات (اسم/ملاحظات) لازم تحمل data-label عشان يظهر
    # كعنوان فوق القيمة داخل الكارت على الجوال (::before content).
    assert 'data-label=' in html


def test_disease_types_list_data_label_matches_translated_header(app, client, owner):
    db.session.add(DiseaseType(name="مرض تجريبي", notes="ملاحظة دواء طويلة للاختبار"))
    db.session.commit()
    client.post("/login", data={"phone": owner.phone, "password": "pass1234"})
    resp = client.get("/health/disease-types")
    html = resp.data.decode()
    assert 'data-label="الاسم"' in html
    assert 'data-label="ملاحظات"' in html
