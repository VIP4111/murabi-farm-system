"""فحص "النسخ الاحتياطي والاسترجاع" — الواجهة كانت تقول صراحة "هذا
الملف ضمانتك الوحيدة لو صار عطل بقاعدة البيانات" (بند إضافي بعد حادثة
حقيقية: قاعدة Render انتهت صلاحيتها وانقطع الوصول للبيانات)، لكن فحص
الكود لقى: تصدير فقط، صفر استرجاع — لو صار عطل حقيقي، ما فيه أي طريقة
ترجع الملف المحفوظ للنظام. هذا الاختبار يتأكد إن الاسترجاع الجديد
(`import_all_tables_json`) يعيد البيانات فعلياً، مع صحة العلاقات
(بما فيها عمود ذاتي المرجع `animals.mother_id`)."""
import io

from app.core import backup_service
from app.extensions import db
from app.models import Animal, Barn
from app.models.animal import AnimalSource
from tests.factories import make_animal, make_barn


def test_export_then_restore_round_trip_preserves_data(app):
    with app.app_context():
        barn = make_barn(barn_no="TIP-BK-1", barn_name="حظيرة النسخة")
        mother = make_animal(animal_no="TIP-BK-MOM", gender="أنثى", barn_id=barn.id)
        child = make_animal(animal_no="TIP-BK-CHILD", gender="أنثى", barn_id=barn.id)
        child.mother_id = mother.id
        db.session.commit()

        buf = backup_service.export_all_tables_json()
        import json
        payload = json.loads(buf.getvalue().decode("utf-8"))

        # نمسح فعلياً ونضيف بيانات مختلفة، عشان نتأكد الاسترجاع يستبدلها
        # بمحتوى الملف بالضبط (مو دمج).
        Animal.query.delete()
        Barn.query.delete()
        db.session.commit()
        make_animal(animal_no="TIP-BK-JUNK")
        db.session.commit()

        counts = backup_service.import_all_tables_json(payload)
        db.session.commit()

        assert counts["animals"] >= 2
        restored_mother = Animal.query.filter_by(animal_no="TIP-BK-MOM").first()
        restored_child = Animal.query.filter_by(animal_no="TIP-BK-CHILD").first()
        assert restored_mother is not None
        assert restored_child is not None
        # العلاقة الذاتية المرجع (mother_id) لازم ترجع صح رغم إنها
        # أُجِّلت لتمرير UPDATE ثانٍ (الجدول يشير لنفسه).
        assert restored_child.mother_id == restored_mother.id
        # الرأس "الدخيل" اللي أضفناه بعد المسح ما يفترض يبقى موجوداً —
        # الاسترجاع استبدال كامل، مو دمج.
        assert Animal.query.filter_by(animal_no="TIP-BK-JUNK").first() is None


def test_invalid_backup_file_is_rejected_with_clear_error(app):
    with app.app_context():
        import pytest
        with pytest.raises(backup_service.InvalidBackupFile):
            backup_service.import_all_tables_json({"not": "a backup file"})
        with pytest.raises(backup_service.InvalidBackupFile):
            backup_service.import_all_tables_json([])


def test_enum_column_round_trips_correctly_not_as_python_repr(app):
    """بند إصلاح مصاحب — أعمدة Enum (`Animal.source`) كانت تُصدَّر
    كتمثيل Python الخام ("AnimalSource.PURCHASE") بدل الاسم الفعلي
    ("PURCHASE")، فيفشل أي استرجاع لاحق بخطأ Enum غير معروف."""
    with app.app_context():
        animal = make_animal(animal_no="TIP-BK-ENUM", source=AnimalSource.GIFT)
        buf = backup_service.export_all_tables_json()
        import json
        payload = json.loads(buf.getvalue().decode("utf-8"))
        row = next(r for r in payload["tables"]["animals"] if r["animal_no"] == "TIP-BK-ENUM")
        assert row["source"] == "GIFT"
        assert "AnimalSource" not in row["source"]


def test_restore_route_rejects_non_owner(logged_in_client, worker, app):
    """حصري لصاحب الحلال فقط — نفس مستوى حماية ضبط المصنع بالضبط."""
    with app.app_context():
        buf = backup_service.export_all_tables_json()
        content = buf.getvalue()

    client = logged_in_client
    client.get("/logout")
    client.post("/login", data={"phone": worker.phone, "password": "pass1234"})

    resp = client.post(
        "/settings/backup/restore",
        data={
            "backup_file": (io.BytesIO(content), "backup.json"),
            "confirm_phrase": "استرجاع النسخة",
            "password": "pass1234",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 403


def test_restore_route_rejects_wrong_confirm_phrase(logged_in_client):
    resp = logged_in_client.post(
        "/settings/backup/restore",
        data={
            "backup_file": (io.BytesIO(b'{"tables": {}}'), "backup.json"),
            "confirm_phrase": "غلط",
            "password": "pass1234",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "لازم تكتب عبارة التأكيد بالضبط" in resp.data.decode()


def test_restore_route_full_flow_replaces_data_and_logs_out(logged_in_client, owner, app):
    with app.app_context():
        make_animal(animal_no="TIP-BK-BEFORE")
        buf = backup_service.export_all_tables_json()
        content = buf.getvalue()

    with app.app_context():
        Animal.query.delete()
        db.session.commit()
        make_animal(animal_no="TIP-BK-AFTER-WIPE")
        db.session.commit()

    resp = logged_in_client.post(
        "/settings/backup/restore",
        data={
            "backup_file": (io.BytesIO(content), "backup.json"),
            "confirm_phrase": "استرجاع النسخة",
            "password": "pass1234",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "تسجيل الدخول" in body  # اتخرج من الجلسة تلقائياً

    with app.app_context():
        assert Animal.query.filter_by(animal_no="TIP-BK-BEFORE").first() is not None
        assert Animal.query.filter_by(animal_no="TIP-BK-AFTER-WIPE").first() is None
