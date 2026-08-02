"""تجميع كل إضافات Flask بمكان واحد، عشان نتفادى استيراد دائري بين الملفات."""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_babel import Babel
from flask_wtf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
babel = Babel()
# حماية CSRF (بند إضافي 93، 2026-08-02 — التحليل الثالث) — قبل هذا
# البند ما كان فيه أي رمز CSRF بأي فورم، والحماية الوحيدة كانت
# SESSION_COOKIE_SAMESITE=Lax (بند 87) اللي تخفف الخطر بس ما تلغيه.
# CSRFProtect يتحقق تلقائياً من كل POST/PUT/DELETE.
csrf = CSRFProtect()
