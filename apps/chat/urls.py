from django.shortcuts import path
from . import views

urlpatterns = [
    path("/chat/", views.chat_lists, name="chat_list"),
    path('/chat/<int:id>', views.room, name="chat_room"),
    path('/chat/<int:id>/create/message'),
]
