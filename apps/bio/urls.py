from django.urls import path
from .views import *

urlpatterns = [
    path('authentication/login', login_view , name='login'),
    path('authentication/signup', signup, name='signup'),
    path('authentication/check', check, name='check'),
    path('authentication/logout', log_out, name="logout"),

    path('friends/', friends_list, name='friends_list'),
    path('friends/<int:id>', friends_information, name="friends_information"),
    path('friends/remove/<int:id>',unfriend,name='unfriend'),
    path('friends/add/<int:id>',add_friend,name='add_friend'),

    path('',bio,name='bio'),
    path("information/change/",bio_information_change,name="bio_information_change"),
]
