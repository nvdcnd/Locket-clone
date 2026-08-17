from django.db import models
from ..bio.models import Bio

# Create your models here.
class Image_type(models.Model):
    name = models.CharField(max_length=255)

class Emoji_type(models.Model):
    emoji = models.CharField(max_length=255)

class Image(models.Model):
    user = models.ForeignKey(Bio,on_delete=models.CASCADE,related_name='image_share_bio')
    image = models.ImageField(upload_to='/Locket/images')
    text = models.CharField(max_length=255)
    type_share = models.ForeignKey(Image_type,null=True,on_delete=models.CASCADE,related_name='image_share_type')
    shared_list = models.ManyToManyField(Bio,null=True,related_name='image_share_shared_list')
    create_at = models.DateTimeField(auto_now_add=True)

class Image_emoji_share(models.Model):
    user = models.ForeignKey(Bio,on_delete=models.CASCADE,related_name='image_emoji_share')
    image = models.ForeignKey(Image,on_delete=models.CASCADE,related_name='image_emoji_image')
    emoji = models.ForeignKey(Emoji_type,on_delete=models.CASCADE,related_name='image_emoji_emoji')
    create_at = models.DateTimeField(auto_now_add=True)
