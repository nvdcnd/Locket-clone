"""System check: môi trường production đã đủ chưa.

Chỉ chạy khi settings đặt REQUIRE_PRODUCTION_ENV = True (config/settings/production.py).
`manage.py migrate` (bước đầu trong CMD của container) luôn chạy system checks, nên nếu
thiếu biến môi trường thì container dừng ngay với thông báo rõ ràng, thay vì chạy "ngầm"
với sqlite / InMemoryChannelLayer / ổ đĩa tạm rồi mất dữ liệu hoặc WebSocket không hoạt động.

`collectstatic` (chạy lúc docker build) không chạy system checks nên không cần các biến này.
"""
from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security)
def production_environment_check(app_configs, **kwargs):
    if not getattr(settings, "REQUIRE_PRODUCTION_ENV", False):
        return []

    errors = []

    if not getattr(settings, "DATABASE_URL", ""):
        errors.append(Error(
            "DATABASE_URL chưa được đặt: production đang rơi về sqlite trong container (mất dữ liệu khi redeploy).",
            hint="Đặt DATABASE_URL=postgres://user:pass@host:5432/db",
            id="locket.E001",
        ))

    if not getattr(settings, "REDIS_URL", ""):
        errors.append(Error(
            "REDIS_URL / REDIS_HOST_URL chưa được đặt: channel layer đang là InMemory, "
            "WebSocket chỉ hoạt động trong 1 process và không chia sẻ giữa các worker.",
            hint="Đặt REDIS_URL=redis://host:6379/0",
            id="locket.E002",
        ))

    if not getattr(settings, "USE_CLOUDINARY", False):
        errors.append(Error(
            "Thiếu CLOUDINARY_CLOUD_NAME / CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET: "
            "ảnh upload đang lưu vào ổ đĩa container (mất khi redeploy).",
            hint="Đặt đủ 3 biến CLOUDINARY_* hoặc đổi STORAGES['default'] sang backend bền khác.",
            id="locket.E003",
        ))

    real_hosts = [h for h in settings.ALLOWED_HOSTS if h not in ("127.0.0.1", "localhost")]
    if not real_hosts:
        errors.append(Error(
            "ALLOWED_HOSTS chưa được đặt.",
            hint="Đặt ALLOWED_HOSTS=ten-mien.com (nhiều host cách nhau bằng dấu phẩy).",
            id="locket.E004",
        ))
    elif "*" in real_hosts:
        errors.append(Error(
            "ALLOWED_HOSTS chứa '*': AllowedHostsOriginValidator sẽ chấp nhận WebSocket từ MỌI origin "
            "(Cross-Site WebSocket Hijacking).",
            hint="Liệt kê host thật thay cho '*'.",
            id="locket.E005",
        ))

    return errors
