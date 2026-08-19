from django.urls import path
from .views import forgot_password, forgot_password_verify, change_password

urlpatterns = [
    path('', forgot_password, name='forgot_password'),
    path('verify/<int:id>', forgot_password_verify, name='forgot_password_verify'),
    path('change/<int:id>', change_password, name='change_password'),
]
