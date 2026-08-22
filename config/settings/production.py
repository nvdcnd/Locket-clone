"""Settings cho production (container chạy sau reverse proxy HTTPS như Render/Railway/Nginx).

Những thứ bắt buộc phải có ở môi trường thật được kiểm tra 2 tầng:
- SECRET_KEY: kiểm tra ngay khi import (Dockerfile truyền SECRET_KEY=build-only lúc collectstatic).
- DATABASE_URL / REDIS / CLOUDINARY / ALLOWED_HOSTS: kiểm tra bằng Django system check
  (apps/core/checks.py) -> `manage.py migrate` trong CMD của container sẽ dừng ngay với thông
  báo rõ ràng, thay vì chạy "ngầm" với sqlite / InMemory / ổ đĩa tạm rồi mất dữ liệu.
"""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

# Production không bao giờ chạy DEBUG, bất kể biến môi trường.
DEBUG = False

if not SECRET_KEY or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured(
        "SECRET_KEY chưa được đặt hoặc đang dùng key dev (django-insecure-...). "
        "Sinh key mới: python -c \"from django.core.management.utils import get_random_secret_key as k; print(k())\""
    )

# Bật system check "môi trường production đã đủ chưa" (xem apps/core/checks.py).
REQUIRE_PRODUCTION_ENV = True

# Loopback để HEALTHCHECK của Docker (gọi 127.0.0.1) không bị DisallowedHost.
ALLOWED_HOSTS = ALLOWED_HOSTS + ["127.0.0.1", "localhost"]

# Sau reverse proxy: tin header X-Forwarded-Proto để request.is_secure() đúng,
# nếu không mọi POST sẽ 403 "Origin checking failed" vì Django tưởng request là http.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

CSRF_TRUSTED_ORIGINS = [
    f"https://{'*' + h if h.startswith('.') else h}"
    for h in ALLOWED_HOSTS
    if h not in ("*", "127.0.0.1", "localhost")
]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)

# Render/Railway đã redirect http->https ở edge. Bật SECURE_SSL_REDIRECT=True nếu tự chạy
# sau Nginx không redirect; khi đó /health/ được miễn để HEALTHCHECK (http nội bộ) vẫn 200.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
