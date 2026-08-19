"""Test cho app forgot_password: quên mật khẩu qua mã gửi email.

Tính năng vừa được merge vào. Mỗi test mô tả một hành vi mà người dùng
mong đợi; test nào fail nghĩa là code thật đang không làm đúng hành vi đó.
"""
import importlib
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.test_helpers import CAI_DAT_TEST, TestCoDuLieu

from apps.forgot_password.models import Forgot_password_request


@override_settings(**CAI_DAT_TEST)
class ForgotPasswordModelTest(TestCoDuLieu):
    def test_tao_yeu_cau_quen_mat_khau(self):
        """Một yêu cầu quên mật khẩu gồm: người dùng, mã đã băm, hạn dùng, trạng thái."""
        user = User.objects.create_user('an', 'an@example.com', 'mat-khau-manh-123')
        yeu_cau = Forgot_password_request.objects.create(
            user=user,
            code='ma-da-bam',
            expire=timezone.now() + timedelta(minutes=10),
            status='pending',
        )
        self.assertEqual(yeu_cau.user, user)
        self.assertEqual(yeu_cau.status, 'pending')

    def test_xoa_user_thi_yeu_cau_mat_theo(self):
        user = User.objects.create_user('an', 'an@example.com', 'mat-khau-manh-123')
        Forgot_password_request.objects.create(
            user=user, code='x', expire=timezone.now(), status='pending',
        )
        user.delete()
        self.assertEqual(Forgot_password_request.objects.count(), 0)


class ForgotPasswordCodeTest(TestCoDuLieu):
    def test_code_views_phai_import_duoc(self):
        """File views.py phải import được — hiện đang vỡ vì lời gọi send_mail
        thiếu dấu phẩy giữa các tham số (SyntaxError)."""
        importlib.import_module('apps.forgot_password.views')

    def test_cac_trang_quen_mat_khau_phai_co_url(self):
        """Luồng quên mật khẩu phải bấm vào được: cần các url mà chính code
        đang redirect tới (forgot_password_verify, change_password)."""
        for ten in ['forgot_password_verify', 'change_password']:
            try:
                reverse(ten, args=[1])
            except NoReverseMatch:
                self.fail(f'Chưa khai báo url tên "{ten}" trong urls.py nào cả')
