from django.shortcuts import render
from django_ratelimit.decorators import ratelimit
from django.db.models import Q
from .models import *
import json
from channels.layers import get_channel_layer
from ..bio.models import Bio
from asgiref.sync import async_to_sync
from django.http.response import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# Create your views here.
@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def chat_lists(request):
    bio = Bio.objects.filter(user=request.user).first()
    chats = ChatRoom.objects.filter(Q(user1=bio)|Q(user2=bio)).order_by('-updated_at').all()
    paginator = Paginator(chats,10)
    page = request.GET.get('page')
    try:
        page_obj = paginator.get_page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, 'chat/list.html', {'chat_lists':page_obj})

@ratelimit(key='user_or_ip', rate='200/m')
@login_required
def send_message(request, chat_room_id):
    bio = Bio.objects.filter(user=request.user).first()
    chat_room = ChatRoom.objects.filter(id=chat_room_id).first()
    if chat_room: 
        if request.method == 'POST':
            data = json.loads(request.body)
            message = data.get('message')

            new_message = Messages.objects.create(
                sender = bio,
                chatroom = chat_room,
                message = message
            )

            channel_layer = get_channel_layer()

            async_to_sync(channel_layer.group_send)(
                f'chat_{chat_room_id}',
                {
                    'type': 'chat_message',
                    'message_id': new_message.id,
                    'text': new_message.message,
                    'sender_id': new_message.user.id
                }
            )

            #new_message.save()
            return JsonResponse({'success':'message was sent','message_id':message.id}, 200)
    else:
        return JsonResponse({'error':'cant sent the message'}, 500)
    
@ratelimit(key='user_or_ip', rate='500/m')
def room(request, room_id):
    return render(request, "chat/room.html", {'room_id':room_id})
    