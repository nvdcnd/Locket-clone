"""Test cho app image_share: đăng ảnh, bảng tin, thả emoji, xóa ảnh.

Mỗi test mô tả một hành vi mà người dùng mong đợi.
Test nào fail nghĩa là code thật đang không làm đúng hành vi đó.
"""
import base64
import json
import uuid

from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.test_helpers import (
    TEST_SETTINGS, TINY_GIF, BaseTestCase,
    create_user_with_bio, make_friends, sample_image,
)

from apps.image_share.models import Emoji_type, Image, Image_emoji_share, Image_type

# Chuỗi base64 đúng dạng mà trình duyệt gửi lên khi đăng ảnh.
IMAGE_BASE64 = 'data:image/gif;base64,' + base64.b64encode(TINY_GIF).decode()


@override_settings(**TEST_SETTINGS)
class ImageModelTest(BaseTestCase):
    def setUp(self):
        _, self.bio1 = create_user_with_bio('an')

    def test_create_image_with_type_and_share_list(self):
        share_type = Image_type.objects.create(name='ban-be')
        _, bio2 = create_user_with_bio('binh')
        image = Image.objects.create(
            user=self.bio1, image=sample_image(), text='đi chơi', type_share=share_type,
        )
        image.shared_list.add(bio2)
        self.assertEqual(image.type_share, share_type)
        self.assertIn(bio2, image.shared_list.all())

    def test_react_with_emoji(self):
        image = Image.objects.create(user=self.bio1, image=sample_image(), text='đi chơi')
        heart = Emoji_type.objects.create(emoji='❤️')
        reaction = Image_emoji_share.objects.create(user=self.bio1, image=image, emoji=heart)
        self.assertEqual(reaction.emoji, heart)

    def test_deleting_owner_deletes_images(self):
        Image.objects.create(user=self.bio1, image=sample_image(), text='đi chơi')
        self.bio1.delete()
        self.assertEqual(Image.objects.count(), 0)


