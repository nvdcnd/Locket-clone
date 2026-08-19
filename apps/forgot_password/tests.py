"""Test cho app forgot_password: quên mật khẩu qua mã gửi email.

Tính năng vừa được merge vào. Mỗi test mô tả một hành vi mà người dùng
mong đợi; test nào fail nghĩa là code thật đang không làm đúng hành vi đó.
"""
import importlib
import re
from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.test_helpers import TEST_SETTINGS, BaseTestCase

from apps.forgot_password.models import Forgot_password_request


@override_settings(**TEST_SETTINGS)
class ForgotPasswordModelTest(BaseTestCase):
    def test_create_reset_request(self):
        """Một yêu cầu quên mật khẩu gồm: người dùng, mã đã băm, hạn dùng, trạng thái."""
        user = User.objects.create_user('an', 'an@example.com', 'mat-khau-manh-123')
        reset_request = Forgot_password_request.objects.create(
            user=user,
            code='ma-da-bam',
            expire=timezone.now() + timedelta(minutes=10),
            status='pending',
        )
        self.assertEqual(reset_request.user, user)
        self.assertEqual(reset_request.status, 'pending')

    def test_deleting_user_deletes_request(self):
        user = User.objects.create_user('an', 'an@example.com', 'mat-khau-manh-123')
        Forgot_password_request.objects.create(
            user=user, code='x', expire=timezone.now(), status='pending',
        )
        user.delete()
        self.assertEqual(Forgot_password_request.objects.count(), 0)


class ForgotPasswordCodeTest(BaseTestCase):
    def test_views_module_imports(self):
        """File views.py phải import được sạch sẽ, không lỗi cú pháp hay import."""
        importlib.import_module('apps.forgot_password.views')

    def test_reset_flow_urls_exist(self):
        """Luồng quên mật khẩu phải bấm vào được: cần các url mà chính code
        đang redirect tới (forgot_password_verify, change_password)."""
        for name in ['forgot_password_verify', 'change_password']:
            try:
                reverse(name, args=[1])
            except NoReverseMatch:
                self.fail(f'Chưa khai báo url tên "{name}" trong urls.py nào cả')


@override_settings(**TEST_SETTINGS)
class ForgotPasswordFlowTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user = User.objects.create_user('an', 'an@example.com', 'mat-khau-cu-123')

    def _request_reset(self):
        """Gửi yêu cầu quên mật khẩu rồi lấy mã xác nhận từ email gửi ra."""
        response = self.client.post(reverse('forgot_password'), {'email': 'an@example.com'})
        code = re.search(r'\d+', mail.outbox[0].body).group()
        return response, code

    def test_request_sends_email_with_code(self):
        """Nhập email thì nhận được mail chứa mã và được đưa sang trang nhập mã."""
        response, code = self._request_reset()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('an@example.com', mail.outbox[0].to)
        reset_request = Forgot_password_request.objects.get(user=self.user)
        self.assertEqual(reset_request.status, 'pending')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('forgot_password_verify', args=[reset_request.id]))

    def test_wrong_code_is_rejected(self):
        """Nhập sai mã xác nhận thì bị từ chối, trạng thái vẫn là pending."""
        self._request_reset()
        reset_request = Forgot_password_request.objects.get(user=self.user)
        response = self.client.post(
            reverse('forgot_password_verify', args=[reset_request.id]),
            {'code': 'sai-code-roi'},
        )
        self.assertGreaterEqual(response.status_code, 400)
        reset_request.refresh_from_db()
        self.assertEqual(reset_request.status, 'pending')

    def test_full_flow_changes_password(self):
        """Đi hết luồng: nhập email → nhập đúng mã → đặt mật khẩu mới."""
        _, code = self._request_reset()
        reset_request = Forgot_password_request.objects.get(user=self.user)

        response = self.client.post(
            reverse('forgot_password_verify', args=[reset_request.id]),
            {'code': code},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            reverse('change_password', args=[reset_request.id]),
            {'password': 'mat-khau-moi-456'},
        )
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        self.assertTrue(check_password('mat-khau-moi-456', self.user.password),
                        'Mật khẩu mới phải dùng được sau khi đổi')
        reset_request.refresh_from_db()
        self.assertEqual(reset_request.status, 'done')
