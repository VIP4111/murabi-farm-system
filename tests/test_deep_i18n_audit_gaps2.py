"""بند إصلاح (فحص عميق — طلبك: "افحص جميع النوافذ بعمق") — أربع فجوات
إضافية بنفس النمط (قواميس تصنيف ثابتة عربي بحت بدون `_l()`): فئة
العلف، حالة الحيوان الفسيولوجية (خطة العلف)، تقييم الجودة اليدوي
بتقرير أداء الفريق، ونوع المخزون بشاشة الجرد."""
from flask_babel import force_locale

from app.models.feed import Feed
from app.feed import feed_service
from app.team import performance_service as perf_svc
from app.core import inventory_count_service as csvc


def test_feed_class_labels_translate_to_english(app):
    with force_locale("en"):
        assert str(Feed.FEED_CLASS_LABELS_AR["concentrate"]) == "Concentrate"
    with force_locale("ar"):
        assert str(Feed.FEED_CLASS_LABELS_AR["concentrate"]) == "مركّز"


def test_feed_state_labels_translate_to_english(app):
    with force_locale("en"):
        assert str(feed_service.STATE_LABELS_AR["growth"]) == "Growth"


def test_performance_quality_labels_translate_to_english(app):
    with force_locale("en"):
        assert str(perf_svc.QUALITY_LABELS_AR["excellent"]) == "Excellent"


def test_inventory_kind_labels_translate_to_english(app):
    with force_locale("en"):
        assert str(csvc.KIND_LABELS_AR["feed"]) == "Feed"
