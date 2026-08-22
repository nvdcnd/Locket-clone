from django.urls import path

from . import views

urlpatterns = [
    # last_page: ISO datetime (JS gửi encodeURIComponent(last_page)); offset: số ảnh mỗi lần tải.
    path('fetch/<str:last_page>/<int:offset>', views.image_list_infinity_scroll, name='image_list_infinity_scroll'),
    path('create', views.image_create, name='image_create'),
    path('<uuid:id>/emoji', views.emojing_image, name='emojing_image'),
    path('delete/<uuid:id>', views.image_delete, name='image_delete'),
]
