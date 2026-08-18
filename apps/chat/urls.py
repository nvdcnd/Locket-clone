from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat_lists, name="chat_list"),
    path('<int:id>', views.room, name="chat_room"),
    path('to/<int:receiver_id>/', views.send_message, name="send_message"),
    path('to/<int:receiver_id>/reply/message/<int:msg_id>', views.reply_message, name='reply_message'),
    path('to/<int:receiver_id>/reply/image/<int:img_id>', views.reply_image, name="reply_image")
]
