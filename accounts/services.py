import random
import string
import logging
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from .models import OTP

User = get_user_model()
logger = logging.getLogger(__name__)


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

    def get_tokens(self, user, request=None):
        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': ProfileService(user=user).get_profile_data(request),
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

        # Local/dev visibility only. Never log OTP in production.
        if settings.DEBUG:
            logger.info('DEV OTP for %s: %s', email, code)

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

    def get_profile_data(self, request=None):
        picture_url = None
        if self.user.profile_picture:
            picture_url = self.user.profile_picture.url
            if request is not None:
                picture_url = request.build_absolute_uri(picture_url)
        return {
            'id': str(self.user.id),
            'full_name': self.user.full_name,
            'email': self.user.email,
            'is_pro': self.user.is_pro,
            'credits_balance': self.user.credits_balance,
            'profile_picture': picture_url,
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


class PaymentService:
    def __init__(self, user):
        self.user = user

    def list_active_credit_plans(self):
        from .models import CreditPlan
        return CreditPlan.objects.filter(is_active=True)

    def get_credit_plan(self, plan_id):
        from .models import CreditPlan
        return CreditPlan.objects.get(id=plan_id, is_active=True)

    def _get_stripe_client(self):
        import stripe
        if not getattr(settings, 'STRIPE_SECRET_KEY', None):
            return None
        stripe.api_key = settings.STRIPE_SECRET_KEY
        return stripe

    def create_checkout(self, plan_id, provider='stripe'):
        from .models import CreditPlan, Payment
        from django.db import transaction
        plan = self.get_credit_plan(plan_id)
        with transaction.atomic():
            payment = Payment.objects.create(
                user=self.user,
                amount=plan.price,
                currency='USD',
                provider=provider,
                status='pending',
                metadata={'plan_id': str(plan.id), 'credits': plan.credits},
            )
        stripe = self._get_stripe_client() if provider == 'stripe' else None
        if stripe:
            intent = stripe.PaymentIntent.create(
                amount=int(plan.price * 100),
                currency='usd',
                metadata={'payment_id': str(payment.id), 'plan_id': str(plan.id)},
                automatic_payment_methods={'enabled': True},
            )
            payment.provider_payment_id = intent.id
            payment.provider_client_secret = intent.client_secret
            payment.save(update_fields=['provider_payment_id', 'provider_client_secret'])
            return payment, {'client_secret': intent.client_secret}
        return payment, {'payment_id': str(payment.id)}

    def confirm_payment(self, payment_id):
        from .models import CreditPlan, Payment
        from django.db import transaction
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(id=payment_id, user=self.user)
            if payment.status == 'succeeded':
                return payment
            if payment.status in ('failed', 'refunded'):
                raise ValueError('Payment cannot be confirmed.')
            plan_id = payment.metadata.get('plan_id')
            plan = CreditPlan.objects.get(id=plan_id) if plan_id else None
            credits = plan.credits if plan else 0
            payment.status = 'succeeded'
            payment.save(update_fields=['status', 'updated_at'])
            if credits > 0:
                from django.utils import timezone
                from datetime import timedelta
                expires_at = None
                if plan and plan.plan_type != 'lifetime' and plan.duration_days:
                    expires_at = timezone.now() + timedelta(days=plan.duration_days)
                self.user.add_credits(
                    credits,
                    transaction_type='purchase',
                    description=f'Credit purchase -- {plan.name if plan else "manual"}',
                    payment=payment,
                    expires_at=expires_at,
                )
        return payment

    def list_my_transactions(self):
        from .models import CreditTransaction
        return CreditTransaction.objects.filter(user=self.user)

    def get_balance(self):
        return self.user.credits_balance


class AdminPaymentService:
    def list_credit_plans(self, search=None, status=None):
        from .models import CreditPlan
        qs = CreditPlan.objects.all()
        if status:
            qs = qs.filter(is_active=(status == 'active'))
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def get_credit_plan(self, plan_id):
        from .models import CreditPlan
        return CreditPlan.objects.get(id=plan_id)

    def create_credit_plan(self, **data):
        from .models import CreditPlan
        return CreditPlan.objects.create(**data)

    def update_credit_plan(self, plan_id, **data):
        plan = self.get_credit_plan(plan_id)
        for key, value in data.items():
            setattr(plan, key, value)
        plan.save()
        return plan

    def delete_credit_plan(self, plan_id):
        plan = self.get_credit_plan(plan_id)
        plan.delete()

    def list_transactions(self, search=None, type=None):
        from .models import CreditTransaction
        qs = CreditTransaction.objects.all().select_related('user', 'payment')
        if type:
            qs = qs.filter(type=type)
        if search:
            qs = qs.filter(user__email__icontains=search) | qs.filter(description__icontains=search)
        return qs

    def get_transaction(self, transaction_id):
        from .models import CreditTransaction
        return CreditTransaction.objects.select_related('user', 'payment').get(id=transaction_id)
