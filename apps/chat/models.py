from django.db import models
from ..bio.models import Bio
from ..image_share.models import Image

# Create your models here.
class ChatRoom(models.Model):
    user1 = models.ForeignKey(Bio, on_delete=models.CASCADE, related_name='rooms_as_user1')
    user2 = models.ForeignKey(Bio, on_delete=models.CASCADE, related_name='rooms_as_user2')
    
    # Phục vụ trạng thái Seen độc lập cho từng người
    user1_last_read_msg_id = models.BigIntegerField(default=0)
    user2_last_read_msg_id = models.BigIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True) # Dùng để sắp xếp danh sách đoạn chat mới nhất lên đầu

    class Meta:
        # Ràng buộc để 2 người không thể tạo 2 phòng chat trùng nhau
        unique_together = ('user1', 'user2')

class Messages(models.Model):
    chatroom = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages_at_chat_room')
    sender = models.ForeignKey(Bio, on_delete=models.CASCADE, related_name="messages_sender")
    message = models.TextField()
    image_reply = models.ForeignKey(Image, on_delete=models.CASCADE, null=True, related_name="image_message_reply")
    message_reply = models.ForeignKey('self', on_delete=models.CASCADE, null=True, related_name="message_reply")
    created_at = models.DateTimeField(auto_now_add=True)