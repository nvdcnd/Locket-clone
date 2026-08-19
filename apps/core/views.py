from django.shortcuts import render,redirect
from django.http.response import JsonResponse
from django.views.decorators.http import require_http_methods
from ..image_share.models import Image
from ..bio.models import Bio
from django_ratelimit.decorators import ratelimit
from django.core.paginator import Paginator
from django.db.models import Q

# Create your views here.
@require_http_methods(["GET", "HEAD"])
def health_chech(request):
    return JsonResponse({"status":'ok'},status=200)

@ratelimit(key='user_or_ip', rate='status=500/m')
def index(request):
    if request.user.is_authenticated:
        bio = Bio.objects.get(user=request.user)
        friend_ids = bio.friends.values_list('id', flat=True)
        imgs = Image.objects.filter(Q(user=bio) | Q(user_id__in=friend_ids)).order_by('-create_at')
        pagination = Paginator(imgs, 10)
        p = pagination.get_page(1)
        return render(request, 'images/index.html', {'images': p, 'has_next': p.has_next(), 'last_page': p[-1].create_at if p else None})
    else:
        return render('index.html')
