from django.shortcuts import render
from django.core.mail import send_mail
from django_ratelimit.decorators import ratelimit
import time
from .models import Forgot_password_request
import random
from django.db.transaction import transaction
from django.contrib.auth.hashers import make_password, check_password

# Create your views here.

def load_email_html():
    with open("/templates/authentication/forgot_password/mail.html") as file:
        return file.read()

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

        user = User.objects.get(email=email)
        if user:
            code = code_generator()
            message = load_email_html().format(code=code)

            forgot_request = Forgot_password_request.objects.create(
                user=user,
                code=code_hashing(code),
                expire=time.time() + (10*60),
                status="pending"
            )

            send_mail(
                subject=f"Password Reset for {user.email}"
                from_email=os.getenv('FROM_EMAIL'),
                html_message=message,
                message='Success',
                recipent_list=[user.email]
            )

            return redirect("forgot_password_verify")
    return render(request, "/authentication/forgot_password/create.html")

@ratelimit(key='ip', rate='10/m')
def forgot_password_verify(request,id):
    forgot = Forgot_password_request.objects.get(id=id)
    if forgot and time.time() <= forgot.expire:
        if request.method == 'POST':
            code = request.POST.get('code')

            verify_code = check_password(forgot.code, code)
            nowtime = time.time()

            if verify_code and forgot.status == 'pending' and nowtime <= forgot.expire:
                forgot.status = 'changing'
                forgot.save()
                return redirect("change_password")
            else:
                return JsonResponse({"error":'there are some error'},500)
    else:
        return JsonResponse({"error":'there are some error'},500)
    return render(request, '/authentication/forgot_password/verify.html')

@ratelimit(key='ip', rate='10/m')
@transaction.atomic
def change_password(request,id):
    forgot = Forgot_password_request.objects.get(id=id)
    if forgot and forgot.status == 'changing':
        if request.method == "POST":
            password = request.POST.get("password")

            forgot.user.password = make_password(password)
            forgot.user.save()
        
            forgot.status = 'done'
            forgot.save()

            return redirect('login')
    else:
        return JsonResponse({"error":'there are some error'},500)
    