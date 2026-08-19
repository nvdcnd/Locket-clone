"""Test cho app chat: phòng chat, tin nhắn và WebSocket.

Mỗi test mô tả một hành vi mà người dùng mong đợi.
Test nào fail nghĩa là code thật đang không làm đúng hành vi đó.
"""
import contextlib
import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from django.urls import reverse

from apps.image_share.models import Image
from apps.test_helpers import TEST_SETTINGS as BASE_TEST_SETTINGS
from apps.test_helpers import BaseTestCase, create_user_with_bio, sample_image

from apps.chat.models import ChatRoom, Messages
from apps.chat.routing import websocket_urlpatterns

# Chat cần thêm channel layer chạy trong RAM thay cho Redis thật.
TEST_SETTINGS = dict(
    BASE_TEST_SETTINGS,
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)


@override_settings(**TEST_SETTINGS)
class ChatRoomModelTest(BaseTestCase):
    def setUp(self):
        _, self.bio1 = create_user_with_bio('an')
        _, self.bio2 = create_user_with_bio('binh')

    def test_create_room_between_two_users(self):
        room = ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)
        self.assertEqual(room.user1_last_read_msg_id, 0)
        self.assertEqual(room.user2_last_read_msg_id, 0)

    def test_duplicate_room_not_allowed(self):
        ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)

    def test_reversed_duplicate_room_not_allowed(self):
        """Đã có phòng (An, Bình) thì không được tạo thêm phòng (Bình, An).

        Comment trong model nói rõ "2 người không thể tạo 2 phòng chat trùng
        nhau", nhưng unique_together hiện tại không chặn được chiều ngược lại.
        """
        ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ChatRoom.objects.create(user1=self.bio2, user2=self.bio1)


@override_settings(**TEST_SETTINGS)
class MessagesModelTest(BaseTestCase):
    def setUp(self):
        _, self.bio1 = create_user_with_bio('an')
        _, self.bio2 = create_user_with_bio('binh')
        self.room = ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)

    def test_create_plain_message(self):
        msg = Messages.objects.create(chatroom=self.room, sender=self.bio1, message='chào Bình')
        self.assertEqual(msg.message, 'chào Bình')
        self.assertIsNone(msg.image_reply)
        self.assertIsNone(msg.message_reply)

    def test_reply_to_message(self):
        original = Messages.objects.create(chatroom=self.room, sender=self.bio1, message='ăn cơm chưa?')
        reply = Messages.objects.create(
            chatroom=self.room, sender=self.bio2,
            message='rồi nhé', message_reply=original,
        )
        self.assertEqual(reply.message_reply, original)

    def test_reply_to_image(self):
        image = Image.objects.create(user=self.bio1, image=sample_image(), text='ảnh đẹp')
        reply = Messages.objects.create(
            chatroom=self.room, sender=self.bio2,
            message='ảnh xịn đấy', image_reply=image,
        )
        self.assertEqual(reply.image_reply, image)

    def test_deleting_room_deletes_messages(self):
        Messages.objects.create(chatroom=self.room, sender=self.bio1, message='chào')
        self.room.delete()
        self.assertEqual(Messages.objects.count(), 0)


