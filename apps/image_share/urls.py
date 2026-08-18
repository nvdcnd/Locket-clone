from django.shortcuts import path
from . import views

urlpatterns = [
    path('fetch/<last_page>', views.image_list_infinity_scroll, name='image_list_infinity_scroll'),
    path('create', views.image_create, name="image_create"),
    path('<int:id>/emoji', views.emojing_image, name="emojing_image"),
    path('delete/<int:id>',views.image_delete, name='image_delete')
]
