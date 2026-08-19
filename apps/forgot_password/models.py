from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Forgot_password_request(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_forgot_password")
    code = models.TextField()
    expire = models.DateTimeField()
    status = models.CharField(max_length=255)
