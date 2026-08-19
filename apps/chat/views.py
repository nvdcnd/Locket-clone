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
def send_message(request, receiver_id):
    bio = Bio.objects.filter(user=request.user).first()
    receiver = Bio.objects.filter(user__id=receiver_id).first()
    chat_room = ChatRoom.objects.filter(Q(user1 = bio , user2=receiver) | Q(user1=receiver, user2=bio)).first()
    if not chat_room:
        chat_room = ChatRoom.objects.create(user1=bio, user2=receiver)
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
            f'chat_{chat_room.id}',
            {
                'type': 'new_message_notification',
                'message_id': new_message.id,
                'text': new_message.message,
                'sender_id': new_message.sender.id
            }
        )

        #new_message.save()
        return JsonResponse({'success':'message was sent','message_id':new_message.id}, status=200)

@ratelimit(key='user_or_ip', rate='200/m')
@login_required
def reply_message(request, receiver_id, msg_id):
    bio = Bio.objects.filter(user=request.user).first()
    receiver = Bio.objects.filter(user__id=receiver_id).first()
    chat_room = ChatRoom.objects.filter(Q(user1 = bio , user2=receiver) | Q(user1=receiver, user2=bio)).first()
    msg = Messages.objects.filter(id=msg_id,chatroom=chat_room).first()
    if chat_room and msg:
        if request.method == 'POST':
            data = json.loads(request.body)
            message = data.get('message')

            new_message = Messages.objects.create(
                sender = bio,
                chatroom = chat_room,
                message = message,
                message_reply = msg
            )

            channel_layer = get_channel_layer()

            async_to_sync(channel_layer.group_send)(
                f'chat_{chat_room.id}',
                {
                    'type': 'new_message_notification',
                    'message_id': new_message.id,
                    'text': new_message.message,
                    'reply_message_id': new_message.message_reply.id,
                    'sender_id': new_message.sender.id
                }
            )

            #new_message.save()
            return JsonResponse({'success':'message was sent','message_id':new_message.id}, status=200)
    return JsonResponse({'error':'message was not sent'}, status=404)

@ratelimit(key='user_or_ip', rate='200/m')
@login_required
def reply_image(request, receiver_id, img_id):
    bio = Bio.objects.filter(user=request.user).first()
    receiver = Bio.objects.filter(user__id=receiver_id).first()
    chat_room = ChatRoom.objects.filter(Q(user1 = bio , user2=receiver) | Q(user1=receiver, user2=bio)).first()
    if not chat_room:
        chat_room = ChatRoom.objects.create(user1=bio, user2=receiver)
    img = Image.objects.filter(Q(user=bio) | Q(user=receiver), id=img_id).first()
    if img:
        if request.method == 'POST':
            data = json.loads(request.body)
            message = data.get('message')

            new_message = Messages.objects.create(
                sender = bio,
                chatroom = chat_room,
                message = message,
                image_reply = img
            )

            channel_layer = get_channel_layer()

            async_to_sync(channel_layer.group_send)(
                f'chat_{chat_room.id}',
                {
                    'type': 'new_message_notification',
                    'message_id': new_message.id,
                    'text': new_message.message,
                    'reply_image_id': new_message.image_reply.id,
                    'sender_id': new_message.sender.id
                }
            )

            #new_message.save()
            return JsonResponse({'success':'message was sent','message_id':new_message.id}, status=200)
    return JsonResponse({'error':'message was not sent'}, status=404)
    
@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def room(request, room_id):
    return render(request, "chat/room.html", {'room_id':room_id})
    