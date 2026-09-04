# 01 — خريطة النظام

> تدقيق مستقل. المصدر: الكود والاختبارات وقاعدة البيانات — لا الوثائق وحدها.
> الفرع المرجعي: `main` @ `930f35b`. تاريخ التدقيق: 2026-09-04.

## 1) الخريطة السريعة

| العنصر | ما وجدته فعلياً بالكود |
|---|---|
| **الغرض الفعلي** | نظام إدارة تشغيلية شامل **لمزرعة واحدة** (أغنام/ماعز + نعام): سجل حيوانات، دورة إنتاج بعشر مراحل، صحة/صيدلية، تكاثر، علف، مالية ورواتب، مهام وبلاغات فريق، تقارير، مساعد ذكي اختياري، وعمل بدون اتصال (PWA). |
| **المستخدمون والأدوار** | 11 دوراً افتراضياً بـ`app/permissions_registry.py:DEFAULT_ROLES`: `owner`, `doctor`, `nurse`, `accountant`, `viewer` (أدوار نظام)، و`farm_worker`, `construction_worker`, `livestock_worker`, `farm_manager`, `housemaid` (بصفر صلاحيات عمداً) + `worker`. الصلاحيات **بيانات** بقاعدة البيانات (37 صلاحية، جدول `role_permissions`) قابلة للتعديل من الواجهة. |
| **التقنية** | Flask 3.0.3 + SQLAlchemy 2.x (Flask-SQLAlchemy 3.1.1) + Flask-Migrate/Alembic + Flask-Login + Flask-Babel + Flask-WTF (CSRF) + APScheduler. **Server-Side Rendering بالكامل** (Jinja2، صفر إطار واجهة). جافاسكربت خام بملفين فقط (`sw.js`, `offline_sync.js`) + سكربتات مضمّنة بالقوالب. |
| **التطبيقات والخدمات** | تطبيق واحد (monolith) بـ15 Blueprint: `auth`, `core`(بلا بادئة), `health`, `finance`, `repro`, `team`, `feed`, `reports`, `ostrich`, `assistant`, `climate`, `batches`, `warehouses`, `equipment`, `onboarding`. 289 راوت، 151 ملف بايثون (27,724 سطر)، 168 قالب Jinja (12,159 سطر). |
| **قاعدة البيانات** | SQLite افتراضياً، PostgreSQL بالإنتاج (`psycopg2-binary` مثبَّت، `_normalize_database_url` يعالج `postgres://`). **80 جدولاً**، 42 ملف موديل، 103 مايجريشن بسلسلة خطية ورأس واحد (`0f2a5b602937`). |
| **التكاملات الخارجية** | 5، كلها اختيارية وتُتجاهَل بصمت بدون مفاتيح: Telegram Bot API (إشعارات + webhook أوامر)، Resend (بريد)، Cloudinary (تخزين ملفات)، Open-Meteo (طقس، بلا مفتاح)، Google Gemini + Anthropic Claude (المساعد الذكي — `google-genai` مثبَّت، `anthropic` **غير مثبَّت** بـrequirements). |
| **المصادقة والصلاحيات** | Flask-Login بكوكي جلسة موقَّعة (`remember=True` دائماً). الدخول برقم الجوال + كلمة مرور (`scrypt` عبر Werkzeug). قفل بعد 5 محاولات فاشلة لمدة **دقيقة واحدة** (`User.LOCKOUT_MINUTES = 1`). التفويض عبر ديكوريتر `require_permission(code)` (`app/auth/decorators.py:7`) + فحوص داخل الخدمات (`report_service`, `task_service`). |
| **أهم تدفقات العمل** | (1) تسجيل/شراء حيوان ← دورة إنتاج ← بيع/نفوق/أرشفة. (2) بلاغ عامل ← قبول دكتور ← تحويل/تنفيذ ← إغلاق. (3) توليد مهام تلقائي (8 مولّدات) ← مراجعة ← تنفيذ ميداني. (4) تسجيل علاج/تحصين ← خصم صيدلية FIFO ← فترة سحب دواء ← بوابة منع بيع. (5) مالية: شراء/بيع/مصروف ← تقارير تكلفة الرأس ونقطة التعادل. (6) رواتب شهرية ← تأكيد ← حركة مصروف. |
| **التشغيل محلياً** | `pip install -r requirements.txt` ← `flask db upgrade` ← `flask seed` ← `python run.py`. **يتطلب Python ≥ 3.12** (بسبب `numpy==2.5.1`) — غير موثَّق بأي مكان؛ فشل التثبيت على 3.11 بهذا التدقيق. |
| **النشر** | Render (Docker أو Procfile) أو Railway. `Procfile`: `release: flask db upgrade && flask seed` ثم `gunicorn run:app --workers 2 --timeout 60`. `Dockerfile`: python:3.12-slim، نفس السلسلة داخل `CMD`. |
| **مستوى الاكتمال** | **عالٍ جداً بالعرض (breadth)، متوسط بالعمق التشغيلي.** أغلب الشاشات تعمل فعلاً ببيانات حقيقية، لكن استهلاك الاستعلامات ينمو خطّياً مع حجم القطيع (≈38 استعلاماً لكل رأس بالصفحة الرئيسية — مقيس)، والعزل بين مستخدمي نفس الجهاز مكسور، وثلاثة تدفقات مالية/صلاحيات فيها أخطاء مؤكَّدة. |

## 2) البنية الفعلية

