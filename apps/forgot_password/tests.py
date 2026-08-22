"""Test cho app forgot_password: quên mật khẩu qua mã gửi email.

Mỗi test mô tả một hành vi mà người dùng mong đợi;
test nào fail nghĩa là code thật đang không làm đúng hành vi đó.
"""
import importlib
import re
import uuid
from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.test_helpers import TEST_SETTINGS, BaseTestCase

from apps.forgot_password.models import Forgot_password_request
from apps.forgot_password.views import code_generator


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

    def test_code_is_always_six_digits(self):
        """Mã OTP phải đủ 6 chữ số (trước đây random.randint(0,100000) có thể ra '7')."""
        for _ in range(200):
            self.assertRegex(code_generator(), r'^\d{6}$')

    def test_reset_flow_urls_exist(self):
        """Các url mà code redirect tới (forgot_password_verify, change_password) phải có, nhận UUID."""
        for name in ['forgot_password_verify', 'change_password']:
            try:
                reverse(name, args=[uuid.uuid4()])
            except NoReverseMatch:
                self.fail(f'Chưa khai báo url tên "{name}" nhận UUID')


@override_settings(**TEST_SETTINGS)
class ForgotPasswordFlowTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user = User.objects.create_user('an', 'an@example.com', 'mat-khau-cu-123')

    def _request_reset(self, email='an@example.com'):
        """Gửi yêu cầu quên mật khẩu rồi lấy mã xác nhận từ email gửi ra."""
        response = self.client.post(reverse('forgot_password'), {'email': email})
        code = re.search(r'\d{6}', mail.outbox[-1].body).group()
        return response, code

    def test_open_forgot_page(self):
        response = self.client.get(reverse('forgot_password'))
        self.assertEqual(response.status_code, 200)

    def test_request_sends_email_with_code(self):
        """Nhập email thì nhận được mail chứa mã và được đưa sang trang nhập mã."""
        response, code = self._request_reset()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('an@example.com', mail.outbox[0].to)
        self.assertRegex(code, r'^\d{6}$')
        reset_request = Forgot_password_request.objects.get(user=self.user)
        self.assertEqual(reset_request.status, 'pending')
        self.assertNotEqual(reset_request.code, code, 'Mã phải được băm, không lưu thô')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('forgot_password_verify', args=[reset_request.id]))

    def test_unknown_email_sends_nothing(self):
        response = self.client.post(reverse('forgot_password'), {'email': 'khong-co@example.com'})
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Không tìm thấy', status_code=404)

    def test_new_request_cancels_old_pending_one(self):
        """Xin mã lần 2 thì mã lần 1 hết hiệu lực."""
        _, old_code = self._request_reset()
        old_request = Forgot_password_request.objects.get(user=self.user)
        self._request_reset()
        old_request.refresh_from_db()
        self.assertEqual(old_request.status, 'cancelled')
        response = self.client.post(reverse('forgot_password_verify', args=[old_request.id]), {'code': old_code})
        self.assertEqual(response.status_code, 400)

    def test_wrong_code_is_rejected(self):
        """Nhập sai mã xác nhận thì bị từ chối, trạng thái vẫn là pending."""
        self._request_reset()
        reset_request = Forgot_password_request.objects.get(user=self.user)
        response = self.client.post(
            reverse('forgot_password_verify', args=[reset_request.id]),
            {'code': 'sai-code-roi'},
        )
        self.assertEqual(response.status_code, 400)
        reset_request.refresh_from_db()
        self.assertEqual(reset_request.status, 'pending')

    def test_expired_code_is_rejected(self):
        _, code = self._request_reset()
        reset_request = Forgot_password_request.objects.get(user=self.user)
        reset_request.expire = timezone.now() - timedelta(seconds=1)
        reset_request.save()
        response = self.client.post(reverse('forgot_password_verify', args=[reset_request.id]), {'code': code})
        self.assertEqual(response.status_code, 400)
        reset_request.refresh_from_db()
        self.assertEqual(reset_request.status, 'pending')

    def test_change_page_requires_verified_code(self):
        """Chưa nhập đúng mã thì không vào được bước đổi mật khẩu (kể cả biết id)."""
        self._request_reset()
        reset_request = Forgot_password_request.objects.get(user=self.user)
        response = self.client.post(
            reverse('change_password', args=[reset_request.id]), {'password': 'mat-khau-moi-456'},
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(check_password('mat-khau-cu-123', self.user.password))

    def test_change_is_rejected_after_expiry(self):
        """Đã verify nhưng để quá hạn mới đổi mật khẩu thì bị từ chối (trước đây không kiểm tra)."""
        _, code = self._request_reset()
        reset_request = Forgot_password_request.objects.get(user=self.user)
        self.client.post(reverse('forgot_password_verify', args=[reset_request.id]), {'code': code})
        reset_request.refresh_from_db()
        reset_request.expire = timezone.now() - timedelta(seconds=1)
        reset_request.save()
        response = self.client.post(
            reverse('change_password', args=[reset_request.id]), {'password': 'mat-khau-moi-456'},
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(check_password('mat-khau-cu-123', self.user.password))

    def test_weak_new_password_is_rejected(self):
        _, code = self._request_reset()
        reset_request = Forgot_password_request.objects.get(user=self.user)
        self.client.post(reverse('forgot_password_verify', args=[reset_request.id]), {'code': code})
        response = self.client.post(reverse('change_password', args=[reset_request.id]), {'password': '123'})
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(check_password('mat-khau-cu-123', self.user.password))

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
        self.assertEqual(response.url, reverse('login'))

        self.user.refresh_from_db()
        self.assertTrue(check_password('mat-khau-moi-456', self.user.password),
                        'Mật khẩu mới phải dùng được sau khi đổi')
        reset_request.refresh_from_db()
        self.assertEqual(reset_request.status, 'done')

        # Mã đã dùng rồi thì không dùng lại được
        response = self.client.post(
            reverse('change_password', args=[reset_request.id]), {'password': 'mat-khau-khac-789'},
        )
        self.assertEqual(response.status_code, 400)
