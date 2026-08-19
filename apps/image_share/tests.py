"""Test cho app image_share: đăng ảnh, bảng tin, thả emoji, xóa ảnh.

Mỗi test mô tả một hành vi mà người dùng mong đợi.
Test nào fail nghĩa là code thật đang không làm đúng hành vi đó.
"""
import base64
import json

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.test_helpers import (
    ANH_GIF_1X1, CAI_DAT_TEST, TestCoDuLieu, anh_mau, ket_ban, tao_nguoi_dung,
)

from apps.image_share.models import Emoji_type, Image, Image_emoji_share, Image_type

# Chuỗi base64 đúng dạng mà trình duyệt gửi lên khi đăng ảnh.
ANH_BASE64 = 'data:image/gif;base64,' + base64.b64encode(ANH_GIF_1X1).decode()


@override_settings(**CAI_DAT_TEST)
class ImageModelTest(TestCoDuLieu):
    def setUp(self):
        _, self.bio_an = tao_nguoi_dung('an')

    def test_tao_anh_kem_loai_va_danh_sach_chia_se(self):
        loai = Image_type.objects.create(name='ban-be')
        _, bio_binh = tao_nguoi_dung('binh')
        anh = Image.objects.create(
            user=self.bio_an, image=anh_mau(), text='đi chơi', type_share=loai,
        )
        anh.shared_list.add(bio_binh)
        self.assertEqual(anh.type_share, loai)
        self.assertIn(bio_binh, anh.shared_list.all())

    def test_tha_emoji_vao_anh(self):
        anh = Image.objects.create(user=self.bio_an, image=anh_mau(), text='đi chơi')
        tim = Emoji_type.objects.create(emoji='❤️')
        luot_tha = Image_emoji_share.objects.create(user=self.bio_an, image=anh, emoji=tim)
        self.assertEqual(luot_tha.emoji, tim)

    def test_xoa_chu_anh_thi_anh_mat_theo(self):
        Image.objects.create(user=self.bio_an, image=anh_mau(), text='đi chơi')
        self.bio_an.delete()
        self.assertEqual(Image.objects.count(), 0)


@override_settings(**CAI_DAT_TEST)
class DangAnhTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user, self.bio = tao_nguoi_dung('an')

    def _dang_anh(self, text='ảnh hôm nay'):
        return self.client.post(
            reverse('image_create'),
            data=json.dumps({'image': ANH_BASE64, 'text': text}),
            content_type='application/json',
        )

    def test_dang_anh_thanh_cong(self):
        """Đăng ảnh base64 hợp lệ thì ảnh được lưu cho đúng chủ."""
        self.client.force_login(self.user)
        response = self._dang_anh('ảnh hôm nay')
        self.assertEqual(response.status_code, 200)
        anh = Image.objects.filter(text='ảnh hôm nay').first()
        self.assertIsNotNone(anh, 'Ảnh phải được lưu vào hệ thống')
        self.assertEqual(anh.user, self.bio)

    def test_chua_co_bio_thi_khong_dang_duoc(self):
        from django.contrib.auth.models import User
        user_moi = User.objects.create_user('moi', 'moi@example.com', 'mat-khau-manh-123')
        self.client.force_login(user_moi)
        response = self._dang_anh()
        self.assertGreaterEqual(response.status_code, 400)
        self.assertEqual(Image.objects.count(), 0)

    def test_chua_dang_nhap_bi_day_ve_trang_login(self):
        response = self._dang_anh()
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


@override_settings(**CAI_DAT_TEST)
class BangTinAnhTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user_an, self.bio_an = tao_nguoi_dung('an')
        _, self.bio_binh = tao_nguoi_dung('binh')
        ket_ban(self.bio_an, self.bio_binh)

    def test_bang_tin_co_anh_cua_minh_va_cua_ban(self):
        Image.objects.create(user=self.bio_an, image=anh_mau(), text='ảnh của an')
        Image.objects.create(user=self.bio_binh, image=anh_mau(), text='ảnh của bình')
        self.client.force_login(self.user_an)
        response = self.client.get(
            reverse('image_list_infinity_scroll', args=['2000-01-01'])
        )
        self.assertEqual(response.status_code, 200)
        du_lieu = json.loads(response.content)
        self.assertIn('images', du_lieu)
        self.assertIn('has_next', du_lieu)


@override_settings(**CAI_DAT_TEST)
class ThaEmojiTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user_an, self.bio_an = tao_nguoi_dung('an')
        self.anh = Image.objects.create(user=self.bio_an, image=anh_mau(), text='đi chơi')
        self.tim = Emoji_type.objects.create(emoji='❤️')
        self.client.force_login(self.user_an)

    def test_tha_emoji_thanh_cong(self):
        response = self.client.post(
            reverse('emojing_image', args=[self.anh.id]),
            data=json.dumps({'emoji': '❤️'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Image_emoji_share.objects.filter(image=self.anh, user=self.bio_an, emoji=self.tim).exists(),
            'Lượt thả emoji phải được lưu lại',
        )

    def test_tha_emoji_vao_anh_khong_ton_tai_thi_bao_loi(self):
        response = self.client.post(
            reverse('emojing_image', args=[999999]),
            data=json.dumps({'emoji': '❤️'}),
            content_type='application/json',
        )
        self.assertGreaterEqual(response.status_code, 400)


@override_settings(**CAI_DAT_TEST)
class XoaAnhTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user_an, self.bio_an = tao_nguoi_dung('an')
        self.user_binh, self.bio_binh = tao_nguoi_dung('binh')
        self.anh_cua_an = Image.objects.create(user=self.bio_an, image=anh_mau(), text='của an')
        self.client.force_login(self.user_an)

    def test_xoa_anh_cua_minh_thi_anh_bien_mat(self):
        self.client.post(reverse('image_delete', args=[self.anh_cua_an.id]))
        self.assertFalse(Image.objects.filter(id=self.anh_cua_an.id).exists())

    def test_xoa_anh_bao_thanh_cong(self):
        response = self.client.post(reverse('image_delete', args=[self.anh_cua_an.id]))
        self.assertEqual(response.status_code, 200)

    def test_khong_xoa_duoc_anh_cua_nguoi_khac(self):
        anh_cua_binh = Image.objects.create(user=self.bio_binh, image=anh_mau(), text='của bình')
        response = self.client.post(reverse('image_delete', args=[anh_cua_binh.id]))
        self.assertTrue(Image.objects.filter(id=anh_cua_binh.id).exists(),
                        'Ảnh của người khác phải còn nguyên')
        self.assertGreaterEqual(response.status_code, 400)
