from django.urls import path
from .profile_views import ProfileView, ChangePasswordView, ProfilePictureView

urlpatterns = [
    path('', ProfileView.as_view(), name='profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('picture/', ProfilePictureView.as_view(), name='profile-picture'),
]
