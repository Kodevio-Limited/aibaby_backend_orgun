from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .serializers import ProfileSerializer, ChangePasswordSerializer, ProfilePictureSerializer
from .services import ProfileService


class ProfileView(APIView):
    def get(self, request):
        try:
            service = ProfileService(user=request.user)
        except Exception as e:
            return Response(
                {'detail': 'Could not load profile.', 'code': 'PROFILE_LOAD_FAILED'},
                status=500,
            )
        return Response({'data': service.get_profile_data()})

    def patch(self, request):
        serializer = ProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            service = ProfileService(user=request.user)
            user = service.update_profile(serializer.validated_data)
        except Exception as e:
            return Response(
                {'detail': 'Could not update profile.', 'code': 'PROFILE_UPDATE_FAILED'},
                status=500,
            )

        return Response({'data': service.get_profile_data()})


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
        except Exception as e:
            return Response(
                {'detail': 'Could not change password.', 'code': 'PASSWORD_CHANGE_FAILED'},
                status=500,
            )

        if not success:
            raise ValidationError(message)

        return Response({'message': message})


class ProfilePictureView(APIView):
    def patch(self, request):
        serializer = ProfilePictureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = ProfileService(user=request.user)
            service.update_picture(serializer.validated_data['profile_picture'])
        except Exception as e:
            return Response(
                {'detail': 'Could not update picture.', 'code': 'PICTURE_UPDATE_FAILED'},
                status=500,
            )

        return Response({'data': ProfileService(user=request.user).get_profile_data()})
