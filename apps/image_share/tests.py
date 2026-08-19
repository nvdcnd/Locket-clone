"""Test cho app image_share: đăng ảnh, bảng tin, thả emoji, xóa ảnh.

Mỗi test mô tả một hành vi mà người dùng mong đợi.
Test nào fail nghĩa là code thật đang không làm đúng hành vi đó.
"""
import base64
import json

from django.test import Client, override_settings
from django.urls import reverse

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

    def _upload(self, text='ảnh hôm nay'):
        return self.client.post(
            reverse('image_create'),
            data=json.dumps({'image': IMAGE_BASE64, 'text': text}),
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

    def test_user_without_bio_cannot_upload(self):
        from django.contrib.auth.models import User
        new_user = User.objects.create_user('moi', 'moi@example.com', 'mat-khau-manh-123')
        self.client.force_login(new_user)
        response = self._upload()
        self.assertGreaterEqual(response.status_code, 400)
        self.assertEqual(Image.objects.count(), 0)

    def test_anonymous_is_redirected_to_login(self):
        response = self._upload()
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


@override_settings(**TEST_SETTINGS)
class ImageFeedTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')
        _, self.bio2 = create_user_with_bio('binh')
        make_friends(self.bio1, self.bio2)

    def test_feed_shows_own_and_friends_images(self):
        Image.objects.create(user=self.bio1, image=sample_image(), text='ảnh của an')
        Image.objects.create(user=self.bio2, image=sample_image(), text='ảnh của bình')
        self.client.force_login(self.user1)
        response = self.client.get(
            reverse('image_list_infinity_scroll', args=['2000-01-01', 10])
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('images', data)
        self.assertIn('has_next', data)


@override_settings(**TEST_SETTINGS)
class EmojiTest(BaseTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)
        self.user1, self.bio1 = create_user_with_bio('an')
        self.image = Image.objects.create(user=self.bio1, image=sample_image(), text='đi chơi')
        self.heart = Emoji_type.objects.create(emoji='❤️')
        self.client.force_login(self.user1)

    def test_react_to_image_succeeds(self):
        response = self.client.post(
            reverse('emojing_image', args=[self.image.id]),
            data=json.dumps({'emoji': '❤️'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Image_emoji_share.objects.filter(image=self.image, user=self.bio1, emoji=self.heart).exists(),
            'Lượt thả emoji phải được lưu lại',
        )

    def test_react_to_missing_image_fails(self):
        response = self.client.post(
            reverse('emojing_image', args=[999999]),
            data=json.dumps({'emoji': '❤️'}),
            content_type='application/json',
        )
        self.assertGreaterEqual(response.status_code, 400)


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
        self.assertGreaterEqual(response.status_code, 400)
