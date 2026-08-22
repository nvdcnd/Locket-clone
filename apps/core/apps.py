from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        # Đăng ký system check cho môi trường production (xem apps/core/checks.py).
        from . import checks  # noqa: F401
