"""Settings cho máy dev / CI / test.

Chạy được ngay mà không cần Redis, Postgres, Cloudinary hay SMTP:
- DB: sqlite (trừ khi đặt DATABASE_URL)
- Channel layer: InMemory (trừ khi đặt REDIS_URL / REDIS_HOST_URL)
- Media: thư mục media/ cục bộ (trừ khi đặt đủ 3 biến CLOUDINARY_*)
- Email: in ra console
"""
from .base import *  # noqa: F401,F403

DEBUG = env_bool("DEBUG", True)

# Chỉ để máy dev chạy được khi .env chưa có SECRET_KEY. production.py từ chối key dạng này.
SECRET_KEY = SECRET_KEY or "django-insecure-dev-only-key-do-not-use-in-production"

ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1", "[::1]"]

# Dev luôn in mail ra console để luồng quên mật khẩu không phụ thuộc SMTP thật.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Không dùng Manifest storage ở dev: nếu DEBUG=False mà chưa collectstatic sẽ 500
# "Missing staticfiles manifest entry".
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# WhiteNoise ở dev/test: phục vụ thẳng từ finders (thư mục static của từng app),
# không cần collectstatic và không cảnh báo "No directory at: .../staticfiles".
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
