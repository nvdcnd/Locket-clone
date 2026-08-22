"""Chat 1-1.

Quy ước id trong URL: `receiver_id` là Bio.id (UUID) của người nhận, KHÔNG phải User.id (int).
Toàn bộ template/JS đều truyền Bio.id (friend.id, info.id, img.user.id, post.creater).

Payload đẩy qua channel layer chỉ chứa kiểu JSON/msgpack cơ bản (str/int/bool): Redis channel
layer serialize bằng msgpack, và msgpack không serialize được UUID/datetime -> mọi UUID phải str().
"""
import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.bio.models import Bio
from apps.image_share.models import Image

from .models import ChatRoom, Messages

MESSAGE_MAX_LENGTH = 2000
ROOM_PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _my_bio(request):
    return Bio.objects.filter(user=request.user).select_related('user').first()


def _find_room(bio, other):
    return ChatRoom.objects.filter(
        Q(user1=bio, user2=other) | Q(user1=other, user2=bio)
    ).first()


def _get_or_create_room(bio, other):
    """Tìm phòng của 2 người, chưa có thì tạo; an toàn khi 2 request tạo cùng lúc."""
    room = _find_room(bio, other)
    if room:
        return room
    try:
        with transaction.atomic():
            return ChatRoom.objects.create(user1=bio, user2=other)
    except IntegrityError:
        # Request khác vừa tạo xong (unique_together) -> lấy lại.
        return _find_room(bio, other)


def _are_friends(bio, other):
    return bio.friends.filter(pk=other.pk).exists()


def _resolve_receiver(request, receiver_id):
    """Trả về (bio, receiver, error_response). error_response khác None nghĩa là dừng."""
    bio = _my_bio(request)
    if not bio:
        return None, None, JsonResponse({'error': 'bio not found'}, status=400)
    receiver = Bio.objects.filter(id=receiver_id).select_related('user').first()
    if not receiver or receiver.pk == bio.pk:
        return bio, None, JsonResponse({'error': 'invalid receiver'}, status=400)
    if not _are_friends(bio, receiver):
        return bio, receiver, JsonResponse({'error': 'not friends'}, status=403)
    return bio, receiver, None


def _parse_message(request):
    """Đọc {"message": "..."} từ body JSON. Trả về (message, error_response)."""
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return None, JsonResponse({'error': 'invalid json'}, status=400)
    if not isinstance(data, dict):
        return None, JsonResponse({'error': 'invalid json'}, status=400)
    message = data.get('message')
    if not isinstance(message, str) or not message.strip():
        return None, JsonResponse({'error': 'message is required'}, status=400)
    message = message.strip()
    if len(message) > MESSAGE_MAX_LENGTH:
        return None, JsonResponse({'error': 'message too long'}, status=400)
    return message, None


def _broadcast(room, message):
    payload = {
        'type': 'new_message_notification',
        'message_id': str(message.id),
        'text': message.message,
        'sender_id': str(message.sender_id),
        'created_at': message.created_at.isoformat(),
    }
    if message.message_reply_id:
        payload['reply_message_id'] = str(message.message_reply_id)
    if message.image_reply_id:
        payload['reply_image_id'] = str(message.image_reply_id)
    async_to_sync(get_channel_layer().group_send)(f'chat_{room.id}', payload)


def _create_message(room, sender, text, **extra):
    with transaction.atomic():
        message = Messages.objects.create(sender=sender, chatroom=room, message=text, **extra)
        # Đẩy phòng lên đầu danh sách chat (updated_at auto_now).
        room.save(update_fields=['updated_at'])
        # Chỉ thông báo sau khi DB đã commit, tránh client nhận tin rồi tải lại mà chưa thấy.
        transaction.on_commit(lambda: _broadcast(room, message))
    return message


def _sent(message):
    return JsonResponse({'success': 'message was sent', 'message_id': str(message.id)}, status=200)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def chat_lists(request):
    bio = _my_bio(request)
    if not bio:
        return redirect('check')

    rooms = (
        ChatRoom.objects.filter(Q(user1=bio) | Q(user2=bio))
        .select_related('user1__user', 'user2__user')
        .order_by('-updated_at')
    )
    paginator = Paginator(rooms, 10)
    page_obj = paginator.get_page(request.GET.get('page'))  # tự xử lý page sai / vượt trang

    chat_items = []
    for room in page_obj:
        if room.user1_id == bio.id:
            other, my_read_at = room.user2, room.user1_last_read_at
        else:
            other, my_read_at = room.user1, room.user2_last_read_at
        last_msg = (
            room.messages_at_chat_room.select_related('sender__user')
            .order_by('-created_at')
            .first()
        )
        unread = bool(
            last_msg
            and last_msg.sender_id != bio.id
            and (my_read_at is None or last_msg.created_at > my_read_at)
        )
        chat_items.append({'room': room, 'other': other, 'last_msg': last_msg, 'unread': unread})

    return render(request, 'chat/list.html', {
        'chat_lists': page_obj,
        'chat_items': chat_items,
        'mybio_id': bio.id,
        'total_page': paginator.num_pages,
        'page': page_obj.number,
    })


