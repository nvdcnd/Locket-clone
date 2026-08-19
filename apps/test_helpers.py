"""Đồ nghề dùng chung cho các bài test của dự án.

Gom về một chỗ những việc mà test nào cũng cần:
tạo người dùng kèm Bio, tạo ảnh mẫu, thư mục chứa ảnh tạm.
"""
import tempfile

from django.apps import apps as app_registry
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase

from apps.bio.models import Bio

# Ảnh sinh ra trong lúc test được ném hết vào thư mục tạm này,
# không làm bẩn thư mục dự án.
TEST_MEDIA_DIR = tempfile.mkdtemp(prefix='drf_test_media_')

# Hasher nhanh cho test. Settings mới đặt BCrypt lên đầu nhưng gói bcrypt
# chưa được cài (không có trong requirements.txt) — thiếu override này thì
# mọi thao tác tạo user / đăng nhập đều sập.
FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Cấu hình chung cho các class test: tắt rate limit, ảnh vào thư mục tạm,
# băm mật khẩu nhanh.
TEST_SETTINGS = dict(
    RATELIMIT_ENABLE=False,
    MEDIA_ROOT=TEST_MEDIA_DIR,
    PASSWORD_HASHERS=FAST_HASHERS,
)

# Một ảnh GIF 1x1 hợp lệ, đủ nhỏ để nhét thẳng vào code test.
TINY_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff'
    b'!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00'
    b'\x02\x02D\x01\x00;'
)

_tables_ready = False


def create_missing_tables():
    """Tự tạo bảng cho những model chưa có file migration.

    Các app bio/chat/image_share/forgot_password có thư mục migrations
    nhưng rỗng, nên Django không tạo bảng cho chúng trong test DB.
    Hàm này vá lại chuyện đó ngay trong phạm vi test, không đụng vào dự án.
    """
    global _tables_ready
    if _tables_ready:
        return
    existing = set(connection.introspection.table_names())
    with connection.schema_editor() as editor:
        for model in app_registry.get_models():
            if model._meta.db_table not in existing:
                editor.create_model(model)
    _tables_ready = True


class BaseTestCase(TestCase):
    """TestCase dùng chung: bảo đảm bảng dữ liệu đã sẵn sàng trước khi test."""

    @classmethod
    def setUpClass(cls):
        create_missing_tables()
        super().setUpClass()


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
    """Cho hai Bio trở thành bạn của nhau (đủ cả hai chiều)."""
    bio1.friends.add(bio2)
    bio2.friends.add(bio1)
