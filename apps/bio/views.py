from django import forms
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .forms import LoginForm, UserRegistrationForm
from .models import Bio

FRIENDS_PAGE_SIZE = 10


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
@ratelimit(key='ip', rate='10/m')
def login_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    form = LoginForm(request.POST or None)
    error = None
    if request.method == 'POST':
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.filter(email__iexact=email).order_by('id').first()
            # authenticate() đi qua backend: kiểm tra is_active, và vẫn chạy băm giả khi
            # không tìm thấy user để thời gian phản hồi không tiết lộ email có tồn tại.
            auth_user = authenticate(
                request,
                username=user.username if user else email,
                password=form.cleaned_data['password'],
            )
            if auth_user is not None:
                login(request, auth_user)
                return redirect('check')
            error = 'Email hoặc mật khẩu không đúng.'
        else:
            error = 'Vui lòng nhập email hợp lệ và mật khẩu.'
    return render(request, 'bio/authentication/login.html', {'form': form, 'error': error})


@ratelimit(key='ip', rate='10/m')
def signup(request):
    if request.user.is_authenticated:
        return redirect('/')

    # Form có ảnh nên phải đưa cả request.FILES vào
    form = UserRegistrationForm(request.POST or None, request.FILES or None)
    errors = []
    if request.method == 'POST':
        if form.is_valid():
            username = form.cleaned_data['username'].strip()
            email = form.cleaned_data['email'].strip()
            password = form.cleaned_data['password']

            if User.objects.filter(username__iexact=username).exists():
                errors.append('Tên đăng nhập đã được sử dụng.')
            if User.objects.filter(email__iexact=email).exists():
                errors.append('Email đã được sử dụng.')
            try:
                validate_password(password, User(username=username, email=email))
            except ValidationError as exc:
                errors.extend(exc.messages)

            if not errors:
                try:
                    with transaction.atomic():
                        user = User.objects.create_user(username, email, password)
                        Bio.objects.create(user=user, avatar=form.cleaned_data['image'])
                except IntegrityError:
                    # Hai người đăng ký cùng username gần như cùng lúc.
                    errors.append('Tên đăng nhập đã được sử dụng.')
                else:
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    return redirect('check')
        else:
            errors = [f'{form.fields[name].label}: {err}' for name, errs in form.errors.items() for err in errs]

    return render(request, 'bio/authentication/signup.html', {'form': form, 'errors': errors})


@ratelimit(key='user_or_ip', rate='10/m')
@login_required
def check(request):
    if not Bio.objects.filter(user=request.user).exists():
        Bio.objects.create(user=request.user)
    return redirect('/')


@ratelimit(key='user_or_ip', rate='10/m')
@login_required
@require_POST
def log_out(request):
    logout(request)
    return redirect('/')


# ---------------------------------------------------------------------------
# Friends
# ---------------------------------------------------------------------------
@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def friends_list(request):
    bio = Bio.objects.filter(user=request.user).first()
    if not bio:
        return redirect('check')
    friends = bio.friends.select_related('user').order_by('user__username')
    page_obj = Paginator(friends, FRIENDS_PAGE_SIZE).get_page(request.GET.get('page'))
    return render(request, 'bio/friends/list.html', {'chat_lists': page_obj, 'mybio': bio})


@ratelimit(key='user_or_ip', rate='500/m')
@login_required
@require_POST
@transaction.atomic
def unfriend(request, id):
    bio = Bio.objects.filter(user=request.user).first()
    fr = Bio.objects.filter(id=id).first()
    if bio and fr and bio.friends.filter(id=fr.id).exists():
        bio.friends.remove(fr)  # ManyToManyField('self') đối xứng: tự gỡ cả chiều ngược lại
        return JsonResponse({'success': 'unfriend successfully'}, status=200)
    return JsonResponse({'error': 'you are not friends'}, status=400)


@ratelimit(key='user_or_ip', rate='500/m')
@login_required
@require_POST
@transaction.atomic
def add_friend(request, id):
    bio = Bio.objects.filter(user=request.user).first()
    friend = Bio.objects.filter(id=id).first()
    if not bio or not friend or bio.id == friend.id:
        return JsonResponse({'error': 'invalid friend'}, status=400)
    if bio.friends.filter(id=friend.id).exists():
        return JsonResponse({'error': 'already friends'}, status=400)
    bio.friends.add(friend)  # đối xứng: friend.friends cũng có bio
    return JsonResponse({'success': 'friend added'}, status=200)


@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def friends_information(request, id):
    informations = Bio.objects.filter(id=id).select_related('user')
    info = informations.first()
    if not info:
        return JsonResponse({'error': 'friend not found'}, status=404)
    is_friend = info.friends.filter(user=request.user).exists()
    return render(request, 'bio/information.html', {'informations': informations, 'is_friend': is_friend})


# ---------------------------------------------------------------------------
# Bio
# ---------------------------------------------------------------------------
@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def bio(request):
    informations = Bio.objects.filter(user=request.user).select_related('user')
    if not informations.exists():
        return redirect('check')
    return render(request, 'bio/information.html', {'informations': informations, 'is_friend': False})


@ratelimit(key='user_or_ip', rate='100/m')
@login_required
@require_POST
@transaction.atomic
def bio_information_change(request):
    bio = Bio.objects.filter(user=request.user).select_related('user').first()
    if not bio:
        return JsonResponse({'error': 'bio not found'}, status=404)

    username = (request.POST.get('username') or '').strip()
    email = (request.POST.get('email') or '').strip()
    password = request.POST.get('password') or ''
    image = request.FILES.get('file')

    user = bio.user
    errors = []

    if username and username != user.username:
        try:
            UnicodeUsernameValidator()(username)
            if len(username) > 150:
                raise ValidationError('Tên đăng nhập tối đa 150 ký tự.')
        except ValidationError as exc:
            errors.extend(exc.messages)
        else:
            if User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
                errors.append('Tên đăng nhập đã được sử dụng.')
            user.username = username

    if email and email != user.email:
        try:
            validate_email(email)
        except ValidationError as exc:
            errors.extend(exc.messages)
        else:
            if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                errors.append('Email đã được sử dụng.')
            user.email = email

    if password:
        try:
            validate_password(password, user)
        except ValidationError as exc:
            errors.extend(exc.messages)
        else:
            user.set_password(password)

    if image is not None:
        try:
            image = forms.ImageField().clean(image)  # kiểm tra đúng là file ảnh (Pillow)
        except ValidationError as exc:
            errors.extend(exc.messages)

    if errors:
        return JsonResponse({'error': errors[0], 'errors': errors}, status=400)

    user.save()
    if image is not None:
        bio.avatar = image
        bio.save(update_fields=['avatar'])
    if password:
        # Đổi mật khẩu làm session hash đổi -> không gọi hàm này thì user bị đăng xuất ngay.
        update_session_auth_hash(request, user)

    return JsonResponse({'success': 'information updated'}, status=200)
