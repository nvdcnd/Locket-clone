"""Đồ nghề dùng chung cho các bài test của dự án.

Gom về một chỗ những việc mà test nào cũng cần:
tạo người dùng kèm Bio, tạo ảnh mẫu, thư mục chứa ảnh tạm.
"""
import tempfile

from django.apps import apps as danh_sach_app
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase

from apps.bio.models import Bio

# Ảnh sinh ra trong lúc test được ném hết vào thư mục tạm này,
# không làm bẩn thư mục dự án.
THU_MUC_ANH_TAM = tempfile.mkdtemp(prefix='drf_test_media_')

# Hasher nhanh cho test. Settings mới đặt BCrypt lên đầu nhưng gói bcrypt
# chưa được cài (không có trong requirements.txt) — thiếu override này thì
# mọi thao tác tạo user / đăng nhập đều sập.
HASHER_NHANH = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Cấu hình chung cho các class test: tắt rate limit, ảnh vào thư mục tạm,
# băm mật khẩu nhanh.
CAI_DAT_TEST = dict(
    RATELIMIT_ENABLE=False,
    MEDIA_ROOT=THU_MUC_ANH_TAM,
    PASSWORD_HASHERS=HASHER_NHANH,
)

# Một ảnh GIF 1x1 hợp lệ, đủ nhỏ để nhét thẳng vào code test.
ANH_GIF_1X1 = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff'
    b'!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00'
    b'\x02\x02D\x01\x00;'
)


_da_tao_bang = False


def chuan_bi_bang_du_lieu():
    """Tự tạo bảng cho những model chưa có file migration.

    Các app bio/chat/image_share có thư mục migrations nhưng rỗng,
    nên Django không tạo bảng cho chúng trong test DB. Hàm này vá
    lại chuyện đó ngay trong phạm vi test, không đụng vào dự án.
    """
    global _da_tao_bang
    if _da_tao_bang:
        return
    bang_co_san = set(connection.introspection.table_names())
    with connection.schema_editor() as editor:
        for model in danh_sach_app.get_models():
            if model._meta.db_table not in bang_co_san:
                editor.create_model(model)
    _da_tao_bang = True


class TestCoDuLieu(TestCase):
    """TestCase dùng chung: bảo đảm bảng dữ liệu đã sẵn sàng trước khi test."""

    @classmethod
    def setUpClass(cls):
        chuan_bi_bang_du_lieu()
        super().setUpClass()


def anh_mau(ten='anh.gif'):
    """Trả về một file ảnh upload được, dùng làm avatar hay ảnh chia sẻ."""
    return SimpleUploadedFile(ten, ANH_GIF_1X1, content_type='image/gif')


def tao_nguoi_dung(ten='an', mat_khau='mat-khau-manh-123'):
    """Tạo một User kèm Bio có avatar. Trả về cặp (user, bio)."""
    user = User.objects.create_user(
        username=ten,
        email=f'{ten}@example.com',
        password=mat_khau,
    )
    bio = Bio.objects.create(user=user, avatar=anh_mau(f'{ten}.gif'))
    return user, bio


def ket_ban(bio_a, bio_b):
    """Cho hai Bio trở thành bạn của nhau (đủ cả hai chiều)."""
    bio_a.friends.add(bio_b)
    bio_b.friends.add(bio_a)
