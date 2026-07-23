import logging

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from django.contrib.auth import authenticate
from core.responses import error_response, success_response
from .serializers import (
    RegisterSerializer, SignInSerializer, ForgotPasswordSerializer,
    VerifyOTPSerializer, ResetPasswordSerializer,
)
from .services import AuthService


logger = logging.getLogger(__name__)


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
        except Exception:
            logger.exception('Registration failed for email=%s', serializer.validated_data['email'])
            return error_response('Registration failed.', code='REGISTRATION_FAILED', status=400)

        return success_response(
            {'user': service.get_tokens(user)['user']},
            message='Registered. Please verify your email.',
            code='REGISTERED',
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
        except Exception:
            logger.exception('Sign in failed for email=%s', serializer.validated_data['email'])
            return error_response('Sign in failed.', code='SIGNIN_FAILED', status=500)

        return success_response(tokens, code='SIGNED_IN')


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            service = AuthService()
            service.generate_otp(serializer.validated_data['email'])
        except Exception:
            logger.exception('OTP generation failed for email=%s', serializer.validated_data['email'])
            return error_response('Could not process request.', code='OTP_FAILED', status=500)

        return success_response(message='OTP sent to email.', code='OTP_SENT')


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
        except Exception:
            logger.exception('OTP verification failed for email=%s', serializer.validated_data['email'])
            return error_response('OTP verification failed.', code='OTP_VERIFICATION_FAILED', status=500)

        if not reset_token:
            raise ValidationError('Invalid or expired OTP.')

        return success_response({'reset_token': reset_token}, message='OTP verified.', code='OTP_VERIFIED')


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
        except Exception:
            logger.exception('Password reset failed for reset_token=%s', serializer.validated_data['reset_token'])
            return error_response('Password reset failed.', code='RESET_FAILED', status=500)

        if not success:
            raise ValidationError(message)

        return success_response(message=message, code='PASSWORD_RESET')


class LogoutView(APIView):
    def post(self, request):
        refresh = request.data.get('refresh')
        if not refresh:
            raise ValidationError('Refresh token is required.')

        try:
            from rest_framework_simplejwt.tokens import RefreshToken
            token = RefreshToken(refresh)
            token.blacklist()
        except Exception:
            logger.exception('Logout failed')
            return error_response('Logout failed.', code='LOGOUT_FAILED', status=400)

        return success_response(message='Logged out.', code='LOGGED_OUT')
