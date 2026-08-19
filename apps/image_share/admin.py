from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Image)
admin.site.register(Image_type)
admin.site.register(Emoji_type)
admin.site.register(Image_emoji_share)