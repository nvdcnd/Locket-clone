from django.db import models

from apps.bio.models import Bio
from apps.core.models import BaseModel
from apps.image_share.models import Image


class ChatRoom(BaseModel):
    user1 = models.ForeignKey(Bio, on_delete=models.CASCADE, related_name='rooms_as_user1')
    user2 = models.ForeignKey(Bio, on_delete=models.CASCADE, related_name='rooms_as_user2')

    # Mốc thời gian "đã đọc tới đâu" của từng người. Dùng thời gian vì id tin nhắn là UUID
    # (ngẫu nhiên, không có thứ tự) nên không so sánh "lớn hơn / nhỏ hơn" được.
    user1_last_read_at = models.DateTimeField(null=True, blank=True)
    user2_last_read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Sắp xếp danh sách đoạn chat mới nhất lên đầu

    class Meta:
        # 2 người không thể có 2 phòng chat; save() đã chuẩn hoá thứ tự nên chặn được cả chiều ngược.
        unique_together = ('user1', 'user2')

    def save(self, *args, **kwargs):
        # Luôn xếp bio có id nhỏ hơn làm user1, nhờ đó phòng (A,B) và (B,A) là một.
        if self.user1_id and self.user2_id and self.user1_id > self.user2_id:
            self.user1, self.user2 = self.user2, self.user1
            self.user1_last_read_at, self.user2_last_read_at = (
                self.user2_last_read_at, self.user1_last_read_at,
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f'ChatRoom {self.user1_id} <-> {self.user2_id}'


class Messages(BaseModel):
    chatroom = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages_at_chat_room')
    sender = models.ForeignKey(Bio, on_delete=models.CASCADE, related_name='messages_sender')
    message = models.TextField()
    image_reply = models.ForeignKey(Image, on_delete=models.CASCADE, null=True, blank=True,
                                    related_name='image_message_reply')
    message_reply = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                                      related_name='message_message_reply')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['chatroom', '-created_at'], name='chat_msg_room_created_idx')]

    def __str__(self):
        return f'{self.sender_id}: {self.message[:30]}'
