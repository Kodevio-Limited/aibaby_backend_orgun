import logging

from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from core.responses import error_response, success_response
from .serializers import ProfileSerializer, ChangePasswordSerializer, ProfilePictureSerializer
from .services import ProfileService


logger = logging.getLogger(__name__)


class ProfileView(APIView):
    def get(self, request):
        try:
            service = ProfileService(user=request.user)
        except Exception:
            logger.exception('Could not load profile for user_id=%s', request.user.id)
            return error_response('Could not load profile.', code='PROFILE_LOAD_FAILED', status=500)
        return success_response(service.get_profile_data(), code='PROFILE_LOADED')

    def patch(self, request):
        serializer = ProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            service = ProfileService(user=request.user)
            service.update_profile(serializer.validated_data)
        except Exception:
            logger.exception('Could not update profile for user_id=%s', request.user.id)
            return error_response('Could not update profile.', code='PROFILE_UPDATE_FAILED', status=500)

        return success_response(service.get_profile_data(), code='PROFILE_UPDATED')


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = ProfileService(user=request.user)
            success, message = service.change_password(
                serializer.validated_data['current_password'],
                serializer.validated_data['new_password'],
            )
        except Exception:
            logger.exception('Could not change password for user_id=%s', request.user.id)
            return error_response('Could not change password.', code='PASSWORD_CHANGE_FAILED', status=500)

        if not success:
            raise ValidationError(message)

        return success_response(message=message, code='PASSWORD_CHANGED')


class ProfilePictureView(APIView):
    def patch(self, request):
        serializer = ProfilePictureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = ProfileService(user=request.user)
            service.update_picture(serializer.validated_data['profile_picture'])
        except Exception:
            logger.exception('Could not update profile picture for user_id=%s', request.user.id)
            return error_response('Could not update picture.', code='PICTURE_UPDATE_FAILED', status=500)

        return success_response(ProfileService(user=request.user).get_profile_data(), code='PICTURE_UPDATED')
