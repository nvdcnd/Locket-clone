"""Test cho app bio: tài khoản, đăng nhập, đăng ký và bạn bè.

Mỗi test mô tả một hành vi mà người dùng mong đợi.
Test nào fail nghĩa là code thật đang không làm đúng hành vi đó.

Toàn bộ view của app đã có url nên test gọi qua client như người dùng thật.
"""
import time
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse

from apps.test_helpers import (
    FAST_HASHERS, TEST_SETTINGS, BaseTestCase,
    create_user_with_bio, make_friends, sample_image,
)

from apps.bio.forms import LoginForm, UserRegistrationForm
from apps.bio.models import Bio


@override_settings(**TEST_SETTINGS)
class BioModelTest(BaseTestCase):
    def test_create_bio_for_user(self):
        """Mỗi người dùng có một Bio kèm avatar."""
        user, bio = create_user_with_bio('an')
        self.assertEqual(bio.user, user)
        self.assertTrue(bio.avatar.name)

    def test_create_bio_without_avatar(self):
        """Avatar giờ cho phép để trống (null=True) nên tạo Bio trần vẫn được."""
        user = User.objects.create_user('moi', 'moi@example.com', 'mat-khau-manh-123')
        bio = Bio.objects.create(user=user)
        self.assertFalse(bio.avatar)

    def test_friendship_is_two_way(self):
        """An kết bạn với Bình thì Bình cũng tự động là bạn của An."""
        _, bio1 = create_user_with_bio('an')
        _, bio2 = create_user_with_bio('binh')
        bio1.friends.add(bio2)
        self.assertIn(bio2, bio1.friends.all())
        self.assertIn(bio1, bio2.friends.all())

    def test_deleting_user_deletes_bio(self):
        """Xóa tài khoản thì Bio gắn với nó cũng bị xóa."""
        user, bio = create_user_with_bio('an')
        user.delete()
        self.assertFalse(Bio.objects.filter(id=bio.id).exists())


class LoginFormTest(BaseTestCase):
    def test_valid_with_email_and_password(self):
        form = LoginForm(data={'email': 'an@example.com', 'password': 'bi-mat'})
        self.assertTrue(form.is_valid())

    def test_empty_form_is_invalid(self):
        form = LoginForm(data={})
        self.assertFalse(form.is_valid())

    def test_rejects_malformed_email(self):
        """Ô email phải kiểm tra định dạng chuỗi nhập vào."""
        form = LoginForm(data={'email': 'khong-phai-email', 'password': 'bi-mat'})
        self.assertFalse(form.is_valid())


class UserRegistrationFormTest(BaseTestCase):
    def test_form_has_all_four_fields(self):
        """Form đăng ký phải khởi tạo được và có đủ username, email, image, password.

        (Hiện form là ModelForm nhưng thiếu class Meta nên khởi tạo là vỡ.)
        """
        form = UserRegistrationForm()
        for field in ['username', 'email', 'image', 'password']:
            self.assertIn(field, form.fields)


