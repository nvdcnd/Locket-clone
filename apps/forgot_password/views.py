from datetime import timedelta

from django.shortcuts import render, redirect
from django.http.response import JsonResponse
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
import os
from .models import Forgot_password_request
import random
from django.db import transaction
from django.contrib.auth.hashers import make_password, check_password

# Create your views here.

def code_generator():
    code = random.randint(0,100000)
    code = str(code)
    return code

def code_hashing(code):
    return make_password(code)

@ratelimit(key='ip', rate='10/m')
def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email')

        user = User.objects.filter(email=email).first()
        if user:
            code = code_generator()

            forgot_request = Forgot_password_request.objects.create(
                user=user,
                code=code_hashing(code),
                expire=timezone.now() + timedelta(minutes=10),
                status="pending"
            )

            send_mail(
                subject=f"Password Reset for {user.email}",
                from_email=os.getenv('FROM_EMAIL'),
                html_message=render_to_string('authentication/forgot_password/mail.html', {'code': code}),
                message=f'Mã xác nhận của bạn là: {code}',
                recipient_list=[user.email]
            )

            return redirect("forgot_password_verify", id=forgot_request.id)
    return render(request, "authentication/forgot_password/create.html")

@ratelimit(key='ip', rate='10/m')
def forgot_password_verify(request,id):
    forgot = Forgot_password_request.objects.filter(id=id).first()
    if forgot and timezone.now() <= forgot.expire:
        if request.method == 'POST':
            code = request.POST.get('code')

            if check_password(code, forgot.code) and forgot.status == 'pending':
                forgot.status = 'changing'
                forgot.save()
                return redirect("change_password", id=forgot.id)
            else:
                return JsonResponse({"error": 'mã xác nhận không đúng'}, status=400)
        return render(request, 'authentication/forgot_password/verify.html')
    return JsonResponse({"error": 'yêu cầu không tồn tại hoặc đã hết hạn'}, status=400)

@ratelimit(key='ip', rate='10/m')
@transaction.atomic
def change_password(request,id):
    forgot = Forgot_password_request.objects.filter(id=id).first()
    if forgot and forgot.status == 'changing':
        if request.method == "POST":
            password = request.POST.get("password")

            forgot.user.password = make_password(password)
            forgot.user.save()

            forgot.status = 'done'
            forgot.save()

            return redirect('login')
        return render(request, 'authentication/forgot_password/change.html')
    return JsonResponse({"error": 'yêu cầu không hợp lệ'}, status=400)
