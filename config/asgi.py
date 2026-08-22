"""
ASGI config for drf project.

Thứ tự import QUAN TRỌNG: get_asgi_application() phải chạy trước khi import routing,
vì routing -> consumers -> models; import model trước khi app registry sẵn sàng sẽ
ném AppRegistryNotReady. (Theo đúng tài liệu của Channels.)

https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.chat.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