@override_settings(**TEST_SETTINGS)
class ChatListTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('chat_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_view_chat_list(self):
        _, bio2 = create_user_with_bio('binh')
        ChatRoom.objects.create(user1=self.bio1, user2=bio2)
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat_list'))
        self.assertEqual(response.status_code, 200)


@override_settings(**TEST_SETTINGS)
class SendMessageTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')
        self.user2, self.bio2 = create_user_with_bio('binh')
        self.client.force_login(self.user1)

    def _send(self, text='chào Bình'):
        return self.client.post(
            reverse('send_message', args=[self.user2.id]),
            data=json.dumps({'message': text}),
            content_type='application/json',
        )

    def test_message_is_saved(self):
        self._send('chào Bình')
        msg = Messages.objects.filter(message='chào Bình').first()
        self.assertIsNotNone(msg, 'Tin nhắn phải được lưu vào hệ thống')
        self.assertEqual(msg.sender, self.bio1)

    def test_room_is_created_automatically(self):
        """Nhắn cho người chưa từng chat thì phòng được tạo, nhắn tiếp không tạo thêm."""
        self._send('tin thứ nhất')
        self._send('tin thứ hai')
        self.assertEqual(ChatRoom.objects.count(), 1)

    def test_send_returns_success(self):
        response = self._send()
        self.assertEqual(response.status_code, 200)
        self.assertIn('message_id', json.loads(response.content))

    def test_anonymous_cannot_send(self):
        guest = Client(raise_request_exception=False)
        response = guest.post(
            reverse('send_message', args=[self.user2.id]),
            data=json.dumps({'message': 'lén lút'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


@override_settings(**TEST_SETTINGS)
class ReplyTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')
        self.user2, self.bio2 = create_user_with_bio('binh')
        self.room = ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)
        self.client.force_login(self.user1)

    def test_reply_links_to_original_message(self):
        """Trả lời một tin nhắn thì tin mới phải trỏ về đúng tin gốc."""
        original = Messages.objects.create(chatroom=self.room, sender=self.bio2, message='ăn cơm chưa?')
        self.client.post(
            reverse('reply_message', args=[self.user2.id, original.id]),
            data=json.dumps({'message': 'rồi nhé'}),
            content_type='application/json',
        )
        reply = Messages.objects.filter(message='rồi nhé').first()
        self.assertIsNotNone(reply, 'Tin trả lời phải được lưu')
        self.assertEqual(reply.message_reply, original)

    def test_reply_to_missing_message_fails(self):
        response = self.client.post(
            reverse('reply_message', args=[self.user2.id, 999999]),
            data=json.dumps({'message': 'nói với ai đây?'}),
            content_type='application/json',
        )
        self.assertGreaterEqual(response.status_code, 400)

    def test_reply_links_to_original_image(self):
        """Trả lời một tấm ảnh thì tin mới phải trỏ về đúng ảnh đó."""
        image = Image.objects.create(user=self.bio2, image=sample_image(), text='ảnh chơi')
        self.client.post(
            reverse('reply_image', args=[self.user2.id, image.id]),
            data=json.dumps({'message': 'ảnh đẹp thế'}),
            content_type='application/json',
        )
        reply = Messages.objects.filter(message='ảnh đẹp thế').first()
        self.assertIsNotNone(reply, 'Tin trả lời ảnh phải được lưu')
        self.assertEqual(reply.image_reply, image)


@override_settings(**TEST_SETTINGS)
class ChatRoomPageTest(BaseTestCase):
    def test_open_chat_room(self):
        user, _ = create_user_with_bio('an')
        client = Client(raise_request_exception=False)
        client.force_login(user)
        response = client.get(reverse('chat_room', args=[1]))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_is_redirected_to_login(self):
        """Phòng chat giờ đã yêu cầu đăng nhập mới xem được."""
        client = Client(raise_request_exception=False)
        response = client.get(reverse('chat_room', args=[1]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


class AttachUserToScope:
    """Middleware tí hon cho test: gắn sẵn user vào scope của WebSocket."""

    def __init__(self, app, user):
        self.app = app
        self.user = user

    async def __call__(self, scope, receive, send):
        return await self.app(dict(scope, user=self.user), receive, send)


@override_settings(**TEST_SETTINGS)
class ChatWebSocketTest(BaseTestCase):
    def _connect(self, user, room_id=1):
        app = AttachUserToScope(URLRouter(websocket_urlpatterns), user)
        return WebsocketCommunicator(app, f'ws/chat/{room_id}')

    def test_connect_to_room(self):
        user, _ = create_user_with_bio('an')

        async def scenario():
            comm = self._connect(user)
            try:
                connected, _ = await comm.connect()
                self.assertTrue(connected, 'WebSocket phải kết nối được vào phòng chat')
            finally:
                with contextlib.suppress(Exception):
                    await comm.disconnect()

        async_to_sync(scenario)()

    def test_typing_is_broadcast(self):
        """An gõ phím thì Bình (đang mở cùng phòng) nhận được tín hiệu typing."""
        user1, _ = create_user_with_bio('an')
        user2, _ = create_user_with_bio('binh')

        async def scenario():
            comm1 = self._connect(user1)
            comm2 = self._connect(user2)
            try:
                await comm1.connect()
                await comm2.connect()
                await comm1.send_json_to({'type': 'typing', 'is_typing': True})
                event = await comm2.receive_json_from()
                self.assertEqual(event['type'], 'user_typing')
                self.assertEqual(event['user_id'], user1.id)
                self.assertTrue(event['is_typing'])
            finally:
                for comm in (comm1, comm2):
                    with contextlib.suppress(Exception):
                        await comm.disconnect()

        async_to_sync(scenario)()

    def test_new_message_notification(self):
        """Có tin nhắn mới bắn vào phòng thì người đang mở phòng nhận được ngay."""
        user, _ = create_user_with_bio('an')

        async def scenario():
            comm = self._connect(user, room_id=7)
            try:
                await comm.connect()
                await get_channel_layer().group_send('chat_7', {
                    'type': 'new_message_notification',
                    'message_id': 1,
                    'text': 'chào bạn',
                    'sender_id': user.id,
                })
                event = await comm.receive_json_from()
                self.assertEqual(event['text'], 'chào bạn')
            finally:
                with contextlib.suppress(Exception):
                    await comm.disconnect()

        async_to_sync(scenario)()
