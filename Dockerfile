# صورة نشر بسيطة لنظام "مربي" — Python + gunicorn، بلا أي بناء واجهة
# منفصل (كل القوالب تُقدَّم من Flask نفسه، Server-Side Rendering بالكامل).
FROM python:3.12-slim

WORKDIR /app

# متطلبات نظام لبناء بعض حزم بايثون العلمية (scipy) + خطوط عربية للتصدير PDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# مجلد قاعدة SQLite المحلية + النسخ الاحتياطي — لازم يكون قابلاً للكتابة.
# تنبيه: على المنصات المجانية (Render/Railway بدون Persistent Disk) هذا
# المجلد يُصفَّر عند كل إعادة نشر — راجع ملف التعليمات المرفق (DEPLOY.md).
RUN mkdir -p instance instance/backups

ENV FLASK_APP=run.py
EXPOSE 8000

# عند كل إقلاع: تحديث مخطط القاعدة (migrations) ثم تعبئة البيانات الأولية
# (حساب المالك + الأدوار + الصلاحيات + مراجع تشخيصية) — flask seed مصمَّم
# ليكون آمن التكرار (idempotent)، لا يكرر البيانات لو كانت موجودة أصلاً.
CMD flask db upgrade && flask seed && gunicorn run:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 60
