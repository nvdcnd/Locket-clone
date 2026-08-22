import logging
import secrets
import smtplib
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django_ratelimit.decorators import ratelimit

from .models import Forgot_password_request

logger = logging.getLogger(__name__)

CODE_TTL = timedelta(minutes=10)
STATUS_PENDING = 'pending'
STATUS_CHANGING = 'changing'
STATUS_DONE = 'done'
STATUS_CANCELLED = 'cancelled'


def code_generator():
    """Mã 6 chữ số, luôn đủ 6 ký tự, sinh bằng secrets (CSPRNG) chứ không phải random."""
    return f'{secrets.randbelow(10 ** 6):06d}'


def code_hashing(code):
    return make_password(code)


def _is_usable(forgot, expected_status):
    return bool(forgot and forgot.status == expected_status and timezone.now() <= forgot.expire)


def _invalid(request, message):
    """GET -> hiện lại trang nhập email kèm lỗi; POST (fetch từ JS) -> JSON."""
    if request.method == 'POST':
        return JsonResponse({'error': message}, status=400)
    return render(request, 'authentication/forgot_password/create.html', {'error': message}, status=400)


@ratelimit(key='ip', rate='10/m')
def forgot_password(request):
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        user = User.objects.filter(email__iexact=email).order_by('id').first() if email else None
        if not user:
            return render(request, 'authentication/forgot_password/create.html',
                          {'error': 'Không tìm thấy tài khoản với email này.'}, status=404)

        code = code_generator()
        with transaction.atomic():
            # Mỗi lần yêu cầu mới thì các mã cũ chưa dùng của user này hết hiệu lực.
            Forgot_password_request.objects.filter(
                user=user, status__in=[STATUS_PENDING, STATUS_CHANGING],
            ).update(status=STATUS_CANCELLED)
            forgot_request = Forgot_password_request.objects.create(
                user=user,
                code=code_hashing(code),
                expire=timezone.now() + CODE_TTL,
                status=STATUS_PENDING,
            )

        try:
            send_mail(
                subject=f'Password Reset for {user.email}',
                from_email=None,  # -> settings.DEFAULT_FROM_EMAIL
                html_message=render_to_string('authentication/forgot_password/mail.html', {'code': code}),
                message=f'Mã xác nhận của bạn là: {code}',
                recipient_list=[user.email],
            )
        except (smtplib.SMTPException, OSError):
            logger.exception('Không gửi được mail quên mật khẩu tới %s', user.email)
            return render(request, 'authentication/forgot_password/create.html',
                          {'error': 'Không gửi được email lúc này, vui lòng thử lại sau.'}, status=503)

        return redirect('forgot_password_verify', id=forgot_request.id)
    return render(request, 'authentication/forgot_password/create.html')


@ratelimit(key='ip', rate='10/m')
def forgot_password_verify(request, id):
    forgot = Forgot_password_request.objects.filter(id=id).first()
    if not _is_usable(forgot, STATUS_PENDING):
        return _invalid(request, 'Yêu cầu không tồn tại hoặc đã hết hạn, hãy gửi lại mã.')

    if request.method == 'POST':
        code = (request.POST.get('code') or '').strip()
        if code and check_password(code, forgot.code):
            forgot.status = STATUS_CHANGING
            forgot.save(update_fields=['status'])
            return redirect('change_password', id=forgot.id)
        return JsonResponse({'error': 'mã xác nhận không đúng'}, status=400)
    return render(request, 'authentication/forgot_password/verify.html')


@ratelimit(key='ip', rate='10/m')
def change_password(request, id):
    forgot = Forgot_password_request.objects.filter(id=id).select_related('user').first()
    if not _is_usable(forgot, STATUS_CHANGING):
        return _invalid(request, 'Yêu cầu không hợp lệ hoặc đã hết hạn, hãy gửi lại mã.')

    if request.method == 'POST':
        password = request.POST.get('password') or ''
        try:
            validate_password(password, forgot.user)
        except ValidationError as exc:
            return JsonResponse({'error': ' '.join(exc.messages)}, status=400)

        with transaction.atomic():
            forgot.user.set_password(password)
            forgot.user.save(update_fields=['password'])
            forgot.status = STATUS_DONE
            forgot.save(update_fields=['status'])
        return redirect('login')
    return render(request, 'authentication/forgot_password/change.html')
