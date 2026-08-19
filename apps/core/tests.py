"""Test cho app core: trang chủ và health check.

Mỗi test mô tả một hành vi mà người dùng mong đợi.
Test nào fail nghĩa là code thật đang không làm đúng hành vi đó.
"""
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.test_helpers import THU_MUC_ANH_TAM, TestCoDuLieu, tao_nguoi_dung

CAI_DAT_TEST = dict(RATELIMIT_ENABLE=False, MEDIA_ROOT=THU_MUC_ANH_TAM)


@override_settings(**CAI_DAT_TEST)
class HealthCheckTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_health_check_bao_ok(self):
        """Gọi trang health check phải nhận được 200 và {"status": "ok"}."""
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'status': 'ok'})

    def test_health_check_chan_phuong_thuc_khac(self):
        """Health check chỉ cho GET/HEAD, gửi POST phải bị chặn với mã 405."""
        response = self.client.post(reverse('health'))
        self.assertEqual(response.status_code, 405)


@override_settings(**CAI_DAT_TEST)
class TrangChuTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_trang_chu_mo_duoc_o_duong_dan_goc(self):
        """Người dùng gõ đường dẫn gốc "/" phải mở được trang chủ."""
        response = self.client.get('/')
        self.assertEqual(
            response.status_code, 200,
            'Trang chủ phải nằm ở "/" (hiện path("/") trong config/urls.py làm lệch đường dẫn)',
        )

    def test_khach_thay_trang_gioi_thieu(self):
        """Khách chưa đăng nhập mở trang chủ thì thấy trang giới thiệu."""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)

    def test_nguoi_dung_thay_bang_tin_anh(self):
        """Người đã đăng nhập mở trang chủ thì thấy bảng tin ảnh của mình và bạn bè."""
        user, bio = tao_nguoi_dung('an')
        self.client.force_login(user)
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
