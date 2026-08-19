from django.shortcuts import render, redirect
from django.http.response import JsonResponse
from django.contrib.auth.models import User
from .models import Bio
from django.db import transaction
from django.core.files.base import ContentFile
from django.contrib.auth import login, logout
from .forms import LoginForm, UserRegistrationForm
from django.contrib.auth.decorators import login_required
from django_ratelimit.decorators import ratelimit
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.hashers import check_password

# Authentication
@ratelimit(key='ip', rate='10/m')
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = User.objects.filter(email=form.cleaned_data['email']).first()
            if user and check_password(form.cleaned_data['password'], user.password):
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('check')
        return redirect('/')
    return render(request, 'bio/authentication/login.html', {'form': LoginForm()})

@ratelimit(key='ip', rate='10/m')
def signup(request):
    if request.method == 'POST':
        # Form có ảnh nên phải đưa cả request.FILES vào
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            email_taken = User.objects.filter(email=form.cleaned_data['email']).exists()
            if not email_taken:
                user = User.objects.create_user(
                    form.cleaned_data['username'],
                    form.cleaned_data['email'],
                    form.cleaned_data['password'],
                )

                image = ContentFile(form.cleaned_data['image'].read(), name=form.cleaned_data['image'].name)
                Bio.objects.create(avatar=image, user=user)

                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

                return redirect('check')
        return redirect('/')
    return render(request, 'bio/authentication/signup.html', {'form': UserRegistrationForm()})

@ratelimit(key='user_or_ip', rate='10/m')
@login_required
def check(request):
    if not Bio.objects.filter(user=request.user).exists():
        Bio.objects.create(user=request.user)
    return redirect('/')

@ratelimit(key='user_or_ip', rate='10/m')
@login_required
def log_out(request):
    logout(request)
    return redirect('/')

# Friends
@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def friends_list(request):
    bio = Bio.objects.filter(user=request.user).first()
    if not bio:
        return redirect('check')
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
    bio = Bio.objects.filter(user=request.user).first()
    fr = Bio.objects.filter(id=id).first()
    if bio and fr and bio.friends.filter(id=fr.id).exists():
        bio.friends.remove(fr)
        fr.friends.remove(bio)
        return JsonResponse({'success': 'unfriend successfully'}, status=200)
    else:
        return JsonResponse({'error': 'you are not friends'}, status=400)

@ratelimit(key='user_or_ip', rate='500/m')
@login_required
@transaction.atomic
def add_friend(request, id):
    bio = Bio.objects.filter(user=request.user).first()
    friend = Bio.objects.filter(id=id).first()
    if not bio or not friend or bio.id == friend.id:
        return JsonResponse({'error': 'invalid friend'}, status=400)
    if bio.friends.filter(id=friend.id).exists():
        return JsonResponse({'error': 'already friends'}, status=400)
    else:
        bio.friends.add(friend)
        friend.friends.add(bio)
        return JsonResponse({'success': 'friend added'}, status=200)

@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def friends_information(request, id):
    bio = Bio.objects.filter(id=id)
    if bio:
        return render(request, 'bio/information.html', {'informations':bio})
    else:
        return JsonResponse({'error': 'friend not found'}, status=404)

# Bio
@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def bio(request):
    bio = Bio.objects.filter(user=request.user)
    return render(request, 'bio/information.html', {'informations':bio})

@ratelimit(key='user_or_ip',rate='100/m')
@login_required
@transaction.atomic
def bio_information_change(request):
    bio = Bio.objects.filter(user=request.user).first()
    if not bio:
        return JsonResponse({'error': 'bio not found'}, status=404)
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        image = request.FILES.get('file')
        password = request.POST.get('password')

        user = bio.user
        if username:
            user.username = username
        if email:
            user.email = email
        if password:
            user.set_password(password)
        user.save()

        if image:
            bio.avatar = ContentFile(image.read(), name=image.name)
            bio.save()

        return JsonResponse({'success': 'information updated'}, status=200)
    return JsonResponse({'error': 'method not allowed'}, status=405)
