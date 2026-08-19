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
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.image_share.models import Image
from apps.test_helpers import CAI_DAT_TEST as CAI_DAT_CHUNG
from apps.test_helpers import TestCoDuLieu, anh_mau, tao_nguoi_dung

from apps.chat.models import ChatRoom, Messages
from apps.chat.routing import websocket_urlpatterns

# Chat cần thêm channel layer chạy trong RAM thay cho Redis thật.
CAI_DAT_TEST = dict(
    CAI_DAT_CHUNG,
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)


@override_settings(**CAI_DAT_TEST)
class ChatRoomModelTest(TestCoDuLieu):
    def setUp(self):
        _, self.bio_an = tao_nguoi_dung('an')
        _, self.bio_binh = tao_nguoi_dung('binh')

    def test_tao_phong_chat_giua_hai_nguoi(self):
        phong = ChatRoom.objects.create(user1=self.bio_an, user2=self.bio_binh)
        self.assertEqual(phong.user1_last_read_msg_id, 0)
        self.assertEqual(phong.user2_last_read_msg_id, 0)

    def test_khong_tao_duoc_hai_phong_giong_het_nhau(self):
        ChatRoom.objects.create(user1=self.bio_an, user2=self.bio_binh)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ChatRoom.objects.create(user1=self.bio_an, user2=self.bio_binh)

    def test_khong_tao_duoc_phong_dao_chieu(self):
        """Đã có phòng (An, Bình) thì không được tạo thêm phòng (Bình, An).

        Comment trong model nói rõ "2 người không thể tạo 2 phòng chat trùng
        nhau", nhưng unique_together hiện tại không chặn được chiều ngược lại.
        """
        ChatRoom.objects.create(user1=self.bio_an, user2=self.bio_binh)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ChatRoom.objects.create(user1=self.bio_binh, user2=self.bio_an)


@override_settings(**CAI_DAT_TEST)
class MessagesModelTest(TestCoDuLieu):
    def setUp(self):
        _, self.bio_an = tao_nguoi_dung('an')
        _, self.bio_binh = tao_nguoi_dung('binh')
        self.phong = ChatRoom.objects.create(user1=self.bio_an, user2=self.bio_binh)

    def test_tao_tin_nhan_thuong(self):
        tin = Messages.objects.create(chatroom=self.phong, sender=self.bio_an, message='chào Bình')
        self.assertEqual(tin.message, 'chào Bình')
        self.assertIsNone(tin.image_reply)
        self.assertIsNone(tin.message_reply)

    def test_tin_nhan_tra_loi_tin_nhan(self):
        goc = Messages.objects.create(chatroom=self.phong, sender=self.bio_an, message='ăn cơm chưa?')
        tra_loi = Messages.objects.create(
            chatroom=self.phong, sender=self.bio_binh,
            message='rồi nhé', message_reply=goc,
        )
        self.assertEqual(tra_loi.message_reply, goc)

    def test_tin_nhan_tra_loi_anh(self):
        anh = Image.objects.create(user=self.bio_an, image=anh_mau(), text='ảnh đẹp')
        tra_loi = Messages.objects.create(
            chatroom=self.phong, sender=self.bio_binh,
            message='ảnh xịn đấy', image_reply=anh,
        )
        self.assertEqual(tra_loi.image_reply, anh)

    def test_xoa_phong_thi_tin_nhan_mat_theo(self):
        Messages.objects.create(chatroom=self.phong, sender=self.bio_an, message='chào')
        self.phong.delete()
        self.assertEqual(Messages.objects.count(), 0)


