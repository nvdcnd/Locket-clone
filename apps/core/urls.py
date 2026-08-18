from django.shortcuts import path
from . import views

urlpatterns = [
    path('/', views.index, name='index'),
    path('health/', views.health_chech, name='health')
]
