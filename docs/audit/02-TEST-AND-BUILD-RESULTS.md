# 02 — نتائج التشغيل والفحوص الآلية

بيئة التدقيق: Ubuntu 24.04، Python **3.13.x** (بيئة افتراضية معزولة `.venv-audit`)،
Node v22.22.2. قاعدة بيانات SQLite مؤقتة داخل مجلد مؤقت — **صفر اتصال بأي بيئة
إنتاج، وصفر كتابة على أي قاعدة خارجية**.

## جدول النتائج

| الفحص | النتيجة | العدد/التفصيل | الدليل |
|---|---|---:|---|
| Installation (Python 3.11) | **Fail** | `numpy==2.5.1` يتطلب Python ≥ 3.12 | `ERROR: Could not find a version that satisfies the requirement numpy==2.5.1 … 2.5.1 Requires-Python >=3.12` |
| Installation (Python 3.13) | **Pass** | كل الحزم ثُبِّتت، صفر تعارض | `pip install -r requirements.txt` → exit 0 |
| Lint | **Blocked** | لا يوجد أي إعداد lint بالمشروع (لا flake8/ruff/pylint/pre-commit) | `ls -a` → صفر ملف إعداد؛ `.github/workflows/tests.yml` لا يشغّل lint |
| Type-check | **Blocked** | لا mypy ولا pyright ولا أي type checker؛ التلميحات النوعية جزئية | لا `mypy.ini`/`pyproject.toml`/`setup.cfg` |
| Unit + Integration tests (pytest) | **Pass** | **1571 passed، 0 failed، 3802 تحذير، 830 ثانية (13:50)** | `pytest -q` → `1571 passed, 3802 warnings in 830.40s` |
| JS tests (node --test) | **Pass** | **22 passed، 0 failed** (`tests/js/sw.test.js`, `offline_sync.test.js`) | `node --test tests/js/*.test.js` → `# pass 22 / # fail 0` |
| E2E tests (متصفح حقيقي) | **غير موجودة** | صفر اختبار Playwright/Selenium؛ كل الاختبارات على مستوى Flask test client | `grep -rn "playwright\|selenium" tests/` → صفر |
| Production build | **N/A → Pass** | لا خطوة بناء (SSR بالكامل). التحقق البديل: التطبيق يقلع فعلياً تحت gunicorn بإعدادات الإنتاج | `gunicorn run:app --workers 2 --timeout 60` → `/_healthz` = `{"status":"ok"}` |
| Local runtime (gunicorn) | **Pass** | 136 صفحة GET = 200، 3 = 302، **صفر 5xx** | زحف كامل (أدناه) |
| Database migrations | **Pass** | 103 مايجريشن، سلسلة خطية، **رأس واحد** (`0f2a5b602937`)، تُطبَّق من الصفر بلا خطأ | `flask db upgrade` → exit 0 |
| Schema drift (models ↔ migrations) | **Pass** | **صفر انحراف** | `alembic.autogenerate.compare_metadata` → `NO DRIFT` |
| Seed idempotency | **Pass** | التشغيل الثاني: «حساب المالك موجود مسبقاً، تم تخطيه» | `flask seed` ×2 → exit 0 |
| CI (GitHub Actions) | **Pass** | 412 تشغيلة، آخر 10 كلها `success` على `main` | `actions_list` → `conclusion: success` لكل السجل الأخير |

## تفاصيل الأوامر المنفَّذة

```bash
# 1) بيئة معزولة + تثبيت
python3.11 -m venv .venv-audit && pip install -r requirements.txt   # FAIL (numpy)
python3.13 -m venv .venv-audit && pip install -r requirements.txt   # OK

# 2) مايجريشن على قاعدة مؤقتة تماماً
DATABASE_URL="sqlite:////tmp/.../test_mig.db" flask db upgrade      # OK (103 مايجريشن)
flask seed && flask seed                                            # OK، idempotent
# → 80 جدولاً، 37 صلاحية، 11 دوراً، 84 ربط صلاحية-دور،
#   52 نوع مرض، 185 عرَضاً، 193 ربط مرض-عرض، 14 بند تشيك-ليست، 6 خدمات (كلها موقوفة)

# 3) فحص انحراف المخطط
alembic compare_metadata(migrated_db, db.metadata)                  # NO DRIFT

# 4) الاختبارات
pytest -q                       # 1571 passed / 830s
node --test tests/js/*.test.js  # 22 passed

# 5) تشغيل فعلي بإعدادات الإنتاج
gunicorn run:app --bind 127.0.0.1:8099 --workers 2 --timeout 60

# 6) محاكاة المشروع نفسه (على نسخة منفصلة من القاعدة)
flask simulate-farm-month --days 30   # OK، 2.2 ثانية
```

## زحف كامل لكل مسارات GET (بحساب المالك)

140 مساراً بلا معاملات، منها `logout` مستثنى:

```
STATUS: 136 × 200   |   3 × 302   |   0 × 4xx   |   0 × 5xx
```

**أبطأ الصفحات** (قاعدة شبه فارغة — راجع قسم الأداء لقياس حقيقي):

