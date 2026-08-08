"""تخزين سحابي مجاني للصور/الصوت (بند إضافي 151) — طلبك: قرص Render
المجاني يُمسح بالكامل مع كل نشر جديد، فأي صورة/تسجيل صوتي مرفوع
(بلاغات، فواتير) كان يضيع بأول تحديث. الحل: Cloudinary — باقة مجانية
دائمة (~25GB) بدون بطاقة ائتمان.

**بدون SDK إضافي عمداً** — استخدمت `requests` (تبعية موجودة أصلاً من
بند رادار المناخ) لاستدعاء REST API مباشرة (توقيع الرفع بـSHA1 حسب
توثيق Cloudinary الرسمي)، بدل إضافة حزمة `cloudinary` جديدة لثلاث دوال
رفع فقط.

**Fallback آمن بالكامل**: لو متغيرات البيئة الثلاثة (`CLOUDINARY_CLOUD_NAME`،
`CLOUDINARY_API_KEY`، `CLOUDINARY_API_SECRET`) غير مضبوطة، يرجع تلقائياً
للتخزين المحلي القديم (`UPLOAD_DIR`) بدون أي كسر — صفر تغيير بالسلوك
الحالي لحد ما تُفعَّل المتغيرات الثلاثة فعلياً."""
import hashlib
import os
import time
import uuid

import requests
from flask import current_app


def _cloudinary_configured() -> bool:
    return bool(
        os.environ.get("CLOUDINARY_CLOUD_NAME")
        and os.environ.get("CLOUDINARY_API_KEY")
        and os.environ.get("CLOUDINARY_API_SECRET")
    )


def _upload_to_cloudinary(file_storage, *, subfolder: str) -> str | None:
    """رفع موقَّع (Signed Upload) — التوثيق الرسمي: SHA1 على المعاملات
    مرتبة أبجدياً + api_secret. `auto/upload` يتعامل صح مع صور وصوت
    بنفس المسار."""
    cloud_name = os.environ["CLOUDINARY_CLOUD_NAME"]
    api_key = os.environ["CLOUDINARY_API_KEY"]
    api_secret = os.environ["CLOUDINARY_API_SECRET"]

    timestamp = int(time.time())
    params_to_sign = {"folder": f"murabi/{subfolder}", "timestamp": timestamp}
    to_sign = "&".join(f"{k}={v}" for k, v in sorted(params_to_sign.items())) + api_secret
    signature = hashlib.sha1(to_sign.encode()).hexdigest()

    file_storage.stream.seek(0)
    try:
        resp = requests.post(
            f"https://api.cloudinary.com/v1_1/{cloud_name}/auto/upload",
            data={**params_to_sign, "api_key": api_key, "signature": signature},
            files={"file": (file_storage.filename, file_storage.stream)},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["secure_url"]
    except (requests.RequestException, KeyError, ValueError):
        # فشل الرفع السحابي (شبكة/مفاتيح خاطئة) — يرجع None بصمت،
        # والدالة المستدعية تتراجع للتخزين المحلي بدل ما توقف العملية
        # كلها (تسجيل البلاغ/الفاتورة أهم من نجاح رفع الملف نفسه).
        return None


def _save_locally(file_storage, *, subfolder: str, ext: str) -> str:
    upload_dir = os.path.join(current_app.config["UPLOAD_DIR"], subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.stream.seek(0)
    file_storage.save(os.path.join(upload_dir, filename))
    return f"/uploads/{subfolder}/{filename}"


def save_upload(file_storage, *, subfolder: str, allowed_extensions: set[str], max_bytes: int) -> str | None:
    """نقطة الدخول الموحّدة لأي رفع ملف بالمشروع (صورة بلاغ، ملاحظة
    صوتية، فاتورة) — تفحص الامتداد والحجم أولاً (نفس المنطق اللي كان
    مكرَّراً بثلاث دوال منفصلة)، وترجع None بصمت لأي إدخال غير صالح
    (الملف اختياري دائماً بهالثلاث حالات)."""
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in allowed_extensions:
        return None
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0 or size > max_bytes:
        return None

    if _cloudinary_configured():
        url = _upload_to_cloudinary(file_storage, subfolder=subfolder)
        if url:
            return url
    return _save_locally(file_storage, subfolder=subfolder, ext=ext)
