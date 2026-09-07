"""فحص عميق — اختبار حي كامل للمنتج بالمتصفح (طلبك: "دخل وسجل شرا وضيف
عامل وحظيرة... ونظّف مجموعة من الأغنام"): على مزرعة طازجة ما زارت شاشة
"+ حيوان جديد" الفردية ولا مرة، جدول `AnimalColor` يطلع فاضي تماماً —
شاشة "استقبال دفعة جديدة" (`/animals/bulk-purchase`) كانت ما تستدعي
`_ensure_animal_form_options_seeded()` قبل عرض قائمة الألوان (خلافاً
لـ`animals_new` اللي يستدعيها)، فتطلع الشاشة بدون أي شريحة لون —
والسيرفر برضه يرفض أي صف بلا لون (بند 285) — طريق مسدود فعلي، جربته
مباشرة بالمتصفح على نسخة محلية طازجة قبل هذا الإصلاح."""
from app.models import AnimalColor


def test_bulk_purchase_get_seeds_colors_on_fresh_farm(app, logged_in_client):
    assert AnimalColor.query.count() == 0, "الفحص لازم يبدأ على مزرعة بدون ألوان مزروعة مسبقاً"

    resp = logged_in_client.get("/animals/bulk-purchase")
    body = resp.data.decode()

    assert AnimalColor.query.count() > 0, (
        "الشاشة ما زرعت الألوان الافتراضية — نفس المستخدم اللي يفتح "
        "الاستقبال الجماعي أول شي بمزرعته الجديدة يعلق بدون أي لون يقدر يختاره"
    )
    assert "colorChip" in body
