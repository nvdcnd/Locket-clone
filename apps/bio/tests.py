from django.test import TestCase, Client, override_settings
from .models import Bio
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from .forms import *
import io
from PIL import Image
import tempfile
import shutil

# Create your tests here.


TEMP = tempfile.mkdtemp()


class TestModels(TestCase):
    def setUp(self):
        self.client = CLient()
        self.user = User.objects.create_user(username="Hello",email='example@exp.com',password="hello")

    def test_registing_new_bio(self):
        self.bio = Bio.objects.create(user=self.user)
        self.assertTrue(isinstance(self.bio,Bio))

class CheckViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('check')

        self.user = User.objects.create_user(username="Hello",email='example@exp.com',password="hello")
        self.client.login = login(username="Hello",password="hello")

        self.redirect_url = reverse('core:index')

    def test_check_non_bio_user(self):
        response = self.client.get(self.url)
        
        bio = Bio.objects.get(user=user)

        self.assertTrue(isinstance(bio,Bio))
        self.assertRedirects(response, self.redirect_url)

    def test_check_bio_user(self):
        response = self.client.get(self.url)
        
        #bio = Bio.objects.get(user=user)

        #self.assertTrue(isinstance(bio,Bio))
        self.assertRedirects(response, self.redirect_url)

    def test_check_un_loged_in(self):
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

class UnFriendTest(TestCase):
    def setUp(self):
        self.url = reversr('unfriend')

        self.user1 = User.objects.create_user(username="Hello",email='example@exp.com',password="hello")
        self.bio1 = Bio.objects.create(user=self.user1)

        self.user2 = User.objects.create_user(username="Hello1",email='example@exp.com',password="hello1")
        self.bio2 = Bio.objects.create(user=self.user2)

        self.client.login = login(username="Hello",password="hello")

        #self.redirect_url = reverse('core:index')
        
    def test_unfriend(self):
        self.bio1.friends.add(self.bio2)
        self.bio1.save()

        res = self.client.get(self.url)

        check = self.bio1.friends.get(self.bio2)
        check2 = self.bio2.friends.get(self.bio1)

        self.assertFalse(isinstance(check,self.bio1.friends))
        self.assertFalse(isinstance(check2,self.bio2.friends))
        self.assertEqual(response.status_code, 200)

    def test_un_friend_un_loged_in(self):
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_un_friend_no_bio(self):
        self.client.logout()
        self.bio.get(user=self.user1).delete()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 500)

class AddFriendTest(TestCase):
    def setUp(self):
        self.url = reversr('unfriend')

        self.user1 = User.objects.create_user(username="Hello",email='example@exp.com',password="hello")
        self.bio1 = Bio.objects.create(user=self.user1)

        self.user2 = User.objects.create_user(username="Hello1",email='example@exp.com',password="hello1")
        self.bio2 = Bio.objects.create(user=self.user2)

        self.client.login = login(username="Hello",password="hello")

        #self.redirect_url = reverse('core:index')
        
    def test_add_friend_addfriend(self):
        #self.bio1.friends.add(self.bio2)
        #self.bio1.save()

        res = self.client.get(self.url)

        check = self.bio1.friends.get(self.bio2)
        check2 = self.bio2.friends.get(self.bio1)

        self.assertTrue(isinstance(check,self.bio1.friends))
        self.assertTrue(isinstance(check2,self.bio2.friends))
        self.assertEqual(response.status_code, 200)

    def test_add_friend_un_loged_in(self):
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

    def test_add_friend_no_bio(self):
        self.client.logout()
        self.bio.get(user=self.user1).delete()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 500)

