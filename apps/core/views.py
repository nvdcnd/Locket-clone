from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from apps.bio.models import Bio
from apps.image_share.models import Image

FEED_PAGE_SIZE = 10


@require_http_methods(['GET', 'HEAD'])
def health_check(request):
    return JsonResponse({'status': 'ok'}, status=200)


@ratelimit(key='user_or_ip', rate='500/m')
def index(request):
    if not request.user.is_authenticated:
        return render(request, 'index.html')

    bio = Bio.objects.filter(user=request.user).first()
    if not bio:
        return redirect('check')

    imgs = (
        Image.objects.filter(Q(user=bio) | Q(user__in=bio.friends.all()))
        .select_related('user__user')
        .order_by('-create_at')
    )
    page = Paginator(imgs, FEED_PAGE_SIZE).get_page(1)
    return render(request, 'images/index.html', {
        'images': page,
        'has_next': page.has_next(),
        'last_page': page[-1].create_at if len(page) else None,
    })
