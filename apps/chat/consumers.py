import json
from channels.generic.websocket import WebsocketConsumer

class ChatConsumer(WebsocketConsumer):
    async def connect(self):
        self.room = self.scope['url_route']['kwargs']['id']
        self.room_name = f'chat_{self.room_name}'

        await self.chanel_layer.group_add(
            self.room,
            self.room_name
        )
        await self.accept()

    async def disconnect(self, code):
        return super().disconnect(code)

    async def receive(self, text_data = None, bytes_data = None):
        data = json.loads(text_data)
        event_type == data.get('type')

        if event_type == 'typing':
            # Bắn event tới tất cả mọi người trong nhóm trừ bản thân
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_typing', # Tên hàm sẽ gọi ở dưới
                    'user_id': self.scope['user'].id,
                    'is_typing': data.get('is_typing')
                }
            )
        #self.send(text_data=json.dump)
        #return super().receive(text_data, bytes_data)

    async def user_typing(self, event):
        await self.send(text_data=json.dump(event))