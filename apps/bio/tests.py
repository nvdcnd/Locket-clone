"""Test cho app bio: tài khoản, đăng nhập, đăng ký và bạn bè.

Mỗi test mô tả một hành vi mà người dùng mong đợi.
Test nào fail nghĩa là code thật đang không làm đúng hành vi đó.

Lưu ý: add_friend, unfriend, bio, bio_information_change đã có url;
còn friends_list, friends_information, logout vẫn chưa được gắn vào
urls.py nên phải gọi thẳng hàm view bằng RequestFactory.
"""
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse

from apps.test_helpers import (
    CAI_DAT_TEST, HASHER_NHANH, TestCoDuLieu, anh_mau, ket_ban, tao_nguoi_dung,
)

from apps.bio import views
from apps.bio.forms import LoginForm, UserRegistrationForm
from apps.bio.models import Bio


@override_settings(**CAI_DAT_TEST)
class BioModelTest(TestCoDuLieu):
    def test_tao_bio_cho_nguoi_dung(self):
        """Mỗi người dùng có một Bio kèm avatar."""
        user, bio = tao_nguoi_dung('an')
        self.assertEqual(bio.user, user)
        self.assertTrue(bio.avatar.name)

    def test_tao_bio_khong_can_avatar(self):
        """Avatar giờ cho phép để trống (null=True) nên tạo Bio trần vẫn được."""
        user = User.objects.create_user('moi', 'moi@example.com', 'mat-khau-manh-123')
        bio = Bio.objects.create(user=user)
        self.assertFalse(bio.avatar)

    def test_ket_ban_la_quan_he_hai_chieu(self):
        """An kết bạn với Bình thì Bình cũng tự động là bạn của An."""
        _, bio_an = tao_nguoi_dung('an')
        _, bio_binh = tao_nguoi_dung('binh')
        bio_an.friends.add(bio_binh)
        self.assertIn(bio_binh, bio_an.friends.all())
        self.assertIn(bio_an, bio_binh.friends.all())

    def test_xoa_user_thi_bio_mat_theo(self):
        """Xóa tài khoản thì Bio gắn với nó cũng bị xóa."""
        user, bio = tao_nguoi_dung('an')
        user.delete()
        self.assertFalse(Bio.objects.filter(id=bio.id).exists())


class LoginFormTest(TestCoDuLieu):
    def test_dien_du_email_va_mat_khau_thi_hop_le(self):
        form = LoginForm(data={'email': 'an@example.com', 'password': 'bi-mat'})
        self.assertTrue(form.is_valid())

    def test_bo_trong_thi_khong_hop_le(self):
        form = LoginForm(data={})
        self.assertFalse(form.is_valid())

    def test_email_sai_dinh_dang_bi_tu_choi(self):
        """Ô email phải kiểm tra định dạng (hiện là CharField nên chưa kiểm tra)."""
        form = LoginForm(data={'email': 'khong-phai-email', 'password': 'bi-mat'})
        self.assertFalse(form.is_valid())


class UserRegistrationFormTest(TestCoDuLieu):
    def test_form_dang_ky_co_du_bon_truong(self):
        """Form đăng ký phải khởi tạo được và có đủ username, email, image, password.

        (Hiện form là ModelForm nhưng thiếu class Meta nên khởi tạo là vỡ.)
        """
        form = UserRegistrationForm()
        for truong in ['username', 'email', 'image', 'password']:
            self.assertIn(truong, form.fields)