| الزمن | الحجم | المسار |
|---:|---:|---|
| 0.226s | 77 KB | `/` |
| 0.126s | 78 KB | `/onboarding/setup-checklist` |
| 0.118s | 77 KB | `/settings/readiness` |
| 0.072s | 98 KB | `/settings` |
| 0.047s | 157 KB | `/settings/backup/export-now` |

## قياس أداء حقيقي

**بيئة القياس (مثبَّتة، ولا تُعمَّم على غيرها)**: Ubuntu 24.04 · Python 3.13 ·
Flask test client داخل نفس العملية · **SQLite على ملف محلي** (بلا شبكة، بلا اتصال
خارجي) · طلب واحد بلا تزامن · مستخدم بدور `owner`.
**البيانات**: قطيع مولَّد آلياً بحالة `active` + 5 حظائر + قيدَا وزن لكل رأس؛
صفر بلاغات، صفر مهام سابقة، صفر حركات مالية.
**العدّاد**: مستمع `sqlalchemy.event` على `before_cursor_execute` — عدّ فعلي لكل
استعلام يصل السائق، لا تقدير.

**عدد استعلامات SQL لكل طلب (أربع نقاط قياس):**

| حجم القطيع | `/` | `/animals` | `/alerts` |
|---:|---:|---:|---:|
| 50 | 1,983 | 1,035 | 897 |
| 100 | 3,933 | 2,085 | 1,747 |
| 200 | **7,833** | 4,221 | 3,447 |
| 400 | **15,281** | 8,445 | 6,671 |

**زمن الاستجابة بنفس البيئة (SQLite داخل العملية):**

| حجم القطيع | `/` | `/animals` | `/alerts` |
|---:|---:|---:|---:|
| 50 | 1.15 s | 0.34 s | 0.25 s |
| 100 | 1.87 s | 0.73 s | 0.59 s |
| 200 | 3.13 s | 1.39 s | 1.14 s |
| 400 | 6.78 s | 2.62 s | 2.21 s |

**قياسات مفردة عند 200 رأس** (نفس البيئة): `/team/tasks` = 14 استعلاماً / 0.10 s /
344 KB · `/settings` = 40 / 0.07 s / 90 KB · `/finance/` = 5 / 0.03 s / 73 KB.

**النمو خطّي — مقيس لا مُستنتَج**: الميل بين 50 و400 رأس ≈ **38 استعلاماً لكل رأس**
على `/`، والنقاط الأربع تقع على الخط نفسه. أكثر الاستعلامات تكراراً على `/` عند
200 رأس: `animal_weights` ×1402، `animals` ×1104، `vaccinations` ×805،
`diseases` ×804، `vet_visits` ×800، `matings` ×482 — نمط N+1 كلاسيكي.

> ⚠️ **لم يُقَس على PostgreSQL بهذا التدقيق** (قيد صريح: صفر اتصال بأي قاعدة خارجية).
> **عدد** الاستعلامات ونموّه الخطّي خاصية للكود ويبقى صحيحاً بأي محرّك؛ أما **الزمن**
> فمُقاس على SQLite داخل العملية فقط ولا يُعمَّم. لا يرد بهذا التقرير أي رقم زمني
> لـPostgreSQL لأنه لم يُقَس.

## التحذيرات

3802 تحذيراً، كلها من نوع واحد: `LegacyAPIWarning: Query.get() … deprecated
since SQLAlchemy 2.0`. **57 موضع استدعاء** لـ`.query.get(` داخل `app/`.
غير مؤثِّرة الآن، لكنها دَين ترقية حقيقي: SQLAlchemy 2.x يعتبرها legacy،
وإزالتها مستقبلاً تكسر 57 موضعاً دفعة واحدة.

## ما لم أستطع التحقق منه، والسبب

| البند | السبب |
|---|---|
| السلوك الفعلي للـService Worker والكاش بين مستخدمين | يحتاج متصفح حقيقي (Cache Storage API لا يوجد بـFlask test client). الاستنتاج مبني على قراءة الكود سطراً بسطر — راجع `SEC-01`. |
| سلوك النظام وأداؤه على PostgreSQL | لم أتصل بأي قاعدة خارجية (قيد التدقيق الصريح). كل القياسات الزمنية على SQLite داخل العملية. لم أقِس أثر رحلة الشبكة لكل استعلام على PostgreSQL، ولا أذكر له رقماً. إغلاق الفجوة: تشغيل نفس السكربت على PostgreSQL محلي بأحجام القطيع الأربعة نفسها. |
| فترة صلاحية رمز CSRF الفعلية بالإنتاج | `WTF_CSRF_TIME_LIMIT` غير مضبوط ⇒ الافتراضي 3600 ثانية. أثبتُّ سلوك الرفض والحذف الصامت برمز غير صالح (وهو نفس مسار الرمز المنتهي). |
| سلوك الجدولة مع أكثر من عامل gunicorn | يحتاج تشغيل متزامن حقيقي تحت حمل. الخطر مستنتَج من الكود (SELECT-ثم-INSERT بلا قيد فريد). |
| التوافق عبر المتصفحات وiOS Safari | لا توجد أدوات متصفح بهذي البيئة. |
| دقة الأرقام البيطرية/التغذوية | خارج نطاق التدقيق التقني — الكود نفسه يوثّق أنها تقديرات عامة تحتاج مراجعة طبيب. |
