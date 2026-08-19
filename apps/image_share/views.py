from django.shortcuts import render
from django_ratelimit.decorators import ratelimit
from django.contrib.auth.decorators import login_required
import json
from django.core.files.base import ContentFile
from ..bio.models import Bio
from .models import *
from django.http.response import JsonResponse
import base64

# Create your views here.
@ratelimit(key='user_or_ip', rate='status=200/m')
@login_required
def image_create(request):
    bio = Bio.objects.filter(user=request.user).first()
    if bio:
        if request.method == 'POST':
            data = json.loads(request.body)

            image = data.get('image')
            text = data.get('text')
            #share_type = data.get('shared_type')

            formats, imgstr = image.split(';base64,')
            ext = formats.split('/')[-1] # Extract extension (e.g., 'png', 'jpeg')

            img = ContentFile(base64.b64decode(imgstr), name=f"uploaded_file.{ext}")
            new_image = Image.objects.create(image=img,text=text,image_type=Image_type.objects.get(name=share_type))

            return JsonResponse({'success','đăng ảnh thành công'}, status=200)
    else:
        return JsonResponse({'error','đăng ảnh thất bại'},status=500)

@ratelimit(key='user_or_ip', rate='status=500/m')
@login_required
def image_list_infinity_scroll(request, last_page, offset):
    bio = Bio.objects.filter(user=request.user).first()
    friend_ids = bio.friends.values_list('id', flat=True)
    imgs = Image.objects.filter(Q(user=bio) | Q(user_id__in=friend_ids)).orderby('-create_at').all()

    if last_page:
        imgs = imgs.filter(create_at__lt=last_page)

    img = list(imgs[:offset+1])
    img_next = len(img) > offset

    if img_next:
        img = img[:offset]

    results = [{'id':id, 'image_url':img.image.url, 'text': img.text, 'creater': img.user, 'create_at':img.create_at}]

    return JsonResponse({
        'images': results,
        'has_next': img_next,
        'last_page': results[-1]['create_at'] if results else None
    }, status=200)

@ratelimit(key='user_or_ip', rate='status=500/m')
@login_required
def emojing_image(request, id):
    bio = Bio.objects.get(user=request.user)
    img = Image.objects.get(id=id)
    if bio and img:
        data = json.loads(request.body)
        emoji = data.get('emoji')
        new_emoji_4_img = Image_emoji_share.objects.create(image=img,user=bio,emoji=Emoji_type.object.get(name=emoji))

        return JsonResponse({'success':'sucessful'}, status=200)
    else:
        return JsonResponse({'error':'error'}, status=500)

@login_required
def image_delete(request, id):
    img = Image.objects.get(id=id,user__user_id = request.user.id)
    if img:
        img.delete()
        return JsonResponse({'success':'image deleted'}, status=200)
    else:
        return JsonResponse({'error':'you can not delete this image'}, status=500)