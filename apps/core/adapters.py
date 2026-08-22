from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User


class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """Tự nối tài khoản Google vào tài khoản local có cùng email.

        Chỉ nối khi provider xác nhận email ĐÃ được verify. Nếu nối theo email chưa
        verify, kẻ xấu tạo tài khoản Google với email của nạn nhân là chiếm được
        tài khoản local của nạn nhân (account takeover).
        """
        if sociallogin.is_existing:
            return

        verified_emails = [
            address.email for address in sociallogin.email_addresses
            if address.verified and address.email
        ]
        for email in verified_emails:
            user = User.objects.filter(email__iexact=email).order_by('id').first()
            if user:
                sociallogin.connect(request, user)
                return
