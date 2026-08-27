"""بند إضافي 273 — نية "المالية" الحية بالمساعد الذكي (تحسب مباشرة من
بيانات المزرعة كل مرة) ما كانت تذكر نسبة الربح إطلاقاً، رغم إننا
أضفنا بطاقتها لشاشة المالية الرئيسية ببند 256. نفس المعادلة بالضبط
(صافي ÷ إجمالي الخارج × 100)."""
from datetime import date

from app.assistant import context_service, nlu_service
from app.extensions import db
from app.models import Finance


def _row(op_type, amount):
    db.session.add(Finance(date=date.today(), operation_type=op_type, amount=amount, is_cancelled=False))
    db.session.commit()


def test_finance_summary_computes_net_percent(app):
    _row("sale", 1500)
    _row("purchase", 800)
    _row("expense", 200)
    s = context_service.finance_summary()
    assert s["net"] == 500
    assert s["net_percent"] == 50.0


def test_finance_summary_percent_none_when_no_outflow(app):
    _row("sale", 1000)
    s = context_service.finance_summary()
    assert s["net_percent"] is None


def test_finance_intent_reply_includes_percent(app, owner):
    _row("sale", 1500)
    _row("purchase", 1000)
    result = nlu_service.answer(owner, "كم نسبة ربحي هذا الشهر")
    assert result["intent_code"] == "finance"
    assert "نسبة الربح: 50%" in result["reply"]


def test_finance_intent_still_matches_old_keywords(app, owner):
    result = nlu_service.answer(owner, "شنو صافي الربح هذا الشهر")
    assert result["intent_code"] == "finance"
