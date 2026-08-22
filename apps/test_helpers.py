"""Đồ nghề dùng chung cho các bài test của dự án.

Gom về một chỗ những việc mà test nào cũng cần:
tạo người dùng kèm Bio, tạo ảnh mẫu, thư mục chứa ảnh tạm.
"""
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.bio.models import Bio

# Ảnh sinh ra trong lúc test được ném hết vào thư mục tạm này,
# không làm bẩn thư mục dự án.
TEST_MEDIA_DIR = tempfile.mkdtemp(prefix='drf_test_media_')

# Hasher nhanh cho test (BCrypt thật chậm ~100ms/lần băm).
FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Cấu hình chung cho các class test: tắt rate limit, ảnh vào thư mục tạm,
# băm mật khẩu nhanh, channel layer trong RAM, lưu file cục bộ.
TEST_SETTINGS = dict(
    RATELIMIT_ENABLE=False,
    MEDIA_ROOT=TEST_MEDIA_DIR,
    PASSWORD_HASHERS=FAST_HASHERS,
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)

# Một ảnh GIF 1x1 hợp lệ, đủ nhỏ để nhét thẳng vào code test.
TINY_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff'
    b'!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00'
    b'\x02\x02D\x01\x00;'
)


class BaseTestCase(TestCase):
    """TestCase dùng chung.

    Trước đây class này tự tạo bảng vì các app chưa có migration; giờ migration
    thật đã có (apps/*/migrations/0001_initial.py) nên chỉ còn là alias của TestCase,
    giữ tên để các file test không phải đổi.
    """


def sample_image(name='sample.gif'):
    """Trả về một file ảnh upload được, dùng làm avatar hay ảnh chia sẻ."""
    return SimpleUploadedFile(name, TINY_GIF, content_type='image/gif')


def create_user_with_bio(username='an', password='mat-khau-manh-123'):
    """Tạo một User kèm Bio có avatar. Trả về cặp (user, bio)."""
    user = User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password=password,
    )
    bio = Bio.objects.create(user=user, avatar=sample_image(f'{username}.gif'))
    return user, bio


def make_friends(bio1, bio2):
    """Cho hai Bio trở thành bạn của nhau (ManyToMany đối xứng nên một chiều là đủ)."""
    bio1.friends.add(bio2)
