from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from django.contrib.auth import authenticate
from .serializers import (
    RegisterSerializer, SignInSerializer, ForgotPasswordSerializer,
    VerifyOTPSerializer, ResetPasswordSerializer,
)
from .services import AuthService


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = AuthService()
            user = service.register(
                full_name=serializer.validated_data['full_name'],
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
            )
        except Exception as e:
            return Response(
                {'detail': 'Registration failed.', 'code': 'REGISTRATION_FAILED'},
                status=400,
            )

        return Response(
            {'data': {'user': service.get_tokens(user)['user']}, 'message': 'Registered. Please verify your email.'},
            status=201,
        )


class SignInView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
        )
        if not user:
            raise AuthenticationFailed('Invalid email or password.')

        try:
            service = AuthService()
            tokens = service.get_tokens(user)
        except Exception as e:
            return Response(
                {'detail': 'Sign in failed.', 'code': 'SIGNIN_FAILED'},
                status=500,
            )

        return Response({'data': tokens})


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = AuthService()
            code = service.generate_otp(serializer.validated_data['email'])
        except Exception as e:
            return Response(
                {'detail': 'Could not process request.', 'code': 'OTP_FAILED'},
                status=500,
            )

        return Response({'message': 'OTP sent to email.'})


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = AuthService()
            reset_token = service.verify_otp(
                serializer.validated_data['email'],
                serializer.validated_data['otp'],
            )
        except Exception as e:
            return Response(
                {'detail': 'OTP verification failed.', 'code': 'OTP_VERIFICATION_FAILED'},
                status=500,
            )

        if not reset_token:
            raise ValidationError('Invalid or expired OTP.')

        return Response({'data': {'reset_token': reset_token}, 'message': 'OTP verified.'})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = AuthService()
            success, message = service.reset_password(
                serializer.validated_data['reset_token'],
                serializer.validated_data['password'],
            )
        except Exception as e:
            return Response(
                {'detail': 'Password reset failed.', 'code': 'RESET_FAILED'},
                status=500,
            )

        if not success:
            raise ValidationError(message)

        return Response({'message': message})


class LogoutView(APIView):
    def post(self, request):
        refresh = request.data.get('refresh')
        if not refresh:
            raise ValidationError('Refresh token is required.')

        try:
            from rest_framework_simplejwt.tokens import RefreshToken
            token = RefreshToken(refresh)
            token.blacklist()
        except Exception as e:
            return Response(
                {'detail': 'Logout failed.', 'code': 'LOGOUT_FAILED'},
                status=400,
            )

        return Response({'message': 'Logged out.'})