```
run.py → app.create_app()
  ├─ app/config.py            إعدادات من متغيرات البيئة (Config واحدة، بلا Dev/Prod منفصلة)
  ├─ app/extensions.py        db / migrate / login_manager / babel / csrf
  ├─ app/models/  (42 ملف)    كل الموديلات، مقسّمة حسب المجال
  ├─ app/<module>/routes.py   Blueprint لكل وحدة
  ├─ app/<module>/*_service.py  منطق الأعمال (69 ملف خدمة)
  ├─ app/core/cycle_engine.py محرك دورة الإنتاج (10 مراحل، 6 مسارات، بوابات)
  ├─ app/core/scheduler.py    APScheduler داخل عملية التطبيق + catch-up على كل طلب
  ├─ app/templates/ (168)     Jinja، RTL/LTR حسب اللغة
  ├─ app/translations/        ar (ضمنية بالكود) + en/hi/am (.po + .mo مكوّمة بالمستودع)
  └─ app/static/sw.js + offline_sync.js   PWA وطابور IndexedDB
```

**نقاط الدخول الموحّدة** (مبدأ معماري واضح ومحترَم غالباً):
- إنشاء أي حيوان: `app/core/animal_service.py:create_animal` فقط.
- أي حدث دورة: `app/core/cycle_engine.py:record_cycle_event`.
- أي رفع ملف: `app/core/cloud_storage_service.py:save_upload`.
- أي خصم دواء: `Pharmacy.deduct_stock` (نداء واحد فعلي من `health_service`).

## 3) نموذج الصلاحيات

- 37 صلاحية بـ`app/permissions_registry.py:PERMISSIONS`.
- من 289 راوت: **280 خلف `@login_required`**، 9 عامة (`/login`، `/_healthz`، `/sw.js`، `/uploads/<path>`، `/telegram/webhook`، `/catalog/<token>`، `/lot/<token>`، `/login/language`، `/login/quick`).
- 235 راوت خلف `@require_permission(...)`؛ **45 راوت بـ`login_required` فقط** — أغلبها يفوّض الفحص لخدمة (`report_service`/`task_service`) أو لدالة مساعدة (`warehouses/routes.py:_require_kind_manage`)، لكن ليس كلها (راجع `SEC-02` بسجل الملاحظات).

## 4) أين يختلف الكود عن الوثائق

| الادعاء | الواقع بالكود | الدليل |
|---|---|---|
| `README.md`: «715 اختبار حالياً (يوليو 2026)» | الرقم الفعلي **~1571** حسب رسائل الكوميت الأخيرة و CI | `git log` رسالة `930f35b`: «1571 passed» |
| `README.md`: سكربت المحاكاة «يولّد نشاطاً واقعياً … **عبر نفس نقاط الدخول الحقيقية بالنظام**» | التقريع والأمراض تُكتب **مباشرة على الموديل** بلا مرور بأي خدمة أو بوابة | `app/core/simulation_service.py:95-118` (`db.session.add(Mating(...))`, `db.session.add(Disease(...))`) |
| `settings.html`: «الخدمة الموقوفة **تختفي تماماً من كل الواجهات**» | 5 من 6 خدمات (`crm`, `multi_branch`, `suppliers`, `genetics`, `multi_language`) **لا يقرأها أي كود إطلاقاً** | `grep ServiceToggle` — القارئ الوحيد `app/auth/routes.py:11` لمفتاح `dev_quick_login` |
| `ROADMAP.md` (آخر تحديث 2026-07-23): «لا اختبارات آلية حقيقية»، «تخزين سحابي… غير مبني»، «النعام: غير مبنية إطلاقاً» | الثلاثة **مبنية فعلاً** الآن (1571 اختبار، Cloudinary، `app/ostrich/`) | `ROADMAP.md:20-21,35`؛ مقابل `tests/`، `app/core/cloud_storage_service.py`، `app/ostrich/routes.py` |
| `backup_service.py`: «نفس القيمة الأصلية **تُستنتَج عكسياً وقت الاستيراد لاحقاً**» | **لا يوجد أي مسار استيراد/استعادة** بالمشروع | `grep -rn "import_all_tables\|restore_backup"` → صفر نتيجة |
| `README`: «`flask seed` … **آمن التكرار (idempotent)، لا يكرر البيانات**» | صحيح للإضافة، لكنه صار أيضاً **يحذف** صفوف `Task` ويوقف قوالب مهام — بكل نشر | `app/cli.py` (كوميت `88a3a97`): `db.session.delete(t)` داخل `seed` |
| `.env.example`: `ANTHROPIC_MODEL=claude-opus-4-8` (معلَّق) | `llm_bridge.DEFAULT_MODEL = "claude-sonnet-5"`، والمثال بالملف اسم نموذج قديم | `app/assistant/llm_bridge.py:52` مقابل `.env.example` |

## 5) حقيقة معمارية حاسمة: النظام **أحادي المزرعة** (single-tenant)

لا يوجد عمود `farm_id` ولا `tenant_id` بأي جدول من الـ80. `FarmSettings.get()`
يعيد دائماً الصف `id=1` (`app/models/farm_settings.py:226`). أي نشر واحد =
مزرعة واحدة. هذا يعني:

- **لا ينطبق** سؤال «عزل بيانات بين المزارع» بالشكل الكلاسيكي — كل من يدخل النظام يدخل نفس المزرعة.
- لكن **العزل بين الأدوار داخل المزرعة الواحدة** هو المخاطرة الحقيقية، وهو مكسور فعلياً على الأجهزة المشتركة (راجع `SEC-01`).
- خدمة «تعدد الفروع» بالإعدادات وهمية بالكامل — لا بنية بيانات خلفها.
