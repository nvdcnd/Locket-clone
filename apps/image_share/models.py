from django.db import models
from apps.bio.models import Bio
from apps.core.models import BaseModel

# Create your models here.
class Image_type(BaseModel):
    name = models.CharField(max_length=255)

class Emoji_type(BaseModel):
    emoji = models.CharField(max_length=255)

class Image(BaseModel):
    user = models.ForeignKey(Bio,on_delete=models.CASCADE,related_name='image_share_bio')
    image = models.ImageField(upload_to='Locket/images/')
    text = models.CharField(max_length=255)
    type_share = models.ForeignKey(Image_type,null=True,on_delete=models.CASCADE,related_name='image_share_type')
    shared_list = models.ManyToManyField(Bio)
    create_at = models.DateTimeField(auto_now_add=True)

class Image_emoji_share(BaseModel):
    user = models.ForeignKey(Bio,on_delete=models.CASCADE,related_name='image_emoji_share')
    image = models.ForeignKey(Image,on_delete=models.CASCADE,related_name='image_emoji_image')
    emoji = models.ForeignKey(Emoji_type,on_delete=models.CASCADE,related_name='image_emoji_emoji')
    create_at = models.DateTimeField(auto_now_add=True)
