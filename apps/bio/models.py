from django.db import models
from django.contrib.auth.models import User
from apps.core.models import BaseModel

# Create your models here.
class Bio(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bio_user")
    avatar = models.ImageField(upload_to='Locket/avatar/',null=True)
    friends = models.ManyToManyField('self')