class BioView(TestCase):
    def setUp(self):
        self.clinet = Client()

        self.url = reverse('bio')

        self.user = User.objects.create_user(username="Hello",email='example@exp.com',password="hello")
        self.client.login = login(username="Hello",password="hello")

        self.bio = Bio.objects.create(user=self.user)
    
    def test_bio_loged_in(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bio/information.html')

    def test_bio_not_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

class FriendView(TestCase):
    def setUp(self):
        self.clinet = Client()

        self.url = reverse('friend_information')

        self.user1 = User.objects.create_user(username="Hello",email='example@exp.com',password="hello")
        self.bio1 = Bio.objects.create(user=self.user1)

        self.user2 = User.objects.create_user(username="Hello1",email='example@exp.com',password="hello1")
        self.bio2 = Bio.objects.create(user=self.user2)

        self.bio1.friends.add(self.bio2)
        self.bio1.save()

        self.client.login = login(username="Hello",password="hello")
    
    def test_driend_information_loged_in(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bio/information.html')

    def test_friend_information_not_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

class LogoutTest(TestCase):
    def setUp(self):
        self.clinet = Client()

        self.url = reverse('logout')
        self.redirect_url = reverse('core:index')

        self.user = User.objects.create_user(username="Hello",email='example@exp.com',password="hello")
        self.client.login = login(username="Hello",password="hello")

        self.bio = Bio.objects.create(user=self.user)

    def test_user_logout(self):
        response = self.client.get(self.url)
        self.assertRedirects(response,self.redirect_url)
        self.assertNotIn('_auth_user_id',self.client.sessions)

    def test_logout_not_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)

@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class TestSignUpForm(TestCase):
    
    @classmethod
    def tearDownClass(self):
        super().tearDownClass()
        shutil.rmtree()

    def create_test_image():
        file_obj = io.BytesIO()
        image = Image.new('RGB',(100,100),color='blue')
        image.save(file_obj,'png')
        file_obj.seek(0)

        return SimpleUploadedFile(
            name='hello.png',content=file_obj.read(),content_type='image/png'
        )

    def create_fake_image():
        return SimpleUploadedFile(
            name='hello.exe',content='rickroll',content_type='application/x-msdownload'
        )

    def test_registation_form(self):
        self.img = self.create_test_image()
        form = UserRegistrationForm(data={
            'username':'Hello',
            'email':'ex@example.com',
            'password':'hello'
        }, files={'image':self.img})
        self.assertTrue(form.is_valid())

    def test_registation__invalid_form(self):
        self.img = self.create_fake_image()
        form = UserRegistrationForm(data={
            'username':'Hello',
            'email':'ex@example.com',
            'password':'hello'
        }, files={'image':self.img})
        self.assertFalse(form.is_valid())
        self.asertIn('image', forms.errors)

class TestLoginForm(TestCase):
    def test_form(self):
        form = LoginForm(data={
            'email':'ex@example.com',
            'password':'hello'
        })
        self.assertTrue(form.is_valid())


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class TestSignUpView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('signup')
    
    @classmethod
    def tearDownClass(self):
        super().tearDownClass()
        shutil.rmtree()

    def create_test_image():
        file_obj = io.BytesIO()
        image = Image.new('RGB',(100,100),color='blue')
        image.save(file_obj,'png')
        file_obj.seek(0)

        return SimpleUploadedFile(
            name='hello.png',content=file_obj.read(),content_type='image/png'
        )


    def create_fake_image():
        return SimpleUploadedFile(
            name='hello.exe',content='rickroll',content_type='application/x-msdownload'
        )

    def test_registation_view_form(self):
        self.img = self.create_test_image()

        response = self.client.post(self.url, data={
            'username':'Hello',
            'email':'ex@example.com',
            'password':'hello'
            'image':self.img
        })

        self.assertRedirects(response, reverse("check"))
        self.assertTrue(User.objects.filter(email=ex@example.com).exist())
        self.assertTrue(Bio.objects.filter(user=User.objects.filter(email=ex@example.com).first()).exist())


    def test_registation_view_invalid_form(self):
        self.img = self.create_fake_image()

        response = self.client.post(self.url, data={
            'username':'Hello',
            'email':'rickroll',
            'password':'hello'
            'image':self.img
        })

        form = response.context['form']

        self.assertRedirects(response, reverse("core:index"))
        self.assertTrue(form.error)
        #self.asertIn('')

@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class TestChangeInformationView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('bio_information_change')

        self.user = User.objects.create_user(username="Hello",email='example@exp.com',password="hello")
        self.client.login = login(username="Hello",password="hello")
    
    @classmethod
    def tearDownClass(self):
        super().tearDownClass()
        shutil.rmtree()

    def create_test_image():
        file_obj = io.BytesIO()
        image = Image.new('RGB',(100,100),color='blue')
        image.save(file_obj,'png')
        file_obj.seek(0)

        return SimpleUploadedFile(
            name='hello.png',content=file_obj.read(),content_type='image/png'
        )


    def create_fake_image():
        return SimpleUploadedFile(
            name='hello.exe',content='rickroll',content_type='application/x-msdownload'
        )

    def test_change_form(self):
        self.img = self.create_test_image()
        self.old_infomation = User.objects.filter(email=ex@example.com).first()

        response = self.client.post(self.url, data={
            'username':'Hello1',
            'email':'ex@examplee.com',
            'password':'hello2'
            'image':self.img
        })
        
        self.new_information = User.objects.filter(email=ex@example.com).first()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(seld.old_infomation.username == self.new_information.username)
        self.assertFalse(seld.old_infomation.email == self.new_information.email)
