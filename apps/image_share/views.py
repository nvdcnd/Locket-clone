import base64
import binascii
import io
import json
import logging
import uuid
from datetime import datetime, time

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from PIL import Image as PILImage
from PIL import UnidentifiedImageError

from apps.bio.models import Bio

from .models import Emoji_type, Image, Image_emoji_share

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB sau khi giải mã base64
MAX_FEED_PAGE = 50
ALLOWED_FORMATS = {'JPEG': 'jpg', 'PNG': 'png', 'GIF': 'gif', 'WEBP': 'webp'}
EMOJI_MAX_LENGTH = 16


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _json_body(request):
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _decode_image_data_url(value):
    """'data:image/png;base64,....' -> (bytes, ext). Raise ValueError nếu không hợp lệ."""
    if not isinstance(value, str) or ';base64,' not in value:
        raise ValueError('image phải là data URL base64')
    header, payload = value.split(';base64,', 1)
    if not header.startswith('data:image/'):
        raise ValueError('image phải là data URL dạng data:image/...')
    payload = ''.join(payload.split())
    # Kiểm tra độ dài TRƯỚC khi decode để không cấp phát bộ nhớ cho payload khổng lồ.
    if len(payload) > MAX_IMAGE_BYTES * 4 // 3 + 4:
        raise ValueError('ảnh quá lớn (tối đa 8MB)')
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('dữ liệu base64 không hợp lệ')
    if not raw:
        raise ValueError('ảnh rỗng')
    try:
        with PILImage.open(io.BytesIO(raw)) as im:
            im.verify()
            fmt = im.format
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError('dữ liệu không phải là ảnh')
    ext = ALLOWED_FORMATS.get(fmt or '')
    if not ext:
        raise ValueError('định dạng ảnh không được hỗ trợ (jpg/png/gif/webp)')
    return raw, ext


def _parse_cursor(value):
    """Chuỗi ISO datetime (hoặc ngày) -> aware datetime; None nếu không hợp lệ."""
    try:
        dt = parse_datetime(value)
        if dt is None:
            d = parse_date(value)
            if d is None:
                return None
            dt = datetime.combine(d, time.min)
    except ValueError:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def _visible_images(bio):
    """Ảnh của mình + của bạn bè."""
    return Image.objects.filter(Q(user=bio) | Q(user__in=bio.friends.all()))


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
@ratelimit(key='user_or_ip', rate='200/m')
@login_required
@require_POST
def image_create(request):
    bio = Bio.objects.filter(user=request.user).first()
    if not bio:
        return JsonResponse({'error': 'bio not found'}, status=400)

    data = _json_body(request)
    if data is None:
        return JsonResponse({'error': 'invalid json'}, status=400)

    text = data.get('text') or ''
    if not isinstance(text, str):
        return JsonResponse({'error': 'text không hợp lệ'}, status=400)
    text = text.strip()[:255]

    try:
        raw, ext = _decode_image_data_url(data.get('image'))
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    img = ContentFile(raw, name=f'{uuid.uuid4().hex}.{ext}')
    Image.objects.create(image=img, text=text, user=bio)
    return JsonResponse({'success': 'đăng ảnh thành công'}, status=200)


@ratelimit(key='user_or_ip', rate='500/m')
@login_required
def image_list_infinity_scroll(request, last_page, offset=10):
    bio = Bio.objects.filter(user=request.user).first()
    if not bio:
        return JsonResponse({'error': 'bio not found'}, status=400)

    cursor = _parse_cursor(last_page)
    if cursor is None:
        return JsonResponse({'error': 'last_page phải là thời gian ISO 8601'}, status=400)
    offset = max(1, min(int(offset), MAX_FEED_PAGE))

    imgs = (
        _visible_images(bio)
        .filter(create_at__lt=cursor)
        .select_related('user__user')
        .order_by('-create_at')
    )
    img = list(imgs[:offset + 1])
    img_next = len(img) > offset
    if img_next:
        img = img[:offset]

    results = [
        {
            'id': str(i.id),
            'image_url': i.image.url,
            'text': i.text,
            'creater': str(i.user_id),            # Bio.id -> dùng cho endpoint chat /chat/to/<bio_id>/
            'creater_user_id': i.user.user_id,    # User.id -> so với request.user.id để biết "ảnh của mình"
            'creater_name': i.user.user.username,
            'avatar_url': i.user.avatar.url if i.user.avatar else None,
            'create_at': i.create_at.isoformat(),
        }
        for i in img
    ]

    return JsonResponse({
        'images': results,
        'has_next': img_next,
        'last_page': img[-1].create_at.isoformat() if img else None,
    }, status=200)


@ratelimit(key='user_or_ip', rate='500/m')
@login_required
@require_POST
def emojing_image(request, id):
    bio = Bio.objects.filter(user=request.user).first()
    img = _visible_images(bio).filter(id=id).first() if bio else None
    if not bio or not img:
        return JsonResponse({'error': 'image not found'}, status=404)

    data = _json_body(request)
    emoji = data.get('emoji') if data else None
    if not isinstance(emoji, str) or not emoji.strip() or len(emoji) > EMOJI_MAX_LENGTH:
        return JsonResponse({'error': 'emoji không hợp lệ'}, status=400)

    emoji_type, _ = Emoji_type.objects.get_or_create(emoji=emoji.strip())
    Image_emoji_share.objects.create(image=img, user=bio, emoji=emoji_type)
    return JsonResponse({'success': 'sucessful'}, status=200)


@ratelimit(key='user_or_ip', rate='100/m')
@login_required
@require_POST
def image_delete(request, id):
    img = Image.objects.filter(id=id, user__user=request.user).first()
    if not img:
        return JsonResponse({'error': 'you can not delete this image'}, status=404)

    stored_file = img.image
    img.delete()
    # Xoá file trên storage sau khi xoá bản ghi; lỗi storage không được làm request thất bại.
    try:
        stored_file.delete(save=False)
    except Exception:  # noqa: BLE001 - storage bên ngoài (Cloudinary) có thể lỗi mạng
        logger.warning('Không xoá được file %s trên storage', stored_file.name, exc_info=True)
    return JsonResponse({'success': 'image deleted'}, status=200)
