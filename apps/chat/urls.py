from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat_lists, name="chat_list"),
    path('<uuid:room_id>', views.room, name="chat_room"),
    path('with/<uuid:receiver_id>/', views.chat_with, name="chat_with"),
    path('to/<uuid:receiver_id>/', views.send_message, name="send_message"),
    path('to/<uuid:receiver_id>/reply/message/<uuid:msg_id>', views.reply_message, name='reply_message'),
    path('to/<uuid:receiver_id>/reply/image/<uuid:img_id>', views.reply_image, name="reply_image")
]
