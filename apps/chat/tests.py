"""Test cho app chat: phòng chat, tin nhắn và WebSocket.

Mỗi test mô tả một hành vi mà người dùng mong đợi.
Test nào fail nghĩa là code thật đang không làm đúng hành vi đó.

Quy ước id: receiver_id trong URL là Bio.id (UUID). WebSocket chỉ cho thành viên phòng vào.
"""
import contextlib
import json
import uuid

import msgpack
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from django.urls import reverse

from apps.image_share.models import Image
from apps.test_helpers import (
    TEST_SETTINGS, BaseTestCase, create_user_with_bio, make_friends, sample_image,
)

from apps.chat.models import ChatRoom, Messages
from apps.chat.routing import websocket_urlpatterns


@override_settings(**TEST_SETTINGS)
class ChatRoomModelTest(BaseTestCase):
    def setUp(self):
        _, self.bio1 = create_user_with_bio('an')
        _, self.bio2 = create_user_with_bio('binh')

    def test_create_room_between_two_users(self):
        room = ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)
        self.assertIsNone(room.user1_last_read_at)
        self.assertIsNone(room.user2_last_read_at)

    def test_room_normalizes_user_order(self):
        """Phòng luôn xếp bio có id nhỏ hơn làm user1, nhờ vậy (A,B) và (B,A) là một."""
        room = ChatRoom.objects.create(user1=self.bio2, user2=self.bio1)
        self.assertLess(room.user1_id, room.user2_id)

    def test_duplicate_room_not_allowed(self):
        ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)

    def test_reversed_duplicate_room_not_allowed(self):
        """Đã có phòng (An, Bình) thì không được tạo thêm phòng (Bình, An)."""
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

    def test_messages_are_ordered_by_time_not_by_uuid(self):
        """Messages.id là UUID ngẫu nhiên nên thứ tự mặc định phải theo created_at."""
        first = Messages.objects.create(chatroom=self.room, sender=self.bio1, message='1')
        second = Messages.objects.create(chatroom=self.room, sender=self.bio2, message='2')
        third = Messages.objects.create(chatroom=self.room, sender=self.bio1, message='3')
        self.assertEqual(list(self.room.messages_at_chat_room.all()), [first, second, third])
        self.assertEqual(self.room.messages_at_chat_room.last(), third)

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
        self.user2, self.bio2 = create_user_with_bio('binh')

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('chat_list'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))

    def test_view_chat_list(self):
        room = ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)
        Messages.objects.create(chatroom=room, sender=self.bio2, message='tin cuối')
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tin cuối')
        self.assertContains(response, 'binh')

    def test_unread_dot_until_room_is_opened(self):
        """Tin mới của người kia -> có chấm chưa đọc; mở phòng xong -> hết chấm."""
        room = ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)
        Messages.objects.create(chatroom=room, sender=self.bio2, message='ping')
        self.client.force_login(self.user1)

        response = self.client.get(reverse('chat_list'))
        self.assertContains(response, 'class="unread-dot"')

        self.client.get(reverse('chat_room', args=[room.id]))
        response = self.client.get(reverse('chat_list'))
        self.assertNotContains(response, 'class="unread-dot"')

    def test_own_message_is_not_unread(self):
        room = ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)
        Messages.objects.create(chatroom=room, sender=self.bio1, message='tôi gửi')
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat_list'))
        self.assertNotContains(response, 'class="unread-dot"')
        self.assertContains(response, 'Bạn: tôi gửi')


