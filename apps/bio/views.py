from django.shortcuts import render, redirect
from django.http.response import JsonResponse
from django.contrib.auth.models import User
from .models import Bio
from django.db import transaction
from django.core.files.base import ContentFile
from django.contrib.auth import authenticate, login, logout
from .forms import LoginForm, UserRegistrationForm
from django.contrib.auth.decorators import login_required
from django_ratelimit.decorators import ratelimit
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# Authentication
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

                image = ContentFile(form['image'].read(),name=form['image'].name)
                bio = Bio.objects.create(avatar=image,user=user)

                login(request,user,backend='django.contrib.auth.backends.ModelBackend')

                return redirect('check')
            else:
                if authenticate(request,email=form['email'],password=['password']):
                    login(user_check, backend='django.contrib.auth.backends.ModelBackend')
                    return redirect("check")
        else:
            return redirect('/')

@ratelimit(key='user_or_ip', rate='10/m')
@login_required
def check(request):
    user = User.objects.get(id=request.user.id)
    bio = Bio.objects.get(user=user)
    if user and bio:
        return redirect('/')
    else:
        if request.method == "POST":
            avatar = request.FILE.get('avatar')
            if not avatar:
                return JsonResponse({"error": "Không có dữ liệu ảnh"}, status=400)
        
            image = ContentFile(avatar.read(),name=avatar.name)
        
            bio = Bio.objects.create(avatar=image,user=user)
            #bio.save()
        
            return redirect('/')
    return render(request, 'bio/authentication/check.html')
            
@ratelimit(key='user_or_ip', rate='10/m')
@login_required
def logout(request):
    logout(request.user)
    return redirect('/')

# Friends 
@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def friends_list(request):
    bio = Bio.objects.get(user=request.user)
    friends = bio.friends.all()[::-1]
    pagination = Paginator(friends, 10)
    page = request.GET.get('page')
    try:
        page_obj = pagination.get_page(page)
    except PageNotAnInteger:
        page_obj = pagination.page(1)
    except EmptyPage:
        page_obj = pagination.page(pagination.num_pages)
    
    return render(request, 'bio/friends/list.html', {'chat_lists':page_obj})


@ratelimit(key='user_or_ip', rate='500/m')
@login_required
@transaction.atomic
def unfriend(request, id):
    bio = Bio.objects.get(user=request.user)
    fr = Bio.objects.get(id=id)
    if bio.friends.get(fr) and fr.friends.get(bio):
        bio.friends.delete(fr)
        fr.friends.delete(bio)
        return JsonResponse({'success':'unfriend successfully'}, 200)
    else:
        return JsonResponse({'error':'error'},500)

@ratelimit(key='user_or_ip', rate='500/m')
@login_required
@transaction.atomic
def add_friend(request, from_id):
    bio = Bio.objects.get(user=request.user)
    friend = Bio.objects.get(id=from_id)
    if bio.friends.get(friend) and friend.friends.get(bio):
        return JsonResponse({'error'},500)
    else:
        bio.friends.add(friend)
        friend.friends.add(bio)
        return JsonResponse({'sucess'})

@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def friends_information(request, id):
    bio = Bio.objects.filter(id=id)
    if bio:
        return render(request, 'bio/information.html', {'informations':bio})
    else:
        return JsonResponse({'error'},500)

# Bio
@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def bio(request):
    bio = Bio.objects.filter(user=request.user)
    return render(request, 'bio/information.html', {'informations':bio})

@ratelimit(key='user_or_ip',rate='100/m')
@login_required
def bio_information_change(request):
    bio = Bio.objects.get(user=request.user)
    if bio:
        if request.method == 'POST':
            username = request.POST.get('username')
            email = request.POST.get('email')
            image = request.FILES.get('file')
            password = request.POST.get('password')

            img = ContentFile(image.read(), name=image.name)

            bio.objects.update(username=username,password=password,email=email,avatar=img)

            return JsonResponse({'success'}, 200)
    else:
        return JsonResponse({'error'},500)