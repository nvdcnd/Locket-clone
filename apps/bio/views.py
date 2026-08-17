from django.shortcuts import render, redirect
from django.http.response import JsonResponse
from django.contrib.auth.models import User
from .models import Bio
from django.core.files.base import Contentfile
from django.contrib.auth import authenticate, login, logout
from .forms import LoginForm, UserRegistrationForm
from django.contrib.auth.decorators import login_required
from django_ratelimit.decorators import ratelimit

# Create your views here.
@ratelimit(key='ip', rate='10/m')
def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            check = authenticate(request, email=form['email'], password=form['password'])
            if check:
                login(request, check, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('check')
            else:
                return redirect('/')

@ratelimit(key='ip', rate='10/m')
def signup(request):
    if request.medthod == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user_check = User.objects.get(email=form['email'])
            if not user_check:
                user = User.objects.create_user(form['username'],form['email'],form['password'])
                user.save()
                login(request,user,backend='django.contrib.auth.backends.ModelBackend')
                return redirect('check')
            else:
                if authenticate(request,email=form['email'],password=['password']):
                    login(user_check, backend='django.contrib.auth.backends.ModelBackend')
                    return redirect("check")
        else:
            return redirect('/')

@ratelimit(key='ip', rate='10/m')
@login_required
def check(request):
    user = User.objects.get(id=request.user.id)
    bio = Bio.objects.get(user=user)
    if user and bio:
        if request.method == "POST":
            avatar = request.FILE.get('avatar')
            if not avatar:
                return JsonResponse({"error": "Không có dữ liệu ảnh"}, status=400)

            image = Contentfile(avatar.read(),name=avatar.name)

            bio = Bio.objects.create(avatar=image,user=user)
            bio.save()

            return redirect('/')
    else:
        return redirect('/')
            
@ratelimit(key='ip', rate='10/m')
@login_required
def logout(request):
    logout(request.user)
    return redirect('/')

                