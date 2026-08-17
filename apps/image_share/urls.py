from django.shortcuts import path
from . import views

urlpatterns = [
    path('/image/fetch/<last_page>', views.image_list_infinity_scroll, name='image_list_infinity_scroll'),
    path('/image/create', views.image_create, name="image_create"),
    path('/image/<int:id>/emoji', views.emojing_image, name="emojing_image")
]
