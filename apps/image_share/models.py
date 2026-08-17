from django.db import models
from ..bio.models import Bio

# Create your models here.
class Image_type(models.Model):
    name = models.CharField(max_length=255)

class Image(models.Model):
    user = models.ForeignKey(Bio,on_delete=models.CASCADE,related_name='image_share_bio')
    image = models.ImageField(upload_to='/Locket/images')
    text = models.CharField(max_length=255)
    type_share = models.ForeignKey(Image_type,on_delete=models.CASCADE,related_name='image_share_type')
    shared_list = models.ManyToManyField(Bio,null=True,related_name='image_share_shared_list')

