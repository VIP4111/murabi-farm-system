#!/usr/bin/env bash
# SEC-01 — تشغيل اختبار عزل كاش الـService Worker بمتصفح حقيقي، بأمر واحد.
#
#   bash tests/e2e/run_sw_e2e.sh            # السيناريوهات الثلاثة كلها
#   bash tests/e2e/run_sw_e2e.sh --isolation # العزل بين المستخدمين فقط
#   bash tests/e2e/run_sw_e2e.sh --upgrade   # ترقية v7→v8 بكاش ملوّث فقط
#   bash tests/e2e/run_sw_e2e.sh --queue     # طابور الإدخالات عبر المستخدمين فقط
#
# يجهّز كل شي بنفسه: قاعدة SQLite مؤقتة + مايجريشن + بذر + حساب عامل،
# يشغّل gunicorn على منفذ حر، ينفّذ الاختبار، ثم ينظّف كل شي (حتى عند الفشل).
# لا يلمس أي قاعدة بيانات أو منفذ لك — كل شي داخل مجلد مؤقت يُحذف بالنهاية.
#
# المتطلبات (مرة واحدة):
#   pip install -r requirements.txt playwright && playwright install chromium
#
# يستخدم مفسّر بايثون الحالي (أو PYTHON=/path/to/venv/bin/python لتحديده)،
# ويستدعي flask/gunicorn كوحدات — فيعمل داخل venv بلا تفعيل مسبق.
#
# يخرج بـ0 عند ISOLATED ✅ و1 عند LEAK ❌ — صالح كبوابة قبل النشر.
set -euo pipefail

cd "$(dirname "$0")/../.."
PORT="${SW_E2E_PORT:-8099}"
PYTHON="${PYTHON:-python3}"
WORKDIR="$(mktemp -d)"
DB="$WORKDIR/e2e.db"
PIDFILE="$WORKDIR/gunicorn.pid"

cleanup() {
  [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null || true
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

export FLASK_APP=run.py
export SECRET_KEY="sw-e2e-only-$RANDOM"
export DATABASE_URL="sqlite:///$DB"
export OWNER_PHONE=0500000000
export OWNER_PASSWORD=change-me-123

echo "▶ تجهيز قاعدة مؤقتة: $DB"
"$PYTHON" -m flask db upgrade >/dev/null
"$PYTHON" -m flask seed >/dev/null

echo "▶ إنشاء حساب عامل وحظيرة للاختبار"
"$PYTHON" - <<'PY'
from app import create_app
from app.config import Config
from app.extensions import db
from app.models import User, Role, Barn
app = create_app(Config)
with app.app_context():
    if not User.query.filter_by(phone="0500000002").first():
        w = User(name="عامل الاختبار", phone="0500000002",
                 role_id=Role.query.filter_by(name="worker").first().id, language="ar")
        w.set_password("worker1234")
        db.session.add(w)
    # نموذج البلاغ يشترط حيواناً أو حظيرة — `flask seed` لا ينشئ حظائر
    # (تُنشأ كسولاً عند أول فتح لشاشة "حيوان جديد")، فننشئ واحدة صراحةً.
    if not Barn.query.first():
        db.session.add(Barn(barn_no="E2E-1", barn_name="حظيرة الاختبار",
                            barn_type="عام", capacity=50))
    db.session.commit()
PY

echo "▶ تشغيل gunicorn على المنفذ $PORT"
"$PYTHON" -m gunicorn run:app --bind "127.0.0.1:$PORT" --workers 1 --timeout 60 \
  --pid "$PIDFILE" --log-file "$WORKDIR/gunicorn.log" --daemon

for _ in $(seq 1 40); do
  curl -sf -o /dev/null "http://127.0.0.1:$PORT/_healthz" && break
  sleep 0.5
done
curl -sf -o /dev/null "http://127.0.0.1:$PORT/_healthz" || { echo "✗ الخادم لم يقلع"; cat "$WORKDIR/gunicorn.log"; exit 2; }

URL="http://127.0.0.1:$PORT"
SCENARIO="${1:---all}"
rc=0

run() {  # run <label> <script>
  echo ""
  echo "═══ $1 ═══"
  "$PYTHON" "$2" "$URL" || rc=$?
}

case "$SCENARIO" in
  --isolation) run "عزل الكاش بين المستخدمين" tests/e2e/sw_cache_isolation_e2e.py ;;
  --upgrade)   run "ترقية الـService Worker بكاش ملوّث" tests/e2e/sw_upgrade_e2e.py ;;
  --queue)     run "طابور الإدخالات عبر تبديل الحساب" tests/e2e/offline_queue_across_users_e2e.py ;;
  --all|"")
    run "عزل الكاش بين المستخدمين" tests/e2e/sw_cache_isolation_e2e.py
    run "ترقية الـService Worker بكاش ملوّث" tests/e2e/sw_upgrade_e2e.py
    run "طابور الإدخالات عبر تبديل الحساب" tests/e2e/offline_queue_across_users_e2e.py
    ;;
  *) echo "خيار غير معروف: $SCENARIO" >&2; exit 2 ;;
esac

echo ""
[ "$rc" -eq 0 ] && echo "✅ كل سيناريوهات SEC-01 نجحت" || echo "❌ فشل سيناريو أو أكثر (rc=$rc)"
exit "$rc"