@override_settings(**CAI_DAT_TEST)
class DangNhapTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user, self.bio = tao_nguoi_dung('an', 'mat-khau-manh-123')

    def test_mo_trang_dang_nhap(self):
        """Mở trang đăng nhập (GET) phải nhận được trang, không phải lỗi."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_dang_nhap_dung_thi_duoc_vao(self):
        """Đăng nhập đúng email + mật khẩu thì được chuyển sang trang check."""
        response = self.client.post(reverse('login'), {
            'email': 'an@example.com',
            'password': 'mat-khau-manh-123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('check'))

    def test_dang_nhap_sai_thi_bi_tu_choi(self):
        """Sai mật khẩu thì không được đăng nhập, bị đưa về trang chủ."""
        response = self.client.post(reverse('login'), {
            'email': 'an@example.com',
            'password': 'sai-be-bet',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        self.assertNotIn('_auth_user_id', self.client.session,
                         'Đăng nhập sai thì session không được chứa user')


@override_settings(PASSWORD_HASHERS=HASHER_NHANH)
class ChanSpamDangNhapTest(TestCoDuLieu):
    """Trang đăng nhập giới hạn 10 lần/phút cho mỗi địa chỉ IP."""

    def setUp(self):
        cache.clear()
        self.client = Client(raise_request_exception=False)

    def tearDown(self):
        cache.clear()

    def test_lan_thu_11_bi_chan(self):
        du_lieu = {'email': 'ai-do@example.com', 'password': 'sai'}
        for _ in range(10):
            self.client.post(reverse('login'), du_lieu)
        response = self.client.post(reverse('login'), du_lieu)
        self.assertEqual(response.status_code, 403)


@override_settings(**CAI_DAT_TEST)
class DangKyTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_dang_ky_tao_tai_khoan_moi(self):
        """Đăng ký hợp lệ thì tạo User + Bio, đăng nhập luôn và chuyển trang."""
        response = self.client.post(reverse('signup'), {
            'username': 'binh',
            'email': 'binh@example.com',
            'password': 'mat-khau-manh-123',
            'image': anh_mau(),
        })
        self.assertTrue(User.objects.filter(username='binh').exists(),
                        'Đăng ký xong phải có tài khoản trong hệ thống')
        self.assertTrue(Bio.objects.filter(user__username='binh').exists(),
                        'Đăng ký xong phải có Bio kèm avatar')
        self.assertEqual(response.status_code, 302)

    def test_dang_ky_email_trung_khong_tao_them_tai_khoan(self):
        """Đăng ký bằng email đã tồn tại thì không được tạo thêm tài khoản."""
        tao_nguoi_dung('an')
        so_user_truoc = User.objects.count()
        response = self.client.post(reverse('signup'), {
            'username': 'an-gia-mao',
            'email': 'an@example.com',
            'password': 'mat-khau-khac-456',
            'image': anh_mau(),
        })
        self.assertEqual(User.objects.count(), so_user_truoc)
        self.assertLess(response.status_code, 500,
                        'Email trùng thì báo lỗi tử tế chứ không được sập server')


@override_settings(**CAI_DAT_TEST)
class TrangCheckTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_chua_dang_nhap_bi_day_ve_trang_login(self):
        response = self.client.get(reverse('check'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_da_co_bio_thi_ve_thang_trang_chu(self):
        """Ai đã có Bio rồi thì trang check chỉ việc đưa họ về trang chủ."""
        user, _ = tao_nguoi_dung('an')
        self.client.force_login(user)
        response = self.client.get(reverse('check'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_chua_co_bio_thi_tu_tao_roi_ve_trang_chu(self):
        """Người chưa có Bio vào trang check thì được tự tạo Bio rồi đưa về trang chủ.

        (Hành vi mới sau merge: không cần nộp avatar nữa vì avatar đã null=True.)
        """
        user = User.objects.create_user('moi', 'moi@example.com', 'mat-khau-manh-123')
        self.client.force_login(user)
        response = self.client.get(reverse('check'))
        self.assertTrue(Bio.objects.filter(user=user).exists(),
                        'Trang check phải tự tạo Bio cho người chưa có')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')


@override_settings(**CAI_DAT_TEST)
class DangXuatTest(TestCoDuLieu):
    def test_dang_xuat_roi_ve_trang_chu(self):
        """Đăng xuất xong thì được đưa về trang chủ.

        (View logout vẫn chưa có url nên gọi thẳng hàm.)
        """
        user, _ = tao_nguoi_dung('an')
        request = RequestFactory().get('/user/authentication/logout')
        request.user = user
        response = views.logout(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')


@override_settings(**CAI_DAT_TEST)
class BanBeTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user_an, self.bio_an = tao_nguoi_dung('an')
        self.user_binh, self.bio_binh = tao_nguoi_dung('binh')
        self.client.force_login(self.user_an)

    def test_ket_ban_thanh_cong_ca_hai_chieu(self):
        """An gửi kết bạn với Bình thì hai người thành bạn của nhau."""
        response = self.client.post(reverse('add_friend', args=[self.bio_binh.id]))
        self.assertIn(self.bio_binh, self.bio_an.friends.all())
        self.assertIn(self.bio_an, self.bio_binh.friends.all())
        self.assertEqual(response.status_code, 200)

    def test_ket_ban_voi_nguoi_da_la_ban_thi_bao_loi(self):
        ket_ban(self.bio_an, self.bio_binh)
        response = self.client.post(reverse('add_friend', args=[self.bio_binh.id]))
        self.assertGreaterEqual(response.status_code, 400)

    def test_chua_dang_nhap_khong_ket_ban_duoc(self):
        khach = Client(raise_request_exception=False)
        response = khach.post(reverse('add_friend', args=[self.bio_binh.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_huy_ket_ban_thanh_cong_ca_hai_chieu(self):
        """Đang là bạn mà hủy kết bạn thì cả hai phía đều hết là bạn."""
        ket_ban(self.bio_an, self.bio_binh)
        response = self.client.post(reverse('unfriend', args=[self.bio_binh.id]))
        self.assertNotIn(self.bio_binh, self.bio_an.friends.all())
        self.assertNotIn(self.bio_an, self.bio_binh.friends.all())
        self.assertEqual(response.status_code, 200)

    def test_huy_ket_ban_voi_nguoi_la_thi_bao_loi(self):
        response = self.client.post(reverse('unfriend', args=[self.bio_binh.id]))
        self.assertGreaterEqual(response.status_code, 400)

    def test_chua_dang_nhap_khong_huy_ket_ban_duoc(self):
        khach = Client(raise_request_exception=False)
        response = khach.post(reverse('unfriend', args=[self.bio_binh.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_xem_danh_sach_ban_be(self):
        """(View friends_list vẫn chưa có url nên gọi thẳng hàm.)"""
        ket_ban(self.bio_an, self.bio_binh)
        request = RequestFactory().get('/ban-be')
        request.user = self.user_an
        response = views.friends_list(request)
        self.assertEqual(response.status_code, 200)

    def test_xem_thong_tin_cua_ban(self):
        """(View friends_information vẫn chưa có url nên gọi thẳng hàm.)"""
        ket_ban(self.bio_an, self.bio_binh)
        request = RequestFactory().get('/ban-be/xem')
        request.user = self.user_an
        response = views.friends_information(request, self.bio_binh.id)
        self.assertEqual(response.status_code, 200)


@override_settings(**CAI_DAT_TEST)
class TrangCaNhanTest(TestCoDuLieu):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user, self.bio = tao_nguoi_dung('an')

    def test_xem_trang_ca_nhan_cua_minh(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('bio'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bio/information.html')

    def test_chua_dang_nhap_bi_day_ve_trang_login(self):
        response = self.client.get(reverse('bio'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_doi_thong_tin_ca_nhan(self):
        """Đổi username, email, mật khẩu, avatar thì thông tin mới phải được lưu."""
        self.client.force_login(self.user)
        self.client.post(reverse('bio_information_change'), {
            'username': 'an-moi',
            'email': 'an-moi@example.com',
            'password': 'mat-khau-moi-789',
            'file': anh_mau('avatar-moi.gif'),
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'an-moi')
        self.assertEqual(self.user.email, 'an-moi@example.com')
