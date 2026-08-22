import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q

from .models import ChatRoom

# Mã đóng kết nối tuỳ ứng dụng (dải 4000-4999 dành cho application theo RFC 6455).
CLOSE_UNAUTHENTICATED = 4401
CLOSE_FORBIDDEN = 4403


class ChatConsumer(AsyncWebsocketConsumer):
    """Một kết nối = một người dùng đang mở một phòng chat.

    Chỉ người đã đăng nhập VÀ là thành viên của phòng mới được vào group
    `chat_<room_id>`; nếu không, ai đoán được room_id cũng đọc trộm được tin nhắn.
    """

    room_name = None

    async def connect(self):
        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return

        self.room_id = self.scope['url_route']['kwargs']['room_id']
        if not await self._is_member(user, self.room_id):
            await self.close(code=CLOSE_FORBIDDEN)
            return

        self.room_name = f'chat_{self.room_id}'
        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()

    @staticmethod
    @database_sync_to_async
    def _is_member(user, room_id):
        return ChatRoom.objects.filter(
            Q(user1__user=user) | Q(user2__user=user), id=room_id,
        ).exists()

    async def disconnect(self, code):
        if self.room_name:
            await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except ValueError:
            return
        if not isinstance(data, dict):
            return

        if data.get('type') == 'typing':
            await self.channel_layer.group_send(
                self.room_name,
                {
                    'type': 'user_typing',  # -> self.user_typing
                    'user_id': self.scope['user'].id,
                    'is_typing': bool(data.get('is_typing')),
                },
            )

    async def user_typing(self, event):
        await self.send(text_data=json.dumps(event))

    async def new_message_notification(self, event):
        await self.send(text_data=json.dumps(event))
