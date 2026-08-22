"""Test cho app core: trang chủ, health check và system check môi trường production."""
from django.conf import settings
from django.test import Client, override_settings
from django.urls import reverse

from apps.core.checks import production_environment_check
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

    def test_login_required_redirects_to_real_login_page(self):
        """LOGIN_URL phải trỏ về /user/authentication/login (trước đây /accounts/login/ -> 404)."""
        response = self.client.get(reverse('friends_list'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')), response.url)
        self.assertEqual(self.client.get(response.url).status_code, 200)


class SettingsTest(BaseTestCase):
    def test_login_url_is_a_named_route(self):
        self.assertEqual(settings.LOGIN_URL, 'login')

    def test_production_env_check_is_silent_outside_production(self):
        self.assertEqual(production_environment_check(None), [])

    @override_settings(REQUIRE_PRODUCTION_ENV=True, DATABASE_URL='', REDIS_URL='',
                       USE_CLOUDINARY=False, ALLOWED_HOSTS=['*'])
    def test_production_env_check_reports_every_missing_piece(self):
        ids = {e.id for e in production_environment_check(None)}
        self.assertEqual(ids, {'locket.E001', 'locket.E002', 'locket.E003', 'locket.E005'})

    @override_settings(REQUIRE_PRODUCTION_ENV=True, DATABASE_URL='postgres://x', REDIS_URL='redis://x',
                       USE_CLOUDINARY=True, ALLOWED_HOSTS=['locket.example.com', '127.0.0.1'])
    def test_production_env_check_passes_when_configured(self):
        self.assertEqual(production_environment_check(None), [])