@override_settings(**TEST_SETTINGS)
class LoginViewTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user, self.bio = create_user_with_bio('an', 'mat-khau-manh-123')

    def test_open_login_page(self):
        """Mở trang đăng nhập (GET) phải nhận được trang, không phải lỗi."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_login_with_correct_password(self):
        """Đăng nhập đúng email + mật khẩu thì được chuyển sang trang check."""
        response = self.client.post(reverse('login'), {
            'email': 'an@example.com',
            'password': 'mat-khau-manh-123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('check'))

    def test_login_with_wrong_password(self):
        """Sai mật khẩu thì không được đăng nhập, bị đưa về trang chủ."""
        response = self.client.post(reverse('login'), {
            'email': 'an@example.com',
            'password': 'sai-be-bet',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        self.assertNotIn('_auth_user_id', self.client.session,
                         'Đăng nhập sai thì session không được chứa user')


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class LoginRateLimitTest(BaseTestCase):
    """Trang đăng nhập giới hạn 10 lần/phút cho mỗi địa chỉ IP."""

    def setUp(self):
        cache.clear()
        self.client = Client(raise_request_exception=False)

    def tearDown(self):
        cache.clear()

    def test_11th_attempt_is_blocked(self):
        data = {'email': 'ai-do@example.com', 'password': 'sai'}
        # Đóng băng đồng hồ của ratelimit để cả 11 request chắc chắn rơi
        # vào cùng một cửa sổ 1 phút (tránh chập chờn khi chạy vắt qua phút).
        with mock.patch('django_ratelimit.core.time.time', return_value=time.time()):
            for _ in range(10):
                self.client.post(reverse('login'), data)
            response = self.client.post(reverse('login'), data)
        self.assertEqual(response.status_code, 403)


@override_settings(**TEST_SETTINGS)
class SignupViewTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_signup_creates_new_account(self):
        """Đăng ký hợp lệ thì tạo User + Bio, đăng nhập luôn và chuyển trang."""
        response = self.client.post(reverse('signup'), {
            'username': 'binh',
            'email': 'binh@example.com',
            'password': 'mat-khau-manh-123',
            'image': sample_image(),
        })
        self.assertTrue(User.objects.filter(username='binh').exists(),
                        'Đăng ký xong phải có tài khoản trong hệ thống')
        self.assertTrue(Bio.objects.filter(user__username='binh').exists(),
                        'Đăng ký xong phải có Bio kèm avatar')
        self.assertEqual(response.status_code, 302)

    def test_duplicate_email_creates_no_account(self):
        """Đăng ký bằng email đã tồn tại thì không được tạo thêm tài khoản."""
        create_user_with_bio('an')
        users_before = User.objects.count()
        response = self.client.post(reverse('signup'), {
            'username': 'an-gia-mao',
            'email': 'an@example.com',
            'password': 'mat-khau-khac-456',
            'image': sample_image(),
        })
        self.assertEqual(User.objects.count(), users_before)
        self.assertLess(response.status_code, 500,
                        'Email trùng thì báo lỗi tử tế chứ không được sập server')


@override_settings(**TEST_SETTINGS)
class CheckViewTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('check'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_user_with_bio_goes_home(self):
        """Ai đã có Bio rồi thì trang check chỉ việc đưa họ về trang chủ."""
        user, _ = create_user_with_bio('an')
        self.client.force_login(user)
        response = self.client.get(reverse('check'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_user_without_bio_gets_one_created(self):
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


@override_settings(**TEST_SETTINGS)
class LogoutViewTest(BaseTestCase):
    def test_logout_redirects_home(self):
        """Đăng xuất xong thì session bị xóa và được đưa về trang chủ."""
        user, _ = create_user_with_bio('an')
        client = Client(raise_request_exception=False)
        client.force_login(user)
        response = client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')
        self.assertNotIn('_auth_user_id', client.session,
                         'Đăng xuất rồi thì session không được còn user')


@override_settings(**TEST_SETTINGS)
class FriendsTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')
        self.user2, self.bio2 = create_user_with_bio('binh')
        self.client.force_login(self.user1)

    def test_add_friend_works_both_ways(self):
        """An gửi kết bạn với Bình thì hai người thành bạn của nhau."""
        response = self.client.post(reverse('add_friend', args=[self.bio2.id]))
        self.assertIn(self.bio2, self.bio1.friends.all())
        self.assertIn(self.bio1, self.bio2.friends.all())
        self.assertEqual(response.status_code, 200)

    def test_add_friend_twice_fails(self):
        make_friends(self.bio1, self.bio2)
        response = self.client.post(reverse('add_friend', args=[self.bio2.id]))
        self.assertGreaterEqual(response.status_code, 400)

    def test_anonymous_cannot_add_friend(self):
        guest = Client(raise_request_exception=False)
        response = guest.post(reverse('add_friend', args=[self.bio2.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_unfriend_works_both_ways(self):
        """Đang là bạn mà hủy kết bạn thì cả hai phía đều hết là bạn."""
        make_friends(self.bio1, self.bio2)
        response = self.client.post(reverse('unfriend', args=[self.bio2.id]))
        self.assertNotIn(self.bio2, self.bio1.friends.all())
        self.assertNotIn(self.bio1, self.bio2.friends.all())
        self.assertEqual(response.status_code, 200)

    def test_unfriend_stranger_fails(self):
        response = self.client.post(reverse('unfriend', args=[self.bio2.id]))
        self.assertGreaterEqual(response.status_code, 400)

    def test_anonymous_cannot_unfriend(self):
        guest = Client(raise_request_exception=False)
        response = guest.post(reverse('unfriend', args=[self.bio2.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_view_friends_list(self):
        make_friends(self.bio1, self.bio2)
        response = self.client.get(reverse('friends_list'))
        self.assertEqual(response.status_code, 200)

    def test_view_friend_information(self):
        make_friends(self.bio1, self.bio2)
        response = self.client.get(reverse('friends_information', args=[self.bio2.id]))
        self.assertEqual(response.status_code, 200)


@override_settings(**TEST_SETTINGS)
class ProfileTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user, self.bio = create_user_with_bio('an')

    def test_view_own_profile(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('bio'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bio/information.html')

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('bio'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_update_profile_information(self):
        """Đổi username, email, mật khẩu, avatar thì thông tin mới phải được lưu."""
        self.client.force_login(self.user)
        self.client.post(reverse('bio_information_change'), {
            'username': 'an-moi',
            'email': 'an-moi@example.com',
            'password': 'mat-khau-moi-789',
            'file': sample_image('new-avatar.gif'),
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'an-moi')
        self.assertEqual(self.user.email, 'an-moi@example.com')
