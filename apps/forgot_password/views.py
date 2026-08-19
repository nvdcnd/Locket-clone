from django.shortcuts import render
from django.core.mail import send_mail
from django_ratelimit.decorators import ratelimit
import time
from .models import Forgot_password_request
import random
from django.contrib.auth.hashers import make_password

# Create your views here.

def load_email_html():
    with open("/templates/bio/forgot_password/mail.html") as file:
        return file.read()

def code_generator():
    code = random.randint(0,100000)
    

@ratelimit(key='ip', rate='10/m')
def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email')

        user = User.objects.get(email=email)
        if user:
            forgot_request = Forgot_password_request.objects.create(
                user=user,
                code=
            )