"""Test cho app core: trang chủ và health check.

Mỗi test mô tả một hành vi mà người dùng mong đợi.
Test nào fail nghĩa là code thật đang không làm đúng hành vi đó.
"""
from django.test import Client, override_settings
from django.urls import reverse

from apps.test_helpers import TEST_SETTINGS, BaseTestCase, create_user_with_bio


@override_settings(**TEST_SETTINGS)
class HealthCheckTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_health_check_returns_ok(self):
        """Gọi trang health check phải nhận được 200 và {"status": "ok"}."""
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'status': 'ok'})

    def test_health_check_rejects_post(self):
        """Health check chỉ cho GET/HEAD, gửi POST phải bị chặn với mã 405."""
        response = self.client.post(reverse('health'))
        self.assertEqual(response.status_code, 405)


@override_settings(**TEST_SETTINGS)
class IndexViewTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_homepage_lives_at_root(self):
        """Người dùng gõ đường dẫn gốc "/" phải mở được trang chủ."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_guest_sees_landing_page(self):
        """Khách chưa đăng nhập mở trang chủ thì thấy trang giới thiệu (index.html)."""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')

    def test_logged_in_user_sees_image_feed(self):
        """Người đã đăng nhập mở trang chủ thì thấy bảng tin ảnh (images/index.html)."""
        user, bio = create_user_with_bio('an')
        self.client.force_login(user)
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'images/index.html')
