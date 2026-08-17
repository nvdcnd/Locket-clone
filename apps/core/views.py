from django.shortcuts import render,redirect
from django.http.response import JsonResponse
from django.views.decorators.http import require_http_methods


# Create your views here.
@require_http_methods(["GET", "HEAD"])
def health_chech(request):
    return JsonResponse({"status":'ok'},200)

def index(request):
    if request.user.is_authenticated:
        return render('hello.html')
    else:
        return render('index.html')
