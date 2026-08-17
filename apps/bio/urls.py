from django.urls import path
from .views import *

urlpatterns = [
    path('/authentication/login', login , name='login'),
    path('/authentication/signup', signup, name='signup'),
    path('/authentication/check', check, name='check')
]
