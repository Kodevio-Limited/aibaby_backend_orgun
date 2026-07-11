import random
import string
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from .models import OTP

User = get_user_model()


class AuthService:
    def __init__(self, user=None):
        self.user = user

    def register(self, full_name, email, password):
        user = User.objects.create_user(
            full_name=full_name,
            email=email,
            password=password,
            is_verified=False,
        )
        return user

    def get_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': ProfileService(user=user).get_profile_data(),
        }

    def generate_otp(self, email):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None
        code = ''.join(random.choices(string.digits, k=6))
        OTP.objects.create(
            user=user,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        return code

    def verify_otp(self, email, code):
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None
        otp = OTP.objects.filter(
            user=user, code=code, is_used=False, expires_at__gt=timezone.now()
        ).first()
        if not otp:
            return None
        otp.is_used = True
        otp.save(update_fields=['is_used'])
        refresh = RefreshToken()
        refresh['otp_verified'] = True
        refresh['user_id'] = str(user.id)
        return str(refresh.access_token)

    def reset_password(self, reset_token, password):
        from rest_framework_simplejwt.tokens import AccessToken
        try:
            token = AccessToken(reset_token)
            if not token.get('otp_verified'):
                return False, 'Invalid reset token.'
            user = User.objects.get(id=token['user_id'])
            user.set_password(password)
            user.save(update_fields=['password'])
            return True, 'Password updated.'
        except Exception:
            return False, 'Invalid or expired reset token.'


class ProfileService:
    def __init__(self, user):
        self.user = user

    def get_profile_data(self):
        return {
            'id': str(self.user.id),
            'full_name': self.user.full_name,
            'email': self.user.email,
            'is_pro': self.user.is_pro,
            'profile_picture': self.user.profile_picture.url if self.user.profile_picture else None,
        }

    def update_profile(self, data):
        for field in ['full_name', 'email']:
            if field in data:
                setattr(self.user, field, data[field])
        self.user.save(update_fields=['full_name', 'email'])
        return self.user

    def change_password(self, current_password, new_password):
        if not self.user.check_password(current_password):
            return False, 'Current password is incorrect.'
        self.user.set_password(new_password)
        self.user.save(update_fields=['password'])
        return True, 'Password updated.'

    def update_picture(self, picture):
        self.user.profile_picture = picture
        self.user.save(update_fields=['profile_picture'])
        return self.user
