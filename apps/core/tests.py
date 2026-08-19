from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from apps.bio.models import Bio

# Create your tests here.
class HealthURLTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('health')

    def test_check(self):
        check = self.client.get(self.url)
        self.assertEqual(check.status_code, 200)


class IndexViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('index')

        self.user = User.objects.create_user(username="Hello",email='example@exp.com',password="hello")
        self.bio = Bio.objects.create(user=self.user)

        self.client.login = login(username="Hello",password="hello")

    def test_loged_in_view(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'images/index.html')

    def test_unloged_in_view(self):
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')