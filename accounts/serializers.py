from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import CreditPlan, Payment, CreditTransaction

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already registered.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError('Passwords do not match.')
        return attrs


class SignInSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)


class ResetPasswordSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError('Passwords do not match.')
        return attrs


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_name', 'email', 'profile_picture', 'is_pro', 'credits_balance']
        read_only_fields = ['is_pro', 'credits_balance']


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8)
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError('Passwords do not match.')
        return attrs


class ProfilePictureSerializer(serializers.Serializer):
    profile_picture = serializers.ImageField()


class CreditPlanOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditPlan
        fields = [
            'id', 'name', 'price', 'credits', 'features', 'popular',
            'is_active', 'order', 'created_at', 'updated_at',
        ]


class CreditPlanInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditPlan
        fields = [
            'name', 'price', 'credits', 'features', 'popular',
            'is_active', 'order',
        ]


class CheckoutSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    provider = serializers.ChoiceField(choices=['stripe', 'test'], default='stripe')


class CheckoutOutputSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    client_secret = serializers.CharField(required=False, allow_blank=True)
    provider = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()


class ConfirmPaymentSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()


class PaymentOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'amount', 'currency', 'provider', 'provider_payment_id',
            'status', 'metadata', 'created_at', 'updated_at',
        ]


class CreditTransactionOutputSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    amount = serializers.SerializerMethodField()

    class Meta:
        model = CreditTransaction
        fields = [
            'id', 'user_id', 'user_name', 'user_email', 'credits',
            'type', 'description', 'balance_after', 'amount', 'created_at',
        ]

    def get_amount(self, obj):
        if obj.payment:
            return obj.payment.amount
        return None


class CreditTransactionAdminOutputSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    amount = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = CreditTransaction
        fields = [
            'id', 'user_id', 'user_name', 'user_email', 'credits',
            'type', 'description', 'balance_after', 'amount', 'status',
            'created_at',
        ]

    def get_amount(self, obj):
        if obj.payment:
            return obj.payment.amount
        return None

    def get_status(self, obj):
        if obj.payment:
            return obj.payment.status
        return 'success'
