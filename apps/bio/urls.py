from django.urls import path
from .views import *

urlpatterns = [
    path('authentication/login', login , name='login'),
    path('authentication/signup', signup, name='signup'),
    path('authentication/check', check, name='check'),

    path('un/friend/<int:id>',unfriend,name='unfriend'),
    path('add/friend/<int:id>',add_friend,name='add_friend'),

    path('',bio,name='bio'),
    path("information/change/",bio_information_change,name="bio_information_change"),
]
