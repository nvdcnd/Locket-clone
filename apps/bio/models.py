from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Bio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bio_user")
    avatar = models.ImageField(upload_to='./Locket/avatar')
    friends = models.ManyToManyField(User, related_name='bio_friends',null=True)

