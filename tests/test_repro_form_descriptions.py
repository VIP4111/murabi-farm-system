"""بند إضافي — طلبك: "المطلوب كل نافذه تظيف عليها او فيها وصف علشان
الي يدخل يعرف شنو بيسوي. وتحت الملاحضات تكتب الدوره الي راح يمشي
فيها" — على نماذج تقريع جديد/تشخيص حمل جديد/فحص سونار جديد."""


def test_mating_form_has_description_and_next_stage_note(logged_in_client):
    resp = logged_in_client.get("/repro/matings/new")
    body = resp.get_data(as_text=True)
    assert "سجّل هنا محاولة تقريع" in body
    assert "الخطوة الجاية بالدورة" in body


def test_pregnancy_form_has_description_and_next_stage_note(logged_in_client):
    resp = logged_in_client.get("/repro/pregnancies/new")
    body = resp.get_data(as_text=True)
    assert "سجّل هنا نتيجة تأكيد حمل" in body
    assert "الخطوة الجاية بالدورة" in body


def test_sonar_form_has_description_and_next_stage_note(logged_in_client):
    resp = logged_in_client.get("/repro/sonar/new")
    body = resp.get_data(as_text=True)
    assert "سجّل هنا نتيجة فحص سونار" in body
    assert "الخطوة الجاية بالدورة" in body