@ratelimit(key='user_or_ip', rate='200/m')
@login_required
@require_POST
def send_message(request, receiver_id):
    bio, receiver, error = _resolve_receiver(request, receiver_id)
    if error:
        return error
    text, error = _parse_message(request)
    if error:
        return error
    room = _get_or_create_room(bio, receiver)
    return _sent(_create_message(room, bio, text))


@ratelimit(key='user_or_ip', rate='200/m')
@login_required
@require_POST
def reply_message(request, receiver_id, msg_id):
    bio, receiver, error = _resolve_receiver(request, receiver_id)
    if error:
        return error
    text, error = _parse_message(request)
    if error:
        return error
    room = _find_room(bio, receiver)
    original = Messages.objects.filter(id=msg_id, chatroom=room).first() if room else None
    if not original:
        return JsonResponse({'error': 'message was not sent'}, status=404)
    return _sent(_create_message(room, bio, text, message_reply=original))


@ratelimit(key='user_or_ip', rate='200/m')
@login_required
@require_POST
def reply_image(request, receiver_id, img_id):
    bio, receiver, error = _resolve_receiver(request, receiver_id)
    if error:
        return error
    text, error = _parse_message(request)
    if error:
        return error
    # Chỉ trả lời được ảnh của mình hoặc của người nhận (ảnh mà cả hai cùng thấy).
    img = Image.objects.filter(Q(user=bio) | Q(user=receiver), id=img_id).first()
    if not img:
        return JsonResponse({'error': 'message was not sent'}, status=404)
    room = _get_or_create_room(bio, receiver)
    return _sent(_create_message(room, bio, text, image_reply=img))


@ratelimit(key='user_or_ip', rate='200/m')
@login_required
def chat_with(request, receiver_id):
    """Mở (hoặc tạo) phòng chat 1-1 với một người bạn rồi chuyển tới phòng đó."""
    bio = _my_bio(request)
    if not bio:
        return redirect('check')
    receiver = Bio.objects.filter(id=receiver_id).first()
    if not receiver or receiver.pk == bio.pk or not _are_friends(bio, receiver):
        return redirect('chat_list')
    room = _get_or_create_room(bio, receiver)
    return redirect('chat_room', room_id=room.id)


@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def room(request, room_id):
    bio = _my_bio(request)
    if not bio:
        return redirect('check')

    # Chỉ cho vào phòng mà chính mình là thành viên.
    chat_room = (
        ChatRoom.objects.filter(Q(user1=bio) | Q(user2=bio), id=room_id)
        .select_related('user1__user', 'user2__user')
        .first()
    )
    if not chat_room:
        return redirect('chat_list')

    if chat_room.user1_id == bio.id:
        receiver = chat_room.user2
        my_read_field, my_read_at = 'user1_last_read_at', chat_room.user1_last_read_at
        their_read_at = chat_room.user2_last_read_at
    else:
        receiver = chat_room.user1
        my_read_field, my_read_at = 'user2_last_read_at', chat_room.user2_last_read_at
        their_read_at = chat_room.user1_last_read_at

    chat_messages = list(
        chat_room.messages_at_chat_room
        .select_related('sender__user', 'message_reply__sender__user', 'image_reply')
        .order_by('-created_at')[:ROOM_PAGE_SIZE]
    )[::-1]

    # Đánh dấu mình đã đọc tới tin mới nhất. Dùng update() để không đụng updated_at (auto_now)
    # và không chạy lại ChatRoom.save().
    if chat_messages:
        newest_at = chat_messages[-1].created_at
        if my_read_at is None or newest_at > my_read_at:
            ChatRoom.objects.filter(pk=chat_room.pk).update(**{my_read_field: newest_at})

    # "Đã xem": tin cuối cùng CỦA MÌNH mà người kia đã đọc tới.
    seen_msg_id = None
    if their_read_at:
        for m in reversed(chat_messages):
            if m.sender_id == bio.id:
                if m.created_at <= their_read_at:
                    seen_msg_id = m.id
                break

    return render(request, 'chat/room.html', {
        'room_id': room_id,
        'my_bio_id': bio.id,
        'receiver': receiver,
        'receiver_bio_id': receiver.id,
        'seen_msg_id': seen_msg_id,
        'chat_messages': chat_messages,
    })
