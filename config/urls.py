"""
URL configuration for drf project.

https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("chat/", include("apps.chat.urls")),
    path("image/", include("apps.image_share.urls")),
    path("user/", include("apps.bio.urls")),
    path("forgot/", include("apps.forgot_password.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("oauth/", include("allauth.urls")),
]

# Chỉ có tác dụng khi DEBUG=True: phục vụ ảnh upload từ MEDIA_ROOT (FileSystemStorage ở dev).
# Static ở dev đã do django.contrib.staticfiles / WhiteNoise lo.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