@override_settings(**TEST_SETTINGS)
class ImageCreateTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user, self.bio = create_user_with_bio('an')

    def _upload(self, text='ảnh hôm nay', image=IMAGE_BASE64):
        return self.client.post(
            reverse('image_create'),
            data=json.dumps({'image': image, 'text': text}),
            content_type='application/json',
        )

    def test_upload_image_succeeds(self):
        """Đăng ảnh base64 hợp lệ thì ảnh được lưu cho đúng chủ."""
        self.client.force_login(self.user)
        response = self._upload('ảnh hôm nay')
        self.assertEqual(response.status_code, 200)
        image = Image.objects.filter(text='ảnh hôm nay').first()
        self.assertIsNotNone(image, 'Ảnh phải được lưu vào hệ thống')
        self.assertEqual(image.user, self.bio)
        self.assertTrue(image.image.name.endswith('.gif'))

    def test_user_without_bio_cannot_upload(self):
        from django.contrib.auth.models import User
        new_user = User.objects.create_user('moi', 'moi@example.com', 'mat-khau-manh-123')
        self.client.force_login(new_user)
        response = self._upload()
        self.assertGreaterEqual(response.status_code, 400)
        self.assertEqual(Image.objects.count(), 0)

    def test_non_image_payload_is_rejected(self):
        """Chuỗi base64 không phải ảnh (hoặc không phải base64) -> 400, không lưu, không 500."""
        self.client.force_login(self.user)
        fake = 'data:image/png;base64,' + base64.b64encode(b'khong phai anh dau').decode()
        self.assertEqual(self._upload(image=fake).status_code, 400)
        self.assertEqual(self._upload(image='khong-co-base64').status_code, 400)
        self.assertEqual(self._upload(image=None).status_code, 400)
        self.assertEqual(Image.objects.count(), 0)

    def test_invalid_json_is_400(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('image_create'), data='{{', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_get_is_not_allowed(self):
        """GET vào /image/create trước đây trả None (500); giờ phải là 405."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('image_create'))
        self.assertEqual(response.status_code, 405)

    def test_anonymous_is_redirected_to_login(self):
        response = self._upload()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))


@override_settings(**TEST_SETTINGS)
class ImageFeedTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')
        _, self.bio2 = create_user_with_bio('binh')
        _, self.stranger = create_user_with_bio('la')
        make_friends(self.bio1, self.bio2)
        self.client.force_login(self.user1)

    def _fetch(self, last_page, offset=10):
        return self.client.get(reverse('image_list_infinity_scroll', args=[last_page, offset]))

    def test_feed_shows_own_and_friends_images_only(self):
        Image.objects.create(user=self.bio1, image=sample_image(), text='ảnh của an')
        Image.objects.create(user=self.bio2, image=sample_image(), text='ảnh của bình')
        Image.objects.create(user=self.stranger, image=sample_image(), text='ảnh người lạ')

        response = self._fetch(timezone.now().isoformat())
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual({i['text'] for i in data['images']}, {'ảnh của an', 'ảnh của bình'})
        self.assertFalse(data['has_next'])
        first = data['images'][0]
        for key in ('id', 'image_url', 'creater', 'creater_user_id', 'creater_name', 'create_at'):
            self.assertIn(key, first)

    def test_feed_url_accepts_integer_offset(self):
        """Trước đây url khai <uuid:offset> nên /image/fetch/<ts>/10 là 404."""
        response = self.client.get('/image/fetch/2030-01-01T00:00:00+00:00/10')
        self.assertEqual(response.status_code, 200)

    def test_feed_paginates_with_cursor(self):
        for i in range(12):
            Image.objects.create(user=self.bio1, image=sample_image(), text=f'ảnh {i}')
        data = json.loads(self._fetch(timezone.now().isoformat()).content)
        self.assertEqual(len(data['images']), 10)
        self.assertTrue(data['has_next'])
        data2 = json.loads(self._fetch(data['last_page']).content)
        self.assertEqual(len(data2['images']), 2)
        self.assertFalse(data2['has_next'])
        seen = {i['id'] for i in data['images']} | {i['id'] for i in data2['images']}
        self.assertEqual(len(seen), 12, 'Không được trùng/sót ảnh giữa hai trang')

    def test_invalid_cursor_is_400(self):
        response = self._fetch('khong-phai-ngay')
        self.assertEqual(response.status_code, 400)

    def test_date_only_cursor_is_accepted(self):
        response = self._fetch('2000-01-01')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['images'], [])

    def test_home_feed_page_renders(self):
        Image.objects.create(user=self.bio2, image=sample_image(), text='ảnh của bình')
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ảnh của bình')
        self.assertContains(response, f'data-receiver="{self.bio2.id}"')


@override_settings(**TEST_SETTINGS)
class EmojiTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')
        self.image = Image.objects.create(user=self.bio1, image=sample_image(), text='đi chơi')
        self.heart = Emoji_type.objects.create(emoji='❤️')
        self.client.force_login(self.user1)

    def _react(self, image_id, emoji='❤️'):
        return self.client.post(
            reverse('emojing_image', args=[image_id]),
            data=json.dumps({'emoji': emoji}),
            content_type='application/json',
        )

    def test_react_to_image_succeeds(self):
        response = self._react(self.image.id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Image_emoji_share.objects.filter(image=self.image, user=self.bio1, emoji=self.heart).exists(),
            'Lượt thả emoji phải được lưu lại',
        )

    def test_unknown_emoji_is_created_on_the_fly(self):
        """UI gửi 💛🔥😂😮😭 mà bảng Emoji_type chưa có -> trước đây DoesNotExist 500."""
        response = self._react(self.image.id, '🔥')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Emoji_type.objects.filter(emoji='🔥').exists())

    def test_react_to_missing_image_fails(self):
        response = self._react(uuid.uuid4())
        self.assertEqual(response.status_code, 404)

    def test_cannot_react_to_strangers_image(self):
        _, stranger = create_user_with_bio('la')
        image = Image.objects.create(user=stranger, image=sample_image(), text='riêng')
        response = self._react(image.id)
        self.assertEqual(response.status_code, 404)

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse('emojing_image', args=[self.image.id]))
        self.assertEqual(response.status_code, 405)


@override_settings(**TEST_SETTINGS)
class ImageDeleteTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')
        self.user2, self.bio2 = create_user_with_bio('binh')
        self.own_image = Image.objects.create(user=self.bio1, image=sample_image(), text='của an')
        self.client.force_login(self.user1)

    def test_own_image_is_removed(self):
        self.client.post(reverse('image_delete', args=[self.own_image.id]))
        self.assertFalse(Image.objects.filter(id=self.own_image.id).exists())

    def test_delete_returns_success(self):
        response = self.client.post(reverse('image_delete', args=[self.own_image.id]))
        self.assertEqual(response.status_code, 200)

    def test_cannot_delete_others_image(self):
        others_image = Image.objects.create(user=self.bio2, image=sample_image(), text='của bình')
        response = self.client.post(reverse('image_delete', args=[others_image.id]))
        self.assertTrue(Image.objects.filter(id=others_image.id).exists(),
                        'Ảnh của người khác phải còn nguyên')
        self.assertEqual(response.status_code, 404)

    def test_delete_via_get_is_rejected(self):
        """<img src="/image/delete/<id>"> trên trang lạ không được xoá ảnh (CSRF qua GET)."""
        response = self.client.get(reverse('image_delete', args=[self.own_image.id]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Image.objects.filter(id=self.own_image.id).exists())
