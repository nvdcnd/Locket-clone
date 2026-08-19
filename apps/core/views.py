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
def health_check(request):
    return JsonResponse({"status":'ok'},status=200)

@ratelimit(key='user_or_ip', rate='500/m')
def index(request):
    if request.user.is_authenticated:
        bio = Bio.objects.filter(user=request.user).first()
        if not bio:
            return redirect('check')
        friend_ids = bio.friends.values_list('id', flat=True)
        imgs = Image.objects.filter(Q(user=bio) | Q(user_id__in=friend_ids)).order_by('-create_at').all()
        pagination = Paginator(imgs, 10)
        p = pagination.get_page(1)
        return render(request, 'images/index.html',{'images':p,'has_next': len(imgs) > 10, 'last_page':p[-1].create_at if len(p) else None})
    else:
        return render(request, 'index.html')
