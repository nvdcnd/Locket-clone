from django.shortcuts import render, redirect
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
        page = 1
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, 'chat/list.html', {'chat_lists':page_obj, 'total_page':paginator.count, 'page':page})

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
    bio = Bio.objects.filter(user=request.user).first()
    # Chỉ cho vào phòng mà chính mình là thành viên
    chat_room = ChatRoom.objects.filter(
        Q(user1=bio) | Q(user2=bio), id=room_id
    ).select_related('user1__user', 'user2__user').first()
    if not chat_room:
        return redirect('chat_list')

    receiver = chat_room.user2 if chat_room.user1_id == bio.id else chat_room.user1

    chat_messages = list(
        chat_room.messages_at_chat_room
        .select_related('sender__user', 'message_reply__sender__user', 'image_reply')
        .order_by('-created_at')[:50]
    )[::-1]

    if chat_room.user1_id == bio.id:
        receiver_last_read_msg_id = chat_room.user2_last_read_msg_id
        my_read_field = 'user1_last_read_msg_id'
    else:
        receiver_last_read_msg_id = chat_room.user1_last_read_msg_id
        my_read_field = 'user2_last_read_msg_id'

    # Đánh dấu mình đã đọc tới tin mới nhất (update_fields để không đụng updated_at)
    if chat_messages and getattr(chat_room, my_read_field) < chat_messages[-1].id:
        setattr(chat_room, my_read_field, chat_messages[-1].id)
        chat_room.save(update_fields=[my_read_field])

    return render(request, "chat/room.html", {
        'room_id': room_id,
        'my_bio_id': bio.id,
        'receiver': receiver,
        'receiver_user_id': receiver.user_id,
        'receiver_last_read_msg_id': receiver_last_read_msg_id,
        'chat_messages': chat_messages,
    })
    