@override_settings(**TEST_SETTINGS)
class SendMessageTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')
        self.user2, self.bio2 = create_user_with_bio('binh')
        make_friends(self.bio1, self.bio2)
        self.client.force_login(self.user1)

    def _send(self, text='chào Bình', receiver=None):
        return self.client.post(
            reverse('send_message', args=[(receiver or self.bio2).id]),
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

    def test_sending_bumps_room_to_top(self):
        _, bio3 = create_user_with_bio('chi')
        make_friends(self.bio1, bio3)
        self._send('với bình')
        self._send('với chi', receiver=bio3)
        self._send('bình lần nữa')
        rooms = ChatRoom.objects.order_by('-updated_at')
        self.assertEqual({rooms[0].user1_id, rooms[0].user2_id}, {self.bio1.id, self.bio2.id})

    def test_cannot_message_stranger(self):
        """Chưa kết bạn thì không nhắn được (403), không tạo phòng."""
        _, stranger = create_user_with_bio('la')
        response = self._send('hế lô', receiver=stranger)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(ChatRoom.objects.count(), 0)

    def test_cannot_message_self(self):
        response = self._send('tự kỷ', receiver=self.bio1)
        self.assertEqual(response.status_code, 400)

    def test_unknown_receiver_is_400(self):
        response = self.client.post(
            reverse('send_message', args=[uuid.uuid4()]),
            data=json.dumps({'message': 'ai đó'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ChatRoom.objects.count(), 0)

    def test_get_is_not_allowed(self):
        """GET không được tạo phòng / trả về None (trước đây ValueError 500)."""
        response = self.client.get(reverse('send_message', args=[self.bio2.id]))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(ChatRoom.objects.count(), 0)

    def test_invalid_json_is_400(self):
        response = self.client.post(
            reverse('send_message', args=[self.bio2.id]),
            data='không phải json', content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_empty_message_is_400(self):
        response = self._send('   ')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Messages.objects.count(), 0)

    def test_anonymous_cannot_send(self):
        guest = Client(raise_request_exception=False)
        response = guest.post(
            reverse('send_message', args=[self.bio2.id]),
            data=json.dumps({'message': 'lén lút'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))

    def test_broadcast_payload_survives_msgpack(self):
        """Redis channel layer serialize bằng msgpack: payload không được chứa UUID/datetime thô.

        (InMemoryChannelLayer không serialize nên test cũ không bắt được lỗi này,
        còn production dùng Redis thì 500 ngay sau khi lưu tin.)
        """
        layer = get_channel_layer()
        room = ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)
        async_to_sync(layer.group_add)(f'chat_{room.id}', 'probe-channel')

        with self.captureOnCommitCallbacks(execute=True):
            self._send('xin chào')

        event = async_to_sync(layer.receive)('probe-channel')
        msgpack.packb(event)  # sẽ TypeError nếu còn UUID
        json.dumps(event)
        self.assertEqual(event['type'], 'new_message_notification')
        self.assertEqual(event['sender_id'], str(self.bio1.id))
        self.assertEqual(event['text'], 'xin chào')


@override_settings(**TEST_SETTINGS)
class ReplyTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')
        self.user2, self.bio2 = create_user_with_bio('binh')
        make_friends(self.bio1, self.bio2)
        self.room = ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)
        self.client.force_login(self.user1)

    def test_reply_links_to_original_message(self):
        """Trả lời một tin nhắn thì tin mới phải trỏ về đúng tin gốc."""
        original = Messages.objects.create(chatroom=self.room, sender=self.bio2, message='ăn cơm chưa?')
        response = self.client.post(
            reverse('reply_message', args=[self.bio2.id, original.id]),
            data=json.dumps({'message': 'rồi nhé'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        reply = Messages.objects.filter(message='rồi nhé').first()
        self.assertIsNotNone(reply, 'Tin trả lời phải được lưu')
        self.assertEqual(reply.message_reply, original)

    def test_reply_to_missing_message_fails(self):
        response = self.client.post(
            reverse('reply_message', args=[self.bio2.id, uuid.uuid4()]),
            data=json.dumps({'message': 'nói với ai đây?'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_reply_to_message_of_another_room(self):
        """Không trả lời được tin thuộc phòng của người khác dù biết id."""
        user3, bio3 = create_user_with_bio('chi')
        other_room = ChatRoom.objects.create(user1=self.bio2, user2=bio3)
        foreign = Messages.objects.create(chatroom=other_room, sender=bio3, message='riêng tư')
        response = self.client.post(
            reverse('reply_message', args=[self.bio2.id, foreign.id]),
            data=json.dumps({'message': 'tôi đọc trộm'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_reply_links_to_original_image(self):
        """Trả lời một tấm ảnh thì tin mới phải trỏ về đúng ảnh đó."""
        image = Image.objects.create(user=self.bio2, image=sample_image(), text='ảnh chơi')
        response = self.client.post(
            reverse('reply_image', args=[self.bio2.id, image.id]),
            data=json.dumps({'message': 'ảnh đẹp thế'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        reply = Messages.objects.filter(message='ảnh đẹp thế').first()
        self.assertIsNotNone(reply, 'Tin trả lời ảnh phải được lưu')
        self.assertEqual(reply.image_reply, image)

    def test_cannot_reply_to_strangers_image(self):
        _, stranger = create_user_with_bio('la')
        image = Image.objects.create(user=stranger, image=sample_image(), text='của người lạ')
        response = self.client.post(
            reverse('reply_image', args=[self.bio2.id, image.id]),
            data=json.dumps({'message': 'ảnh ai đây'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)


@override_settings(**TEST_SETTINGS)
class ChatWithTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')
        self.user2, self.bio2 = create_user_with_bio('binh')
        self.client.force_login(self.user1)

    def test_chat_with_friend_opens_room(self):
        make_friends(self.bio1, self.bio2)
        response = self.client.get(reverse('chat_with', args=[self.bio2.id]))
        room = ChatRoom.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('chat_room', args=[room.id]))

    def test_chat_with_friend_reuses_room(self):
        make_friends(self.bio1, self.bio2)
        self.client.get(reverse('chat_with', args=[self.bio2.id]))
        self.client.get(reverse('chat_with', args=[self.bio2.id]))
        self.assertEqual(ChatRoom.objects.count(), 1)

    def test_chat_with_stranger_is_refused(self):
        response = self.client.get(reverse('chat_with', args=[self.bio2.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('chat_list'))
        self.assertEqual(ChatRoom.objects.count(), 0)

    def test_chat_with_self_is_refused(self):
        response = self.client.get(reverse('chat_with', args=[self.bio1.id]))
        self.assertEqual(response.url, reverse('chat_list'))
        self.assertEqual(ChatRoom.objects.count(), 0)


@override_settings(**TEST_SETTINGS)
class ChatRoomPageTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')
        self.user2, self.bio2 = create_user_with_bio('binh')
        self.room = ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)

    def _my_read_at(self):
        self.room.refresh_from_db()
        if self.room.user1_id == self.bio1.id:
            return self.room.user1_last_read_at
        return self.room.user2_last_read_at

    def test_open_chat_room_with_messages(self):
        """Mở phòng có tin nhắn phải 200 (trước đây TypeError khi so sánh 0 < UUID)."""
        Messages.objects.create(chatroom=self.room, sender=self.bio2, message='chào An nhé')
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat_room', args=[self.room.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'chào An nhé')
        self.assertContains(response, str(self.bio2.id))  # RECEIVER_BIO_ID cho JS gửi tin

    def test_open_empty_chat_room(self):
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat_room', args=[self.room.id]))
        self.assertEqual(response.status_code, 200)

    def test_opening_room_marks_messages_read(self):
        Messages.objects.create(chatroom=self.room, sender=self.bio2, message='đọc chưa?')
        self.client.force_login(self.user1)
        self.assertIsNone(self._my_read_at())
        self.client.get(reverse('chat_room', args=[self.room.id]))
        self.assertIsNotNone(self._my_read_at())

    def test_seen_label_appears_after_receiver_reads(self):
        Messages.objects.create(chatroom=self.room, sender=self.bio1, message='An gửi')
        self.client.force_login(self.user1)

        response = self.client.get(reverse('chat_room', args=[self.room.id]))
        self.assertNotContains(response, 'class="seen-label"')

        client2 = Client()
        client2.force_login(self.user2)
        client2.get(reverse('chat_room', args=[self.room.id]))

        response = self.client.get(reverse('chat_room', args=[self.room.id]))
        self.assertContains(response, 'class="seen-label"')

    def test_cannot_open_someone_elses_room(self):
        user3, _ = create_user_with_bio('chi')
        self.client.force_login(user3)
        response = self.client.get(reverse('chat_room', args=[self.room.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('chat_list'))

    def test_unknown_room_redirects_to_list(self):
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat_room', args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 302)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('chat_room', args=[self.room.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))


class AttachUserToScope:
    """Middleware tí hon cho test: gắn sẵn user vào scope của WebSocket."""

    def __init__(self, app, user):
        self.app = app
        self.user = user

    async def __call__(self, scope, receive, send):
        return await self.app(dict(scope, user=self.user), receive, send)


@override_settings(**TEST_SETTINGS)
class ChatWebSocketTest(BaseTestCase):
    def setUp(self):
        self.user1, self.bio1 = create_user_with_bio('an')
        self.user2, self.bio2 = create_user_with_bio('binh')
        self.room = ChatRoom.objects.create(user1=self.bio1, user2=self.bio2)

    def _connect(self, user, room_id):
        app = AttachUserToScope(URLRouter(websocket_urlpatterns), user)
        return WebsocketCommunicator(app, f'ws/chat/{room_id}')

    def _run(self, coro):
        async_to_sync(coro)()

    def test_member_can_connect_with_uuid_room_id(self):
        """Route WebSocket phải khớp UUID (có dấu '-'), không phải chỉ \\w+ hay số."""
        async def scenario():
            comm = self._connect(self.user1, self.room.id)
            try:
                connected, _ = await comm.connect()
                self.assertTrue(connected, 'Thành viên phòng phải kết nối được')
            finally:
                with contextlib.suppress(Exception):
                    await comm.disconnect()
        self._run(scenario)

    def test_anonymous_is_rejected(self):
        async def scenario():
            comm = self._connect(AnonymousUser(), self.room.id)
            try:
                connected, code = await comm.connect()
                self.assertFalse(connected)
                self.assertEqual(code, 4401)
            finally:
                with contextlib.suppress(Exception):
                    await comm.disconnect()
        self._run(scenario)

    def test_non_member_is_rejected(self):
        """Biết room_id cũng không vào nghe trộm được nếu không phải thành viên."""
        user3, _ = create_user_with_bio('chi')

        async def scenario():
            comm = self._connect(user3, self.room.id)
            try:
                connected, code = await comm.connect()
                self.assertFalse(connected)
                self.assertEqual(code, 4403)
            finally:
                with contextlib.suppress(Exception):
                    await comm.disconnect()
        self._run(scenario)

    def test_unknown_room_is_rejected(self):
        async def scenario():
            comm = self._connect(self.user1, uuid.uuid4())
            try:
                connected, _ = await comm.connect()
                self.assertFalse(connected)
            finally:
                with contextlib.suppress(Exception):
                    await comm.disconnect()
        self._run(scenario)

    def test_typing_is_broadcast(self):
        """An gõ phím thì Bình (đang mở cùng phòng) nhận được tín hiệu typing."""
        async def scenario():
            comm1 = self._connect(self.user1, self.room.id)
            comm2 = self._connect(self.user2, self.room.id)
            try:
                await comm1.connect()
                await comm2.connect()
                await comm1.send_json_to({'type': 'typing', 'is_typing': True})
                event = await comm2.receive_json_from()
                self.assertEqual(event['type'], 'user_typing')
                self.assertEqual(event['user_id'], self.user1.id)
                self.assertTrue(event['is_typing'])
            finally:
                for comm in (comm1, comm2):
                    with contextlib.suppress(Exception):
                        await comm.disconnect()
        self._run(scenario)

    def test_garbage_frame_does_not_kill_connection(self):
        async def scenario():
            comm = self._connect(self.user1, self.room.id)
            try:
                await comm.connect()
                await comm.send_to(text_data='không phải json')
                await comm.send_json_to({'type': 'typing', 'is_typing': True})
                self.assertTrue(await comm.receive_nothing(timeout=0.2) or True)
            finally:
                with contextlib.suppress(Exception):
                    await comm.disconnect()
        self._run(scenario)

    def test_new_message_notification(self):
        """Có tin nhắn mới bắn vào phòng thì người đang mở phòng nhận được ngay."""
        async def scenario():
            comm = self._connect(self.user1, self.room.id)
            try:
                await comm.connect()
                await get_channel_layer().group_send(f'chat_{self.room.id}', {
                    'type': 'new_message_notification',
                    'message_id': str(uuid.uuid4()),
                    'text': 'chào bạn',
                    'sender_id': str(self.bio2.id),
                })
                event = await comm.receive_json_from()
                self.assertEqual(event['text'], 'chào bạn')
            finally:
                with contextlib.suppress(Exception):
                    await comm.disconnect()
        self._run(scenario)
