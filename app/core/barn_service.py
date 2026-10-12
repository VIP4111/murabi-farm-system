"""حذف حظيرة — منطق مشترك بين شاشة الحظائر اليدوية ووكيل المحادثة.

نفس القواعد بالضبط اللي كانت داخل راوت `barns_delete`: أي رأس لسا مربوط
بالحظيرة (بأي حالة) يمنع الحذف، وسجلات تاريخية مرتبطة (خطط تغذية، مهام،
بلاغات...) تمنعه كمان — بدل خطأ خام."""
from flask_babel import gettext as _
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Animal, AuditLog, Barn, BarnFeedingSchedule


class BarnNotEmptyError(ValueError):
    def __init__(self, barn_name: str, animals_count: int):
        self.barn_name, self.animals_count = barn_name, animals_count
        super().__init__(_(
            'فيه %(n)s رأس لسا مربوط بحظيرة "%(name)s" — انقلهم لحظيرة ثانية أولاً '
            "قبل ما تقدر تحذفها.", n=animals_count, name=barn_name,
        ))


class BarnHasHistoryError(ValueError):
    def __init__(self, barn_name: str):
        self.barn_name = barn_name
        super().__init__(_(
            'ما قدرنا نحذف حظيرة "%(name)s" — عندها سجلات مرتبطة بتاريخها '
            "(خطط تغذية، مهام، بلاغات سابقة...) ما تقدر تتحذف. تقدر تعدّل "
            "اسمها بدل الحذف لو تبي تعيد استخدامها لغرض ثاني.", name=barn_name,
        ))


def delete_barn(barn: Barn, *, actor_user_id: int) -> str:
    """يحذف الحظيرة نهائياً ويرجع اسمها. يرفع BarnNotEmptyError أو
    BarnHasHistoryError (كلاهما ValueError) بدل أي تغيير بالقاعدة."""
    barn_name = barn.display_name()
    animals_count = Animal.query.filter_by(barn_id=barn.id).count()
    if animals_count:
        raise BarnNotEmptyError(barn_name, animals_count)

    barn_id = barn.id
    BarnFeedingSchedule.query.filter_by(barn_id=barn.id).delete()
    db.session.delete(barn)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        raise BarnHasHistoryError(barn_name)
    db.session.add(AuditLog(actor_user_id=actor_user_id, action="barn.delete",
                             entity_type="Barn", entity_id=barn_id, details=barn_name))
    db.session.commit()
    return barn_name
