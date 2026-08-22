from django.urls import path

from . import consumers

# Dùng path() với converter <uuid:>: id phòng là UUID (có dấu '-'), regex \w+ của bản cũ
# không khớp, còn re_path(r'...<uuid:room_id>') thì coi chuỗi '<uuid:room_id>' là ký tự thường.
# Không có '/' cuối để khớp với JS: new WebSocket(host + '/ws/chat/' + ROOM_ID).
websocket_urlpatterns = [
    path('ws/chat/<uuid:room_id>', consumers.ChatConsumer.as_asgi()),
]
