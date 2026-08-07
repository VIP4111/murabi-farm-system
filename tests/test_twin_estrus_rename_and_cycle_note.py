"""بند إضافي — طلبك: "لاحضت في انافذه الجانبيه زر اسمه برنامج التزامن
التناسلي المتقدم المطلوب تغير اسمه الى استخدام الاسفنجة للمتاوه بعدها
ادخل من داخله برنامج جديد ونزل تحت الملاحظات وكتب وتحت الملاحظات
تكتب الدوره الي راح يمشي فيها"."""


def test_sidebar_link_renamed(logged_in_client):
    resp = logged_in_client.get("/")
    body = resp.get_data(as_text=True)
    assert "استخدام الاسفنجة للمتاوة" in body
    assert "برامج التزامن التناسلي (متقدّم)" not in body


def test_new_program_form_has_full_cycle_note_under_notes(logged_in_client):
    resp = logged_in_client.get("/repro/programs/new")
    body = resp.get_data(as_text=True)
    assert "الدورة الكاملة اللي راح يمشي فيها هذا البرنامج" in body
