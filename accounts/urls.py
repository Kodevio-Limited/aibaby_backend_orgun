from django.urls import path
from .views import (
    RegisterView, SignInView, ForgotPasswordView,
    VerifyOTPView, ResetPasswordView, LogoutView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('sign-in/', SignInView.as_view(), name='sign-in'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
