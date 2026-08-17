from django.shortcuts import render
from django_ratelimit.decorators import ratelimit
from django.contrib.auth.decorators import login_required

# Create your views here.
@login_required
def image_pagination_take(request):
    pass
