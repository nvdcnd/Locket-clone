from django.test import TestCase, Client
from .models import Bio
from django.contrib.auth.models import User
from django.urls import reverse

# Create your tests here.
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