@override_settings(**CAI_DAT_TEST)
class DanhSachChatTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user_an, self.bio_an = tao_nguoi_dung('an')

    def test_chua_dang_nhap_bi_day_ve_trang_login(self):
        response = self.client.get(reverse('chat_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_xem_danh_sach_doan_chat(self):
        _, bio_binh = tao_nguoi_dung('binh')
        ChatRoom.objects.create(user1=self.bio_an, user2=bio_binh)
        self.client.force_login(self.user_an)
        response = self.client.get(reverse('chat_list'))
        self.assertEqual(response.status_code, 200)


@override_settings(**CAI_DAT_TEST)
class GuiTinNhanTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user_an, self.bio_an = tao_nguoi_dung('an')
        self.user_binh, self.bio_binh = tao_nguoi_dung('binh')
        self.client.force_login(self.user_an)

    def _gui_tin(self, noi_dung='chào Bình'):
        return self.client.post(
            reverse('send_message', args=[self.user_binh.id]),
            data=json.dumps({'message': noi_dung}),
            content_type='application/json',
        )

    def test_gui_tin_thi_tin_duoc_luu(self):
        self._gui_tin('chào Bình')
        tin = Messages.objects.filter(message='chào Bình').first()
        self.assertIsNotNone(tin, 'Tin nhắn phải được lưu vào hệ thống')
        self.assertEqual(tin.sender, self.bio_an)

    def test_tu_dong_tao_phong_khi_chua_co(self):
        """Nhắn cho người chưa từng chat thì phòng được tạo, nhắn tiếp không tạo thêm."""
        self._gui_tin('tin thứ nhất')
        self._gui_tin('tin thứ hai')
        self.assertEqual(ChatRoom.objects.count(), 1)

    def test_gui_tin_bao_thanh_cong(self):
        response = self._gui_tin()
        self.assertEqual(response.status_code, 200)
        self.assertIn('message_id', json.loads(response.content))

    def test_chua_dang_nhap_thi_khong_gui_duoc(self):
        khach = Client(raise_request_exception=False)
        response = khach.post(
            reverse('send_message', args=[self.user_binh.id]),
            data=json.dumps({'message': 'lén lút'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


@override_settings(**CAI_DAT_TEST)
class TraLoiTinNhanTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user_an, self.bio_an = tao_nguoi_dung('an')
        self.user_binh, self.bio_binh = tao_nguoi_dung('binh')
        self.phong = ChatRoom.objects.create(user1=self.bio_an, user2=self.bio_binh)
        self.client.force_login(self.user_an)

    def test_tra_loi_tin_nhan_giu_dung_tin_goc(self):
        """Trả lời một tin nhắn thì tin mới phải trỏ về đúng tin gốc."""
        goc = Messages.objects.create(chatroom=self.phong, sender=self.bio_binh, message='ăn cơm chưa?')
        self.client.post(
            reverse('reply_message', args=[self.user_binh.id, goc.id]),
            data=json.dumps({'message': 'rồi nhé'}),
            content_type='application/json',
        )
        tra_loi = Messages.objects.filter(message='rồi nhé').first()
        self.assertIsNotNone(tra_loi, 'Tin trả lời phải được lưu')
        self.assertEqual(tra_loi.message_reply, goc)

    def test_tra_loi_tin_khong_ton_tai_thi_bao_loi(self):
        response = self.client.post(
            reverse('reply_message', args=[self.user_binh.id, 999999]),
            data=json.dumps({'message': 'nói với ai đây?'}),
            content_type='application/json',
        )
        self.assertGreaterEqual(response.status_code, 400)

    def test_tra_loi_anh_giu_dung_anh_goc(self):
        """Trả lời một tấm ảnh thì tin mới phải trỏ về đúng ảnh đó."""
        anh = Image.objects.create(user=self.bio_binh, image=anh_mau(), text='ảnh chơi')
        self.client.post(
            reverse('reply_image', args=[self.user_binh.id, anh.id]),
            data=json.dumps({'message': 'ảnh đẹp thế'}),
            content_type='application/json',
        )
        tra_loi = Messages.objects.filter(message='ảnh đẹp thế').first()
        self.assertIsNotNone(tra_loi, 'Tin trả lời ảnh phải được lưu')
        self.assertEqual(tra_loi.image_reply, anh)


@override_settings(**CAI_DAT_TEST)
class PhongChatTest(TestCoDuLieu):
    def test_mo_phong_chat(self):
        client = Client(raise_request_exception=False)
        response = client.get(reverse('chat_room', args=[1]))
        self.assertEqual(response.status_code, 200)


class GanUserVaoScope:
    """Middleware tí hon cho test: gắn sẵn user vào scope của WebSocket."""

    def __init__(self, app, user):
        self.app = app
        self.user = user

    async def __call__(self, scope, receive, send):
        return await self.app(dict(scope, user=self.user), receive, send)


@override_settings(**CAI_DAT_TEST)
class ChatWebSocketTest(TestCoDuLieu):
    def _ket_noi(self, user, room_id=1):
        app = GanUserVaoScope(URLRouter(websocket_urlpatterns), user)
        return WebsocketCommunicator(app, f'ws/chat/{room_id}')

    def test_ket_noi_duoc_vao_phong_chat(self):
        user, _ = tao_nguoi_dung('an')

        async def kich_ban():
            ket_noi = self._ket_noi(user)
            try:
                thanh_cong, _ = await ket_noi.connect()
                self.assertTrue(thanh_cong, 'WebSocket phải kết nối được vào phòng chat')
            finally:
                with contextlib.suppress(Exception):
                    await ket_noi.disconnect()

        async_to_sync(kich_ban)()

    def test_bao_dang_go_phim_cho_nguoi_kia(self):
        """An gõ phím thì Bình (đang mở cùng phòng) nhận được tín hiệu typing."""
        user_an, _ = tao_nguoi_dung('an')
        user_binh, _ = tao_nguoi_dung('binh')

        async def kich_ban():
            an = self._ket_noi(user_an)
            binh = self._ket_noi(user_binh)
            try:
                await an.connect()
                await binh.connect()
                await an.send_json_to({'type': 'typing', 'is_typing': True})
                su_kien = await binh.receive_json_from()
                self.assertEqual(su_kien['type'], 'user_typing')
                self.assertEqual(su_kien['user_id'], user_an.id)
                self.assertTrue(su_kien['is_typing'])
            finally:
                for ket_noi in (an, binh):
                    with contextlib.suppress(Exception):
                        await ket_noi.disconnect()

        async_to_sync(kich_ban)()

    def test_nhan_thong_bao_tin_nhan_moi(self):
        """Có tin nhắn mới bắn vào phòng thì người đang mở phòng nhận được ngay."""
        user, _ = tao_nguoi_dung('an')

        async def kich_ban():
            ket_noi = self._ket_noi(user, room_id=7)
            try:
                await ket_noi.connect()
                await get_channel_layer().group_send('chat_7', {
                    'type': 'new_message_notification',
                    'message_id': 1,
                    'text': 'chào bạn',
                    'sender_id': user.id,
                })
                su_kien = await ket_noi.receive_json_from()
                self.assertEqual(su_kien['text'], 'chào bạn')
            finally:
                with contextlib.suppress(Exception):
                    await ket_noi.disconnect()

        async_to_sync(kich_ban)()
